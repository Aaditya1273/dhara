# qr_app/services.py
"""Business rules for DHARA. Views stay thin; every state change is validated here."""
import hashlib
import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import (
    AuditEvent, Company, Equipment, EvidenceKind, FollowUpTask, Membership, Payment, ReviewStatus,
    ServiceRecord, ServiceRecordPhoto, SubscriptionPlan, WaterQualityReport,
)

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}
PDF_TYPES = {'.pdf': 'application/pdf'}

# Allowed review transitions. accepted/rejected are final: corrections are new events (`amends`).
REVIEW_TRANSITIONS = {
    ReviewStatus.PENDING: {ReviewStatus.ACCEPTED, ReviewStatus.REJECTED, ReviewStatus.CHANGES_REQUESTED},
    ReviewStatus.CHANGES_REQUESTED: {ReviewStatus.PENDING},
}


# --- Uploads -------------------------------------------------------------------------------

def validate_upload(f, allowed: dict) -> str:
    """Check extension, size and actual file content. Returns the canonical content type."""
    ext = Path(f.name).suffix.lower()
    if ext not in allowed:
        raise ValidationError(f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(allowed))}.")
    if f.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"'{f.name}' is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if f.size == 0:
        raise ValidationError(f"'{f.name}' is empty.")
    content_type = allowed[ext]
    f.seek(0)
    if content_type == 'application/pdf':
        if f.read(5) != b'%PDF-':
            raise ValidationError(f"'{f.name}' is not a valid PDF.")
    else:
        try:
            with Image.open(f) as img:
                img.verify()
                fmt = img.format
        except Exception:
            raise ValidationError(f"'{f.name}' is not a valid image.")
        if {'JPEG': 'image/jpeg', 'PNG': 'image/png'}.get(fmt) != content_type:
            raise ValidationError(f"'{f.name}' content does not match its extension.")
    f.seek(0)
    return content_type


def sha256_of(f) -> str:
    """Digest of the exact bytes received (or stored)."""
    h = hashlib.sha256()
    f.seek(0)
    for chunk in f.chunks() if hasattr(f, 'chunks') else iter(lambda: f.read(65536), b''):
        h.update(chunk)
    f.seek(0)
    return h.hexdigest()


def verify_digest(obj) -> bool:
    """Recompute the stored file's SHA-256 and compare. Detects later changes to that file only;
    it says nothing about whether a photo is genuine or what it shows."""
    with obj.file.open('rb') as fh:
        h = hashlib.sha256()
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest() == obj.sha256


def file_meta(f, content_type):
    return dict(original_name=Path(f.name).name[:255], content_type=content_type, size=f.size, sha256=sha256_of(f))


# --- Audit -------------------------------------------------------------------------------

def audit(company, actor, action, target, summary, **details):
    return AuditEvent.objects.create(
        company=company, actor=actor, action=action,
        target_type=target._meta.model_name, target_id=str(target.pk),
        summary=summary[:255], details=details,
    )


# --- Roles -------------------------------------------------------------------------------

def membership_for(user, company):
    if not user.is_authenticated:
        return None
    return Membership.objects.filter(user=user, company=company).first()


def require_admin(user, company):
    m = membership_for(user, company)
    if not (m and m.is_admin):
        raise PermissionDenied('Only a warden/administrator of this institution can do this.')
    return m


def require_member(user, company):
    m = membership_for(user, company)
    if not m:
        raise PermissionDenied('You are not a member of this institution.')
    return m


# --- Tanks -------------------------------------------------------------------------------

def save_tank(tank: Equipment, user, created: bool):
    require_admin(user, tank.company)
    with transaction.atomic():
        tank.save()
        audit(tank.company, user, 'tank.created' if created else 'tank.updated', tank,
              f"{'Registered' if created else 'Updated'} tank {tank.tank_code}")
    return tank


# --- Maintenance events -------------------------------------------------------------------

def attach_evidence(record: ServiceRecord, user, files_by_kind):
    """files_by_kind: iterable of (kind, UploadedFile). Validates all before storing any."""
    prepared = []
    for kind, f in files_by_kind:
        allowed = {**IMAGE_TYPES, **PDF_TYPES} if kind == EvidenceKind.DOCUMENT else IMAGE_TYPES
        prepared.append((kind, f, file_meta(f, validate_upload(f, allowed))))
    company = record.equipment.company
    created = []
    for kind, f, meta in prepared:
        ev = ServiceRecordPhoto.objects.create(record=record, kind=kind, file=f, uploaded_by=user, **meta)
        audit(company, user, 'evidence.attached', ev,
              f"Attached {ev.get_kind_display().lower()} to event #{record.pk}",
              event=record.pk, sha256=ev.sha256, file=ev.file.name, original_name=ev.original_name)
        created.append(ev)
    return created


def submit_event(tank: Equipment, user, data: dict, files_by_kind, amends: ServiceRecord = None):
    require_member(user, tank.company)
    if data['work_date'] > timezone.localdate():
        raise ValidationError('The work date cannot be in the future.')
    if amends is not None and (amends.equipment_id != tank.pk or amends.review_status == ReviewStatus.PENDING):
        raise ValidationError('Only a reviewed event of this tank can be corrected.')
    with transaction.atomic():
        record = ServiceRecord.objects.create(equipment=tank, author=user, amends=amends, **data)
        audit(tank.company, user, 'event.submitted', record,
              f"Submitted {record.get_event_type_display().lower()} for {tank.tank_code}",
              work_date=str(record.work_date), amends=amends.pk if amends else None)
        attach_evidence(record, user, files_by_kind)
    return record


def respond_to_changes(record: ServiceRecord, user, files_by_kind, note: str):
    """Submitter adds evidence after 'changes requested'; event returns to the review queue."""
    company = record.equipment.company
    require_member(user, company)
    with transaction.atomic():
        record = ServiceRecord.objects.select_for_update().get(pk=record.pk)
        if record.author_id != user.pk and not require_member(user, company).is_admin:
            raise PermissionDenied('Only the submitter or a warden can respond.')
        _check_transition(record.review_status, ReviewStatus.PENDING)
        if not files_by_kind and not note.strip():
            raise ValidationError('Add evidence or a note when responding.')
        attach_evidence(record, user, files_by_kind)
        record.review_status = ReviewStatus.PENDING
        record.reviewed_by = None
        record.reviewed_at = None
        record.save()
        audit(company, user, 'event.resubmitted', record, f"Responded to review on event #{record.pk}",
              note=note.strip())
    return record


def _check_transition(current, new):
    if new not in REVIEW_TRANSITIONS.get(current, set()):
        raise ValidationError(f"Cannot change review status from '{current}' to '{new}'.")


def review_event(record: ServiceRecord, reviewer, decision: str, notes: str = ''):
    company = record.equipment.company
    require_admin(reviewer, company)
    notes = notes.strip()
    with transaction.atomic():
        record = ServiceRecord.objects.select_for_update().get(pk=record.pk)
        _check_transition(record.review_status, decision)
        if record.author_id == reviewer.pk:
            raise PermissionDenied('A submitter cannot review their own maintenance event.')
        if decision == ReviewStatus.ACCEPTED and not record.photos.exists():
            raise ValidationError('An event with no evidence attached cannot be accepted.')
        if decision in (ReviewStatus.REJECTED, ReviewStatus.CHANGES_REQUESTED) and not notes:
            raise ValidationError('Give a reason when rejecting or requesting changes.')
        record.review_status = decision
        record.reviewed_by = reviewer
        record.reviewed_at = timezone.now()
        record.review_notes = notes
        record.save()
        audit(company, reviewer, f'event.{decision}', record,
              f"{record.get_review_status_display()}: event #{record.pk} ({record.equipment.tank_code})",
              notes=notes)
        if decision == ReviewStatus.CHANGES_REQUESTED:
            task = FollowUpTask.objects.create(
                equipment=record.equipment, kind=FollowUpTask.Kind.EVIDENCE_REQUESTED,
                title=f"Respond to review of event #{record.pk}: {notes[:120]}",
                due_date=timezone.localdate() + timedelta(days=7),
                assigned_to=record.author, related_event=record, created_by=reviewer,
            )
            audit(company, reviewer, 'followup.created', task, f"Follow-up: {task.title}")
    return record


# --- Water-quality reports ----------------------------------------------------------------

def upload_report(tank: Equipment, user, data: dict, f):
    require_admin(user, tank.company)
    meta = file_meta(f, validate_upload(f, {**PDF_TYPES, **IMAGE_TYPES}))
    with transaction.atomic():
        report = WaterQualityReport.objects.create(equipment=tank, uploaded_by=user, file=f, **meta, **data)
        audit(tank.company, user, 'report.uploaded', report,
              f"Linked water-quality report ({report.lab_name}, sample {report.sample_date}) to {tank.tank_code}",
              sha256=report.sha256, file=report.file.name, original_name=report.original_name)
    return report


def mark_report_reviewed(report: WaterQualityReport, user):
    company = report.equipment.company
    require_admin(user, company)
    with transaction.atomic():
        report = WaterQualityReport.objects.select_for_update().get(pk=report.pk)
        if report.review_status == WaterQualityReport.Review.REVIEWED:
            raise ValidationError('This report is already marked as reviewed.')
        report.review_status = WaterQualityReport.Review.REVIEWED
        report.reviewed_by = user
        report.reviewed_at = timezone.now()
        report.save()
        audit(company, user, 'report.reviewed', report, f"Marked report #{report.pk} as reviewed")
    return report


# --- Follow-ups ---------------------------------------------------------------------------

def sync_rule_followups(company: Company):
    """Open a follow-up for each tank that the configured policy says needs maintenance or a
    report, unless one is already open. Never closes tasks: a person records the resolution."""
    created = []
    today = timezone.localdate()
    open_pairs = set(FollowUpTask.objects.filter(
        equipment__company=company, status=FollowUpTask.Status.OPEN, kind__in=FollowUpTask.AUTO_KINDS,
    ).values_list('equipment_id', 'kind'))
    for tank in Equipment.objects.filter(company=company).with_dates():
        wanted = []
        if tank.needs_maintenance:
            wanted.append((FollowUpTask.Kind.OVERDUE_MAINTENANCE,
                           f"Record maintenance for {tank.tank_code}: " +
                           ('no accepted maintenance on record' if tank.maintenance_status == 'none'
                            else f'due {tank.next_due_date:%d %b %Y}'),
                           tank.next_due_date or today))
        if tank.report_missing:
            wanted.append((FollowUpTask.Kind.MISSING_REPORT,
                           f"Link a current water-quality report for {tank.tank_code}",
                           tank.next_report_due_date or today))
        for kind, title, due in wanted:
            if (tank.pk, kind) in open_pairs:
                continue
            try:
                with transaction.atomic():
                    task = FollowUpTask.objects.create(equipment=tank, kind=kind, title=title, due_date=due,
                                                       assigned_to=tank.responsible)
                    audit(company, None, 'followup.created', task, f"Follow-up (schedule rule): {title}")
                created.append(task)
            except IntegrityError:  # created concurrently by another request
                pass
    return created


def update_followup(task: FollowUpTask, user, assigned_to=None, due_date=None):
    company = task.equipment.company
    require_admin(user, company)
    if assigned_to is not None and not Membership.objects.filter(user=assigned_to, company=company).exists():
        raise ValidationError('The assignee must be a member of this institution.')
    task.assigned_to = assigned_to
    if due_date:
        task.due_date = due_date
    task.save()
    audit(company, user, 'followup.assigned', task,
          f"Follow-up #{task.pk} assigned to {assigned_to.email if assigned_to else 'nobody'}",
          due_date=str(task.due_date))
    return task


def resolve_followup(task: FollowUpTask, user, notes: str):
    company = task.equipment.company
    m = require_member(user, company)
    if not (m.is_admin or task.assigned_to_id == user.pk):
        raise PermissionDenied('Only the assignee or a warden can resolve this task.')
    if not notes.strip():
        raise ValidationError('Describe how the task was resolved.')
    with transaction.atomic():
        task = FollowUpTask.objects.select_for_update().get(pk=task.pk)
        if task.status != FollowUpTask.Status.OPEN:
            raise ValidationError('This task is already resolved.')
        task.status = FollowUpTask.Status.RESOLVED
        task.resolved_by = user
        task.resolved_at = timezone.now()
        task.resolution_notes = notes.strip()
        task.save()
        audit(company, user, 'followup.resolved', task, f"Resolved follow-up #{task.pk}", notes=task.resolution_notes)
    return task


# --- Upstream QRInvent billing (only when settings.BILLING_ENABLED) -----------------------

@transaction.atomic
def activate_free_plan(company: Company, plan: SubscriptionPlan) -> None:
    if company.payments.filter(plan=plan).exists() or company.subscription_plan_id == plan.pk:
        raise ValueError('The free trial has already been used.')
    company.subscription_plan = plan
    company.subscription_expires_on = timezone.localdate() + timedelta(days=14)
    company.auto_renew = False
    company.yookassa_payment_method_id = None
    company.save()


def create_yookassa_payment(company: Company, plan: SubscriptionPlan, period: str, request) -> str:
    from yookassa import Configuration, Payment as YooKassaPayment

    if period == 'monthly':
        amount, duration_days = plan.price_monthly, 30
    elif period == 'annually':
        amount, duration_days = plan.price_annually, 365
    else:
        raise ValueError("Billing period must be 'monthly' or 'annually'.")

    local_payment = Payment.objects.create(company=company, plan=plan, amount=amount,
                                           duration_days=duration_days, status='pending')
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return_url = request.build_absolute_uri(reverse('qr_app:payment_result', kwargs={'company_slug': company.slug}))
    yookassa_payment = YooKassaPayment.create({
        "amount": {"value": str(amount), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": f"Subscription '{plan.name}' for {company.name}",
        "metadata": {"local_payment_id": str(local_payment.id)},
        "save_payment_method": False,
    }, str(local_payment.id))
    local_payment.yookassa_payment_id = yookassa_payment.id
    local_payment.save()
    return yookassa_payment.confirmation.confirmation_url


@transaction.atomic
def process_successful_payment(payment: Payment, payment_info):
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == 'succeeded':
        return
    payment.status = 'succeeded'
    payment.metadata = json.loads(payment_info.json())
    payment.save()

    company = payment.company
    company.subscription_plan = payment.plan
    method = payment_info.payment_method
    if method and method.id and getattr(method, 'saved', False):
        company.yookassa_payment_method_id = method.id
        company.auto_renew = True
    else:
        company.auto_renew = False
    start_date = timezone.localdate()
    if company.has_active_subscription:
        start_date = company.subscription_expires_on
    company.subscription_expires_on = start_date + timedelta(days=payment.duration_days)
    company.save()
