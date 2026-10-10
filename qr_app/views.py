# qr_app/views.py
import ipaddress
import json
import logging
import secrets
import uuid
from datetime import timedelta
from io import BytesIO

import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, TemplateView

from . import services
from .forms import (
    CompanySettingsForm, FollowUpAssignForm, InvitationForm, InvitedUserRegistrationForm, MaintenanceEventForm,
    InterventionForm, ObservationForm, ResolveForm, SensorForm, RespondForm, ReviewForm, TankForm, UserRegistrationForm, WaterQualityReportForm,
)
from .mixins import ActiveSubscriptionRequiredMixin, AdminRequiredMixin, BillingEnabledMixin, CompanyRequiredMixin
from .models import (
    AuditEvent, Company, Equipment, FollowUpTask, Invitation, Membership, Payment, ReviewStatus, Role,
    ServiceRecord, ServiceRecordPhoto, SubscriptionPlan, TankIntervention, TankObservation, User, WaterQualityReport,
)

logger = logging.getLogger(__name__)


def flash_errors(request, exc):
    for msg in getattr(exc, 'messages', [str(exc)]):
        messages.error(request, msg)


def run_storage_action(request, fn):
    """Runs an upload. Storage failures (disk, S3) roll back the DB transaction and are reported
    honestly instead of showing success. Returns the result or None."""
    try:
        return fn()
    except (ValidationError, PermissionDenied):
        raise
    except Exception:
        logger.exception('Upload/storage failure')
        messages.error(request, 'The file could not be stored, so nothing was saved. Please try again.')
        return None


class CompanyView(CompanyRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def tanks(self):
        return Equipment.objects.filter(company=self.company)

    def get_tank(self, pk):
        return get_object_or_404(self.tanks().with_dates(), pk=pk)

    def get_event(self, pk):
        return get_object_or_404(ServiceRecord.objects.select_related('equipment', 'author', 'reviewed_by'),
                                 pk=pk, equipment__company=self.company)

    def go(self, name, **kwargs):
        return redirect(f'qr_app:{name}', company_slug=self.company.slug, **kwargs)


# --- Public pages ------------------------------------------------------------------------

class LandingPageView(TemplateView):
    template_name = 'landing_page.html'


def healthz(request):
    return JsonResponse({'status': 'ok'})


def public_tank_status(request, token):
    """Read-only QR page. Shows dates and statuses only: no people, notes, files or internal location."""
    tank = get_object_or_404(Equipment.objects.select_related('company').with_dates(), public_token=token)
    latest_event = tank.records.order_by('-created_at').first()
    latest_report = tank.reports.first()
    open_kinds = set(tank.followups.filter(status=FollowUpTask.Status.OPEN).values_list('kind', flat=True))
    return render(request, 'public/tank_status.html', {
        'tank': tank, 'latest_event': latest_event, 'latest_report': latest_report,
        'evidence_status': latest_event.evidence_status if latest_event else None,
        'open_kinds': open_kinds, 'Kind': FollowUpTask.Kind, 'now': timezone.now(),
    })


# --- Auth --------------------------------------------------------------------------------

def register_view(request):
    if request.user.is_authenticated:
        return redirect('select_company')
    form = UserRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.username = form.cleaned_data['email']
            user.set_password(form.cleaned_data['password'])
            user.save()
            company = Company.objects.create(name=form.cleaned_data['company_name'])
            Membership.objects.create(user=user, company=company, role=Role.ADMIN)
            services.audit(company, user, 'institution.created', company, f"Institution {company.name} registered")
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('select_company')
    return render(request, 'registration/register.html', {'form': form})


def accept_invitation_view(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    email, company = invitation.email, invitation.company
    if invitation.created_at < timezone.now() - timedelta(days=7):
        invitation.delete()
        messages.error(request, 'This invitation has expired. Ask your warden for a new one.')
        return redirect('login')

    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user:
        # The invitee must prove they own the account before joining.
        if request.user != existing_user:
            messages.info(request, f'Sign in as {email} to accept this invitation.')
            return redirect_to_login(request.get_full_path())
        with transaction.atomic():
            Membership.objects.get_or_create(user=existing_user, company=company, defaults={'role': invitation.role})
            services.audit(company, existing_user, 'member.joined', company, f"{email} joined as {invitation.get_role_display()}")
            invitation.delete()
        messages.success(request, f'You have joined {company.name}.')
        return redirect('qr_app:dashboard', company_slug=company.slug)

    form = InvitedUserRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = User.objects.create_user(username=email, email=email, password=form.cleaned_data['password'])
            Membership.objects.create(user=user, company=company, role=invitation.role)
            services.audit(company, user, 'member.joined', company, f"{email} joined as {invitation.get_role_display()}")
            invitation.delete()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('select_company')
    return render(request, 'invitations/accept_invitation.html', {'form': form, 'email': email, 'company': company})


@login_required
def select_company_view(request):
    memberships = Membership.objects.filter(user=request.user).select_related('company')
    if not memberships:
        messages.info(request, 'You are not a member of any institution yet.')
        return redirect('register')
    if len(memberships) == 1:
        return redirect('qr_app:dashboard', company_slug=memberships[0].company.slug)
    return render(request, 'registration/select_company.html', {'memberships': memberships})


# --- Overview ----------------------------------------------------------------------------

class DashboardView(CompanyView):
    def get(self, request, *args, **kwargs):
        services.sync_rule_followups(self.company)
        tanks = list(self.tanks().with_dates())
        pending = ServiceRecord.objects.filter(equipment__company=self.company, review_status=ReviewStatus.PENDING)
        open_tasks = FollowUpTask.objects.filter(equipment__company=self.company, status=FollowUpTask.Status.OPEN)
        my_tasks = open_tasks.filter(assigned_to=request.user).select_related('equipment')[:6]
        my_events = ServiceRecord.objects.filter(equipment__company=self.company, author=request.user
                                                 ).select_related('equipment')[:5]
        return render(request, 'dashboards/overview.html', {
            'tank_count': len(tanks),
            'overdue_count': sum(t.needs_maintenance for t in tanks),
            'due_soon_count': sum(t.maintenance_status == 'due_soon' for t in tanks),
            'missing_report_count': sum(t.report_missing for t in tanks),
            'pending_count': pending.count(),
            'pending_no_evidence_count': pending.filter(photos__isnull=True).count(),
            'open_task_count': open_tasks.count(),
            'attention': [t for t in tanks if t.needs_maintenance or t.maintenance_status == 'due_soon'
                          or t.report_missing][:8],
            'my_tasks': my_tasks, 'my_events': my_events,
            'activity': AuditEvent.objects.filter(company=self.company).select_related('actor')[:8],
        })


# --- Tanks -------------------------------------------------------------------------------

class TankListView(CompanyView):
    def get(self, request, *args, **kwargs):
        qs = self.tanks().with_dates().select_related('responsible')
        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(tank_code__icontains=q) | Q(name__icontains=q) | Q(building__icontains=q))
        building = request.GET.get('building', '')
        if building:
            qs = qs.filter(building=building)
        tanks = list(qs)
        status = request.GET.get('status', '')
        if status == 'attention':
            tanks = [t for t in tanks if t.needs_maintenance or t.report_missing]
        elif status:
            tanks = [t for t in tanks if t.maintenance_status == status]
        buildings = self.tanks().exclude(building='').values_list('building', flat=True).distinct().order_by('building')
        return render(request, 'tanks/tank_list.html', {
            'tanks': tanks, 'q': q, 'status': status, 'building': building, 'buildings': buildings,
            'total': self.tanks().count(),
        })


class TankFormView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def get_instance(self):
        pk = self.kwargs.get('pk')
        return get_object_or_404(Equipment, pk=pk, company=self.company) if pk else Equipment(company=self.company)

    def render_form(self, form, instance):
        return render(self.request, 'tanks/tank_form.html', {'form': form, 'tank': instance if instance.pk else None})

    def get(self, request, *args, **kwargs):
        instance = self.get_instance()
        return self.render_form(TankForm(instance=instance, company=self.company), instance)

    def post(self, request, *args, **kwargs):
        instance = self.get_instance()
        created = instance.pk is None
        if created and settings.BILLING_ENABLED and self.company.subscription_plan and \
                self.company.equipment.count() >= self.company.subscription_plan.max_equipment:
            messages.error(request, 'Your plan\'s tank limit has been reached.')
            return redirect('qr_app:tank_list', company_slug=self.company.slug)
        form = TankForm(request.POST, instance=instance, company=self.company)
        if not form.is_valid():
            return self.render_form(form, instance)
        tank = services.save_tank(form.save(commit=False), request.user, created)
        messages.success(request, f"Tank {tank.tank_code} {'registered' if created else 'updated'}.")
        return redirect('qr_app:tank_detail', company_slug=self.company.slug, pk=tank.pk)


class TankDetailView(CompanyView):
    def get(self, request, pk, *args, **kwargs):
        tank = self.get_tank(pk)
        events = tank.records.select_related('author', 'reviewed_by').annotate(evidence_count=Count('photos'))
        return render(request, 'tanks/tank_detail.html', {
            'tank': tank, 'events': events,
            'reports': tank.reports.select_related('uploaded_by', 'reviewed_by'),
            'followups': tank.followups.select_related('assigned_to').filter(status=FollowUpTask.Status.OPEN),
            'public_url': request.build_absolute_uri(reverse('public_tank_status', args=[tank.public_token])),
            'observations': tank.observations.select_related('entered_by', 'device')[:20],
            'latest': services.latest_readings(tank),
            'sensors': tank.sensors.all(),
            **self.twin_context(tank),
        })

    def twin_context(self, tank):
        if not tank.sensors.exists() and not tank.observations.filter(kind='water_temp').exists():
            return {'twin': None, 'twin_note': 'No water-temperature data yet.'}
        twin, hourly = services.tank_twin(tank)
        effects = [(iv, services.intervention_effect(iv, hourly if hourly.available else None))
                   for iv in tank.interventions.select_related('entered_by')]
        return {'twin': twin, 'twin_note': '' if twin else hourly.error, 'effects': effects,
                'chart': twin_chart(tank, twin) if twin and twin.forecast else None}


class TankQRView(CompanyView):
    def get(self, request, pk, *args, **kwargs):
        tank = get_object_or_404(self.tanks(), pk=pk)
        url = request.build_absolute_uri(reverse('public_tank_status', args=[tank.public_token]))
        buffer = BytesIO()
        qrcode.make(url, border=2).save(buffer, 'PNG')
        response = HttpResponse(buffer.getvalue(), content_type='image/png')
        if request.GET.get('download'):
            response['Content-Disposition'] = f'attachment; filename="dhara-{tank.tank_code}.png"'
        return response


# --- Field measurements and Tank Test Priority -------------------------------------------

class ObservationCreateView(CompanyView):
    def render_form(self, tank, form):
        return render(self.request, 'tanks/observation_form.html', {
            'tank': tank, 'form': form, 'methods': TankObservation.METHODS, 'units': TankObservation.UNITS})

    def get(self, request, pk, *args, **kwargs):
        tank = self.get_tank(pk)
        kind = request.GET.get('kind', TankObservation.Kind.FREE_CHLORINE)
        initial = {'kind': kind, 'measured_at': timezone.localtime().replace(second=0, microsecond=0),
                   'entered_unit': TankObservation.CANONICAL_UNIT.get(kind, 'mg/L'),
                   'method': 'dpd_strip' if kind == 'free_chlorine' else 'thermometer'}
        return self.render_form(tank, ObservationForm(initial=initial))

    def post(self, request, pk, *args, **kwargs):
        tank = self.get_tank(pk)
        form = ObservationForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_form(tank, form)
        cd = form.cleaned_data
        obs = run_storage_action(request, lambda: services.record_observation(
            tank, request.user, cd['kind'], cd['entered_value'], cd['entered_unit'], cd['method'],
            cd['measured_at'], cd['sample_point'], cd['notes'], cd.get('photo')))
        if obs is None:
            return self.render_form(tank, form)
        messages.success(request, f"Recorded {obs.get_kind_display().lower()}: {obs.value} "
                                  f"{TankObservation.CANONICAL_UNIT[obs.kind]}.")
        return redirect('qr_app:tank_detail', company_slug=self.company.slug, pk=tank.pk)


def twin_chart(tank, twin, width=640, height=200, pad=28):
    """Inline-SVG coordinates: last 48 h measured (hourly means) + forecast with its approximate band."""
    from zoneinfo import ZoneInfo
    from .twin import hourly_means
    tz = ZoneInfo(settings.TIME_ZONE)
    since = twin.forecast[0][0] - timedelta(hours=49)
    measured = sorted(hourly_means(tank.observations.filter(kind='water_temp', measured_at__gte=since)
                                   .values_list('measured_at', 'value'), tz).items())
    fc = twin.forecast
    times = [h for h, _ in measured] + [f[0] for f in fc]
    temps = [t for _, t in measured] + [f[2] for f in fc] + [f[3] for f in fc]
    t0, t1 = min(times), max(times)
    lo, hi = min(temps) - 1, max(temps) + 1
    span = max((t1 - t0).total_seconds(), 1)

    def x(h):
        return pad + (h - t0).total_seconds() / span * (width - 2 * pad)

    def y(t):
        return height - pad - (t - lo) / (hi - lo) * (height - 2 * pad)

    pts = lambda pairs: ' '.join(f'{x(h):.1f},{y(t):.1f}' for h, t in pairs)
    band = [(f[0], f[3]) for f in fc] + [(f[0], f[2]) for f in reversed(fc)]
    return {'w': width, 'h': height, 'measured': pts(measured), 'forecast': pts([(f[0], f[1]) for f in fc]),
            'band': pts(band), 'now_x': f'{x(fc[0][0]):.1f}', 'lo': f'{lo:.0f}', 'hi': f'{hi:.0f}',
            'y_lo': f'{height - pad:.0f}', 'y_hi': f'{pad:.0f}', 'pad': pad}


class SensorCreateView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def get_tank(self):
        return get_object_or_404(Equipment, pk=self.kwargs['pk'], company=self.company)

    def get(self, request, *args, **kwargs):
        return render(request, 'tanks/sensor_form.html', {'tank': self.get_tank(), 'form': SensorForm()})

    def post(self, request, *args, **kwargs):
        tank = self.get_tank()
        form = SensorForm(request.POST)
        if not form.is_valid():
            return render(request, 'tanks/sensor_form.html', {'tank': tank, 'form': form})
        device, token = services.register_sensor(tank, request.user, form.cleaned_data['thing_name'])
        # Rendered directly (never redirected or stored in a message) so the token is shown exactly once.
        response = render(request, 'tanks/sensor_created.html', {
            'tank': tank, 'device': device, 'token': token,
            'ingest_url': request.build_absolute_uri(reverse('sensor_ingest'))})
        response['Cache-Control'] = 'no-store'
        return response


class InterventionCreateView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def get_tank(self):
        return get_object_or_404(Equipment, pk=self.kwargs['pk'], company=self.company)

    def get(self, request, *args, **kwargs):
        return render(request, 'tanks/intervention_form.html', {'tank': self.get_tank(), 'form': InterventionForm()})

    def post(self, request, *args, **kwargs):
        tank = self.get_tank()
        form = InterventionForm(request.POST)
        if form.is_valid():
            try:
                services.record_intervention(tank, request.user, **form.cleaned_data)
                messages.success(request, 'Intervention recorded. Its effect will be estimated once enough '
                                          'measured days exist on both sides.')
                return redirect('qr_app:tank_detail', company_slug=self.company.slug, pk=tank.pk)
            except ValidationError as e:
                form.add_error(None, e)
        return render(request, 'tanks/intervention_form.html', {'tank': tank, 'form': form})


@csrf_exempt
def sensor_ingest(request):
    """POST JSON {"readings": [{"measured_at": "...+05:30", "water_temp_c": 31.2}], "token": "..."}
    Token may instead be sent as `Authorization: Bearer <token>`. Also answers AWS IoT Core's one-time
    HTTPS destination confirmation request."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    if len(request.body) > 256 * 1024:
        return JsonResponse({'error': 'payload too large'}, status=413)
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)
    if 'confirmationToken' in body and 'enableUrl' in body:
        logger.warning('AWS IoT destination confirmation received. Confirm it in the AWS IoT console with '
                       'token %s (enable URL %s).', body['confirmationToken'], body['enableUrl'])
        return JsonResponse({'status': 'confirmation logged'})
    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else body.get('token')
    device = services.authenticate_device(token)
    if device is None:
        return JsonResponse({'error': 'unknown or inactive device token'}, status=401)
    try:
        created, dupes, errors = services.ingest_readings(device, body.get('readings'))
    except ValidationError as e:
        return JsonResponse({'error': ' '.join(e.messages)}, status=400)
    return JsonResponse({'created': created, 'duplicates': dupes, 'rejected': errors},
                        status=200 if created or dupes or not errors else 400)


class TestPriorityView(CompanyView):
    def get(self, request, *args, **kwargs):
        forecast, rows = services.compute_priorities(self.company)
        created = services.sync_priority_followups(self.company, rows)
        if created:
            messages.info(request, f'{len(created)} new follow-up{"s" if len(created) != 1 else ""} opened '
                                   'from test-priority rules.')
        open_tasks = dict(FollowUpTask.objects.filter(
            equipment__company=self.company, status=FollowUpTask.Status.OPEN,
            kind=FollowUpTask.Kind.TEST_PRIORITY).values_list('equipment_id', 'pk'))
        return render(request, 'tanks/test_priority.html', {
            'forecast': forecast, 'rows': [(t, p, open_tasks.get(t.pk)) for t, p in rows],
            'actionable_count': sum(p.actionable for _, p in rows),
            'cfg': settings.DHARA_PRIORITY,
        })


# --- Maintenance events ------------------------------------------------------------------

class EventCreateView(CompanyView):
    def get_amends(self, tank):
        pk = self.request.GET.get('amends') or self.request.POST.get('amends')
        return get_object_or_404(ServiceRecord, pk=pk, equipment=tank) if pk else None

    def render_form(self, tank, form, amends):
        return render(self.request, 'maintenance/event_form.html', {'tank': tank, 'form': form, 'amends': amends})

    def get(self, request, pk, *args, **kwargs):
        tank = self.get_tank(pk)
        amends = self.get_amends(tank)
        initial = {'event_type': amends.event_type, 'work_date': amends.work_date} if amends else {
            'work_date': timezone.localdate()}
        return self.render_form(tank, MaintenanceEventForm(initial=initial), amends)

    def post(self, request, pk, *args, **kwargs):
        tank = self.get_tank(pk)
        amends = self.get_amends(tank)
        form = MaintenanceEventForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_form(tank, form, amends)
        data = {k: form.cleaned_data[k] for k in ('event_type', 'work_date', 'provider_name', 'notes')}
        try:
            record = run_storage_action(request, lambda: services.submit_event(
                tank, request.user, data, form.evidence(), amends=amends))
        except ValidationError as e:
            flash_errors(request, e)
            return self.render_form(tank, form, amends)
        if record is None:
            return self.render_form(tank, form, amends)
        messages.success(request, 'Maintenance event submitted. It is now waiting for review.')
        return self.go('event_detail', pk=record.pk)


class EventDetailView(CompanyView):
    def get(self, request, pk, *args, **kwargs):
        event = self.get_event(pk)
        can_review = (self.membership.is_admin and event.author_id != request.user.pk
                      and event.review_status == ReviewStatus.PENDING)
        can_respond = (event.review_status == ReviewStatus.CHANGES_REQUESTED
                       and (event.author_id == request.user.pk or self.membership.is_admin))
        return render(request, 'maintenance/event_detail.html', {
            'event': event, 'tank': event.equipment,
            'evidence': event.photos.select_related('uploaded_by'),
            'amendments': event.amendments.all(),
            'history': AuditEvent.objects.filter(company=self.company, target_type='servicerecord',
                                                 target_id=str(event.pk)).select_related('actor'),
            'can_review': can_review, 'review_form': ReviewForm() if can_review else None,
            'can_respond': can_respond, 'respond_form': RespondForm() if can_respond else None,
            'own_event_pending': event.author_id == request.user.pk and event.review_status == ReviewStatus.PENDING,
        })


class EventReviewView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        event = get_object_or_404(ServiceRecord, pk=pk, equipment__company=self.company)
        form = ReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Choose a review decision.')
        else:
            try:
                services.review_event(event, request.user, form.cleaned_data['decision'], form.cleaned_data['notes'])
                messages.success(request, 'Review decision recorded.')
            except ValidationError as e:
                flash_errors(request, e)
        return redirect('qr_app:event_detail', company_slug=self.company.slug, pk=event.pk)


class EventRespondView(CompanyView):
    def post(self, request, pk, *args, **kwargs):
        event = self.get_event(pk)
        form = RespondForm(request.POST, request.FILES)
        if not form.is_valid():
            for errs in form.errors.values():
                for e in errs:
                    messages.error(request, e)
        else:
            try:
                if run_storage_action(request, lambda: services.respond_to_changes(
                        event, request.user, form.evidence(), form.cleaned_data['note'])):
                    messages.success(request, 'Response sent. The event is back in the review queue.')
            except ValidationError as e:
                flash_errors(request, e)
        return self.go('event_detail', pk=event.pk)


class EvidenceVerifyView(CompanyView):
    def post(self, request, pk, *args, **kwargs):
        ev = get_object_or_404(ServiceRecordPhoto, pk=pk, record__equipment__company=self.company)
        try:
            ok = services.verify_digest(ev)
        except Exception:
            logger.exception('Digest verification could not read file %s', ev.pk)
            messages.error(request, 'The stored file could not be read for verification.')
        else:
            (messages.success if ok else messages.error)(
                request, f"SHA-256 {'matches' if ok else 'DOES NOT match'} the digest recorded at upload "
                         f"for '{ev.original_name}'.")
        return self.go('event_detail', pk=ev.record_id)


class ReviewQueueView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        base = ServiceRecord.objects.filter(equipment__company=self.company).select_related('equipment', 'author')
        return render(request, 'maintenance/review_queue.html', {
            'pending': base.filter(review_status=ReviewStatus.PENDING).annotate(evidence_count=Count('photos'))
                           .order_by('created_at'),
            'waiting': base.filter(review_status=ReviewStatus.CHANGES_REQUESTED),
            'recent': base.exclude(review_status__in=[ReviewStatus.PENDING, ReviewStatus.CHANGES_REQUESTED])
                          .select_related('reviewed_by').order_by('-reviewed_at')[:10],
        })


# --- Water-quality reports ---------------------------------------------------------------

class ReportListView(CompanyView):
    def get(self, request, *args, **kwargs):
        reports = WaterQualityReport.objects.filter(equipment__company=self.company).select_related(
            'equipment', 'uploaded_by', 'reviewed_by')
        tanks = list(self.tanks().with_dates())
        return render(request, 'reports/report_list.html', {
            'reports': reports,
            'missing': [t for t in tanks if t.report_missing],
            'no_policy': [t for t in tanks if not t.report_interval_days and not t.last_sample_date],
        })


class ReportCreateView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def get_tank(self):
        return get_object_or_404(Equipment, pk=self.kwargs['pk'], company=self.company)

    def get(self, request, *args, **kwargs):
        return render(request, 'reports/report_form.html', {'tank': self.get_tank(), 'form': WaterQualityReportForm()})

    def post(self, request, *args, **kwargs):
        tank = self.get_tank()
        form = WaterQualityReportForm(request.POST, request.FILES)
        if form.is_valid():
            data = {k: v for k, v in form.cleaned_data.items() if k != 'file'}
            report = run_storage_action(request, lambda: services.upload_report(
                tank, request.user, data, form.cleaned_data['file']))
            if report:
                messages.success(request, 'Water-quality report linked. It is marked as not yet reviewed.')
                return redirect('qr_app:tank_detail', company_slug=self.company.slug, pk=tank.pk)
        return render(request, 'reports/report_form.html', {'tank': tank, 'form': form})


class ReportReviewView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        report = get_object_or_404(WaterQualityReport, pk=pk, equipment__company=self.company)
        try:
            services.mark_report_reviewed(report, request.user)
            messages.success(request, 'Report marked as reviewed by your institution.')
        except ValidationError as e:
            flash_errors(request, e)
        return redirect('qr_app:tank_detail', company_slug=self.company.slug, pk=report.equipment_id)


# --- Follow-ups --------------------------------------------------------------------------

class FollowUpListView(CompanyView):
    def get(self, request, *args, **kwargs):
        services.sync_rule_followups(self.company)
        tasks = FollowUpTask.objects.filter(equipment__company=self.company).select_related(
            'equipment', 'assigned_to', 'resolved_by', 'related_event')
        show = request.GET.get('show', 'open')
        if show == 'mine':
            tasks = tasks.filter(assigned_to=request.user, status=FollowUpTask.Status.OPEN)
        elif show == 'resolved':
            tasks = tasks.filter(status=FollowUpTask.Status.RESOLVED).order_by('-resolved_at')
        else:
            tasks = tasks.filter(status=FollowUpTask.Status.OPEN)
        tasks = list(tasks)
        if self.membership.is_admin:
            for t in tasks:
                t.assign_form = FollowUpAssignForm(company=self.company, auto_id=f'id_t{t.pk}_%s', initial={
                    'assigned_to': t.assigned_to_id, 'due_date': t.due_date})
        return render(request, 'followups/followup_list.html', {'tasks': tasks, 'show': show})


class FollowUpAssignView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        task = get_object_or_404(FollowUpTask, pk=pk, equipment__company=self.company, status=FollowUpTask.Status.OPEN)
        form = FollowUpAssignForm(request.POST, company=self.company)
        if form.is_valid():
            services.update_followup(task, request.user, form.cleaned_data['assigned_to'], form.cleaned_data['due_date'])
            messages.success(request, 'Follow-up updated.')
        else:
            messages.error(request, 'Choose a valid assignee and due date.')
        return redirect('qr_app:followup_list', company_slug=self.company.slug)


class FollowUpResolveView(CompanyView):
    def post(self, request, pk, *args, **kwargs):
        task = get_object_or_404(FollowUpTask, pk=pk, equipment__company=self.company)
        form = ResolveForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Describe how the task was resolved.')
        else:
            try:
                services.resolve_followup(task, request.user, form.cleaned_data['notes'])
                messages.success(request, 'Follow-up resolved.')
            except ValidationError as e:
                flash_errors(request, e)
        return redirect(request.POST.get('next') or reverse('qr_app:followup_list',
                                                              kwargs={'company_slug': self.company.slug}))


# --- Private files -----------------------------------------------------------------------

def _serve(stored_file, content_type, filename):
    if settings.STORAGE_BACKEND == 's3':
        return redirect(stored_file.url)  # short-lived presigned URL
    response = FileResponse(stored_file.open('rb'), content_type=content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


class EvidenceFileView(CompanyView):
    def get(self, request, pk, *args, **kwargs):
        ev = get_object_or_404(ServiceRecordPhoto, pk=pk, record__equipment__company=self.company)
        return _serve(ev.file, ev.content_type, f"evidence-{ev.pk}{ev.file.name[ev.file.name.rfind('.'):]}")


class ReportFileView(CompanyView):
    def get(self, request, pk, *args, **kwargs):
        r = get_object_or_404(WaterQualityReport, pk=pk, equipment__company=self.company)
        return _serve(r.file, r.content_type, f"report-{r.pk}{r.file.name[r.file.name.rfind('.'):]}")


# --- Activity, team, settings ------------------------------------------------------------

class ActivityHistoryView(CompanyRequiredMixin, AdminRequiredMixin, ListView):
    template_name = 'dashboards/activity_list.html'
    context_object_name = 'events'
    paginate_by = 25

    def get_queryset(self):
        return AuditEvent.objects.filter(company=self.company).select_related('actor')


class TeamManageView(CompanyRequiredMixin, AdminRequiredMixin, ActiveSubscriptionRequiredMixin, View):
    def render_page(self, form):
        return render(self.request, 'team/manage_team.html', {
            'form': form,
            'memberships': Membership.objects.filter(company=self.company).select_related('user').order_by('user__email'),
            'invitations': Invitation.objects.filter(company=self.company),
        })

    def get(self, request, *args, **kwargs):
        return self.render_page(InvitationForm())

    def post(self, request, *args, **kwargs):
        form = InvitationForm(request.POST)
        if not form.is_valid():
            return self.render_page(form)
        email = form.cleaned_data['email'].lower()
        if settings.BILLING_ENABLED and self.company.subscription_plan and (
                self.company.members.count() + Invitation.objects.filter(company=self.company).count()
                >= self.company.subscription_plan.max_users):
            messages.error(request, 'Your plan\'s user limit has been reached.')
            return self.render_page(form)
        if self.company.members.filter(email__iexact=email).exists():
            messages.error(request, f'{email} is already a member.')
            return self.render_page(form)
        invitation = form.save(commit=False)
        invitation.email = email
        invitation.company = self.company
        invitation.token = secrets.token_urlsafe(32)
        invitation.save()
        services.audit(self.company, request.user, 'member.invited', invitation,
                       f"Invited {email} as {invitation.get_role_display()}")
        messages.success(request, f'Invitation created for {email}. Share the link below; it expires in 7 days.')
        return redirect('qr_app:manage_team', company_slug=self.company.slug)


class MemberRemoveView(CompanyRequiredMixin, AdminRequiredMixin, View):
    def get_membership(self, pk):
        return get_object_or_404(Membership.objects.select_related('user'), user_id=pk, company=self.company)

    def get(self, request, pk, *args, **kwargs):
        return render(request, 'team/member_confirm_delete.html', {'m': self.get_membership(pk)})

    def post(self, request, pk, *args, **kwargs):
        m = self.get_membership(pk)
        if m.user_id == request.user.pk:
            return HttpResponseForbidden('You cannot remove yourself.')
        m.delete()
        services.audit(self.company, request.user, 'member.removed', m.user, f"Removed {m.user.email} from the institution")
        messages.success(request, f'{m.user.email} was removed. Their past records are kept.')
        return redirect('qr_app:manage_team', company_slug=self.company.slug)


class InvitationRevokeView(CompanyRequiredMixin, AdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        get_object_or_404(Invitation, pk=pk, company=self.company).delete()
        messages.success(request, 'Invitation revoked.')
        return redirect('qr_app:manage_team', company_slug=self.company.slug)


class CompanySettingsView(CompanyRequiredMixin, AdminRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'settings/company_settings.html', {'form': CompanySettingsForm(instance=self.company)})

    def post(self, request, *args, **kwargs):
        form = CompanySettingsForm(request.POST, instance=self.company)
        if form.is_valid():
            form.save()
            services.audit(self.company, request.user, 'institution.updated', self.company, 'Institution settings updated')
            messages.success(request, 'Settings saved.')
            return redirect('qr_app:company_settings', company_slug=self.company.slug)
        return render(request, 'settings/company_settings.html', {'form': form})


# --- System ------------------------------------------------------------------------------

def custom_server_error_view(request, template_name='500.html'):
    error_id = uuid.uuid4()
    logger.critical(f"Server error, id {error_id}")
    return render(request, template_name, {'error_id': error_id}, status=500)


# --- Upstream QRInvent billing (disabled unless BILLING_ENABLED) -------------------------

class BillingView(CompanyRequiredMixin, AdminRequiredMixin, BillingEnabledMixin, View):
    pass


class SubscriptionManageView(BillingView):
    def get(self, request, *args, **kwargs):
        return render(request, 'settings/subscription_manage.html', {
            'company': self.company, 'equipment_usage': self.company.equipment.count(),
            'user_usage': self.company.members.count()})


class SubscriptionSelectView(BillingView):
    def get(self, request, *args, **kwargs):
        return render(request, 'settings/subscription_select.html',
                      {'plans': SubscriptionPlan.objects.order_by('price_monthly')})


class SubscriptionActivateView(BillingView):
    def post(self, request, *args, **kwargs):
        plan = get_object_or_404(SubscriptionPlan, id=request.POST.get('plan_id'))
        try:
            if plan.price_monthly == 0 and plan.price_annually == 0:
                services.activate_free_plan(self.company, plan)
                messages.success(request, f"Free plan '{plan.name}' activated.")
                return redirect('qr_app:subscription_manage', company_slug=self.company.slug)
            return redirect(services.create_yookassa_payment(self.company, plan, request.POST.get('period'), request))
        except ValueError as e:
            messages.error(request, str(e))
        except Exception:
            logger.exception('YooKassa payment creation failed')
            messages.error(request, 'The payment could not be created. Try again later.')
        return redirect('qr_app:subscription_select', company_slug=self.company.slug)


class ToggleAutoRenewView(BillingView):
    def post(self, request, *args, **kwargs):
        self.company.auto_renew = not self.company.auto_renew
        self.company.save()
        return redirect('qr_app:subscription_manage', company_slug=self.company.slug)


class CancelSubscriptionView(BillingView):
    def post(self, request, *args, **kwargs):
        self.company.auto_renew = False
        self.company.save()
        messages.success(request, 'Auto-renewal cancelled.')
        return redirect('qr_app:subscription_manage', company_slug=self.company.slug)


class PaymentResultView(BillingView):
    def get(self, request, *args, **kwargs):
        messages.info(request, 'Payment is being processed.')
        return render(request, 'settings/payment_result.html', {'company': self.company})


YOOKASSA_NETWORKS = [ipaddress.ip_network(n) for n in (
    '185.71.76.0/27', '185.71.77.0/27', '77.75.153.0/25', '77.75.154.128/25', '2a02:5180::/32',
    '77.75.156.11/32', '77.75.156.35/32')]


@csrf_exempt
def yookassa_webhook_view(request):
    """Upstream webhook. The payment status is always re-fetched from the YooKassa API using the
    ID stored on our own Payment row, so a forged notification cannot mark a payment paid."""
    if not settings.BILLING_ENABLED or request.method != 'POST':
        raise Http404
    try:
        if not any(ipaddress.ip_address(request.META.get('REMOTE_ADDR', '')) in n for n in YOOKASSA_NETWORKS):
            return HttpResponseForbidden()
    except ValueError:
        return HttpResponseForbidden()
    try:
        obj = json.loads(request.body).get('object') or {}
    except (json.JSONDecodeError, AttributeError):
        return HttpResponse(status=400)
    payment = Payment.objects.filter(id=(obj.get('metadata') or {}).get('local_payment_id')).first() \
        if (obj.get('metadata') or {}).get('local_payment_id') else None
    if not payment or not payment.yookassa_payment_id:
        return HttpResponse(status=200)
    from yookassa import Configuration, Payment as YooKassaPayment
    try:
        Configuration.account_id = settings.YOOKASSA_SHOP_ID
        Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
        info = YooKassaPayment.find_one(payment.yookassa_payment_id)
    except Exception:
        logger.exception('YooKassa status lookup failed')
        return HttpResponse(status=500)
    if info.status == 'succeeded' and str(info.amount.value) == str(payment.amount):
        services.process_successful_payment(payment, info)
    elif payment.status != info.status:
        payment.status = info.status
        payment.save()
    return HttpResponse(status=200)
