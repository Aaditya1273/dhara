# qr_app/tests.py
import json
import os
import shutil
import tempfile
import unittest
from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from . import services
from .management.commands.seed_demo import sample_pdf
from .models import (
    AuditEvent, Company, Equipment, FollowUpTask, Invitation, Membership, ReviewStatus, Role, ServiceRecord,
    ServiceRecordPhoto, User, WaterQualityReport,
)

MEDIA = tempfile.mkdtemp(prefix='dhara-test-media-')


def png(name='photo.png', size=(40, 30)):
    buf = BytesIO()
    Image.new('RGB', size, 'teal').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def pdf(name='report.pdf'):
    return SimpleUploadedFile(name, sample_pdf(), content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA, STORAGE_BACKEND='local')
class DharaTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.company = Company.objects.create(name='Test Hostel')
        self.other = Company.objects.create(name='Other School')
        self.warden = self.member('warden@t.io', Role.ADMIN)
        self.warden2 = self.member('warden2@t.io', Role.ADMIN)
        self.tech = self.member('tech@t.io', Role.TECHNICIAN)
        self.outsider = self.member('out@o.io', Role.ADMIN, self.other)
        self.tank = Equipment.objects.create(company=self.company, tank_code='T-1', name='Tank A',
                                             building='Block A', location='Roof, east stair',
                                             maintenance_interval_days=90, report_interval_days=180,
                                             responsible=self.tech)

    def member(self, email, role, company=None):
        u = User.objects.create_user(username=email, email=email, password='x-Strong-pass-1')
        Membership.objects.create(user=u, company=company or self.company, role=role)
        return u

    def url(self, name, *args, company=None):
        return reverse(f'qr_app:{name}', args=[(company or self.company).slug, *args])

    def login(self, user):
        self.client.force_login(user)

    def tank_dates(self, tank=None):
        return Equipment.objects.with_dates().get(pk=(tank or self.tank).pk)

    def submit(self, user=None, files=True, work_date=None):
        self.login(user or self.tech)
        data = {'event_type': 'cleaning', 'work_date': (work_date or timezone.localdate()).isoformat(),
                'provider_name': 'Demo Cleaners', 'notes': 'Drained and scrubbed.'}
        if files:
            data['after_photos'] = [png('after.png')]
            data['before_photos'] = [png('before.png')]
        return self.client.post(self.url('event_create', self.tank.pk), data)


class TankTests(DharaTestCase):
    def test_admin_creates_tank_with_audit(self):  # 1
        self.login(self.warden)
        r = self.client.post(self.url('tank_create'), {
            'tank_code': 'hb-02', 'name': 'Tank B', 'maintenance_interval_days': 120})
        tank = Equipment.objects.get(company=self.company, tank_code='HB-02')
        self.assertRedirects(r, self.url('tank_detail', tank.pk))
        self.assertTrue(AuditEvent.objects.filter(action='tank.created', target_id=str(tank.pk)).exists())

    def test_tank_validation(self):
        self.login(self.warden)
        r = self.client.post(self.url('tank_create'), {
            'tank_code': 't-1', 'name': 'Dup', 'maintenance_interval_days': 0, 'capacity_litres': -5})
        form = r.context['form']
        self.assertIn('tank_code', form.errors)  # duplicate in institution (case-insensitive)
        self.assertIn('maintenance_interval_days', form.errors)
        self.assertIn('capacity_litres', form.errors)
        r = self.client.post(self.url('tank_create'), {'tank_code': 'bad id!', 'name': 'X', 'maintenance_interval_days': 30})
        self.assertIn('tank_code', r.context['form'].errors)

    def test_same_tank_code_allowed_in_other_institution(self):
        self.login(self.outsider)
        self.client.post(self.url('tank_create', company=self.other),
                         {'tank_code': 'T-1', 'name': 'Theirs', 'maintenance_interval_days': 30})
        self.assertTrue(Equipment.objects.filter(company=self.other, tank_code='T-1').exists())

    def test_technician_cannot_create_tank(self):
        self.login(self.tech)
        r = self.client.post(self.url('tank_create'), {'tank_code': 'X', 'name': 'X', 'maintenance_interval_days': 30})
        self.assertEqual(r.status_code, 403)

    def test_qr_token_resolves_to_public_page(self):  # 2
        self.assertGreaterEqual(len(self.tank.public_token), 20)
        self.login(self.tech)
        r = self.client.get(self.url('tank_qr', self.tank.pk))
        self.assertEqual(r['Content-Type'], 'image/png')
        self.client.logout()
        r = self.client.get(reverse('public_tank_status', args=[self.tank.public_token]))
        self.assertContains(r, 'Tank A')
        self.assertEqual(self.client.get(reverse('public_tank_status', args=['guess'])).status_code, 404)

    def test_reserved_slug_not_used(self):
        self.assertNotEqual(Company.objects.create(name='Login').slug, 'login')


class PublicPageTests(DharaTestCase):
    def test_only_permitted_fields(self):  # 9, 11
        self.submit()
        self.client.logout()
        r = self.client.get(reverse('public_tank_status', args=[self.tank.public_token]))
        html = r.content.decode()
        for private in ('tech@t.io', 'Demo Cleaners', 'Drained and scrubbed', 'Roof, east stair', '/files/'):
            self.assertNotIn(private, html)
        self.assertIn('does not certify that the water is safe to drink', html)
        self.assertIn('No water-quality report linked.', html)
        for claim in ('contaminat', 'unsafe', 'safe to drink:', 'Safety score'):
            self.assertNotIn(claim.lower(), html.lower().replace('does not certify that the water is safe to drink', ''))
        self.assertNotIn('<form', html)

    def test_public_page_is_read_only(self):
        r = self.client.post(reverse('public_tank_status', args=[self.tank.public_token]), {'x': 1})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ServiceRecord.objects.count(), 0)


class MaintenanceTests(DharaTestCase):
    def test_submit_event_enters_pending_with_digests(self):  # 3, 5, 16
        r = self.submit()
        event = ServiceRecord.objects.get()
        self.assertRedirects(r, self.url('event_detail', event.pk))
        self.assertEqual(event.review_status, ReviewStatus.PENDING)
        self.assertEqual(event.author, self.tech)
        self.assertEqual(event.photos.count(), 2)
        ev = event.photos.first()
        self.assertEqual(len(ev.sha256), 64)
        self.assertTrue(services.verify_digest(ev))
        with open(ev.file.path, 'ab') as fh:  # tamper with the stored file
            fh.write(b'x')
        self.assertFalse(services.verify_digest(ev))

    def test_future_work_date_rejected(self):
        r = self.submit(work_date=timezone.localdate() + timedelta(days=2))
        self.assertIn('work_date', r.context['form'].errors)
        self.assertEqual(ServiceRecord.objects.count(), 0)

    def test_upload_validation(self):  # 14
        self.login(self.tech)
        base = {'event_type': 'cleaning', 'work_date': timezone.localdate().isoformat()}
        cases = {
            'wrong extension': SimpleUploadedFile('x.exe', b'MZ...', content_type='application/octet-stream'),
            'fake image': SimpleUploadedFile('x.png', b'not an image', content_type='image/png'),
            'pdf as photo': pdf('x.pdf'),
        }
        for label, f in cases.items():
            r = self.client.post(self.url('event_create', self.tank.pk), {**base, 'after_photos': [f]})
            self.assertIn('after_photos', r.context['form'].errors, label)
        with mock.patch.object(services, 'MAX_UPLOAD_BYTES', 20):
            r = self.client.post(self.url('event_create', self.tank.pk), {**base, 'after_photos': [png()]})
            self.assertIn('larger than', str(r.context['form'].errors))
        r = self.client.post(self.url('event_create', self.tank.pk),
                             {**base, 'after_photos': [png(f'{i}.png') for i in range(4)]})
        self.assertIn('after_photos', r.context['form'].errors)
        self.assertEqual(ServiceRecord.objects.count(), 0)

    def test_storage_failure_is_reported_and_nothing_saved(self):  # 17
        with mock.patch('django.core.files.storage.FileSystemStorage._save', side_effect=OSError('disk full')):
            r = self.submit()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'could not be stored')
        self.assertEqual(ServiceRecord.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.filter(action='event.submitted').count(), 0)


class ReviewTests(DharaTestCase):
    def setUp(self):
        super().setUp()
        self.submit()
        self.event = ServiceRecord.objects.get()

    def review(self, user, decision, notes=''):
        self.login(user)
        return self.client.post(self.url('event_review', self.event.pk), {'decision': decision, 'notes': notes})

    def test_warden_accepts(self):  # 6
        self.review(self.warden, 'accepted')
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_status, ReviewStatus.ACCEPTED)
        self.assertEqual(self.event.reviewed_by, self.warden)
        self.assertIsNotNone(self.event.reviewed_at)

    def test_reject_requires_reason(self):
        self.review(self.warden, 'rejected')
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_status, ReviewStatus.PENDING)
        self.review(self.warden, 'rejected', 'Photos are of a different tank.')
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_status, ReviewStatus.REJECTED)
        self.assertTrue(ServiceRecord.objects.filter(pk=self.event.pk).exists())  # kept, not deleted

    def test_unauthorized_cannot_review(self):  # 7
        self.assertEqual(self.review(self.tech, 'accepted').status_code, 403)
        self.assertEqual(self.review(self.outsider, 'accepted').status_code, 403)
        self.client.logout()
        self.client.post(self.url('event_review', self.event.pk), {'decision': 'accepted'})
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_status, ReviewStatus.PENDING)

    def test_no_self_review(self):
        own = services.submit_event(self.tank, self.warden, {'event_type': 'inspection',
                                    'work_date': timezone.localdate()}, [('after', png())])
        with self.assertRaises(PermissionDenied):
            services.review_event(own, self.warden, ReviewStatus.ACCEPTED)
        services.review_event(own, self.warden2, ReviewStatus.ACCEPTED)

    def test_cannot_accept_without_evidence(self):
        bare = services.submit_event(self.tank, self.tech, {'event_type': 'inspection',
                                     'work_date': timezone.localdate()}, [])
        self.assertEqual(bare.evidence_status, 'missing')
        with self.assertRaises(ValidationError):
            services.review_event(bare, self.warden, ReviewStatus.ACCEPTED)

    def test_invalid_transitions(self):  # 15
        services.review_event(self.event, self.warden, ReviewStatus.ACCEPTED)
        for decision in (ReviewStatus.REJECTED, ReviewStatus.CHANGES_REQUESTED, ReviewStatus.PENDING):
            with self.assertRaises(ValidationError):
                services.review_event(self.event, self.warden2, decision, 'x')
        with self.assertRaises(ValidationError):
            services.respond_to_changes(self.event, self.tech, [], 'more')

    def test_changes_requested_round_trip_and_followup(self):  # 13 (reviewer-created task)
        self.review(self.warden, 'changes_requested', 'Add a photo of the inside wall.')
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_status, ReviewStatus.CHANGES_REQUESTED)
        task = FollowUpTask.objects.get(kind=FollowUpTask.Kind.EVIDENCE_REQUESTED)
        self.assertEqual(task.assigned_to, self.tech)
        self.login(self.tech)
        self.client.post(self.url('event_respond', self.event.pk), {'note': 'Added', 'after_photos': [png('wall.png')]})
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_status, ReviewStatus.PENDING)
        self.assertEqual(self.event.photos.count(), 3)
        self.client.post(self.url('followup_resolve', task.pk), {'notes': 'Photo added to event.'})
        task.refresh_from_db()
        self.assertEqual(task.status, FollowUpTask.Status.RESOLVED)
        self.assertEqual(task.resolved_by, self.tech)

    def test_correction_creates_new_event(self):
        services.review_event(self.event, self.warden, ReviewStatus.ACCEPTED)
        self.login(self.tech)
        self.client.post(self.url('event_create', self.tank.pk) + f'?amends={self.event.pk}', {
            'event_type': 'cleaning', 'work_date': timezone.localdate().isoformat(), 'amends': self.event.pk,
            'notes': 'Correct date', 'after_photos': [png()]})
        correction = ServiceRecord.objects.exclude(pk=self.event.pk).get()
        self.assertEqual(correction.amends, self.event)
        self.event.refresh_from_db()
        self.assertEqual(self.event.review_status, ReviewStatus.ACCEPTED)  # original untouched


class IsolationTests(DharaTestCase):
    def test_cross_institution_access_denied(self):  # 8
        self.submit()
        event = ServiceRecord.objects.get()
        ev = event.photos.first()
        self.login(self.outsider)
        own_slug_urls = [  # outsider's own institution slug, our object ids
            self.url('tank_detail', self.tank.pk, company=self.other),
            self.url('event_detail', event.pk, company=self.other),
            self.url('evidence_file', ev.pk, company=self.other),
            self.url('tank_qr', self.tank.pk, company=self.other),
        ]
        for u in own_slug_urls:
            self.assertEqual(self.client.get(u).status_code, 404, u)
        for u in (self.url('tank_detail', self.tank.pk), self.url('dashboard'), self.url('evidence_file', ev.pk)):
            self.assertEqual(self.client.get(u).status_code, 403, u)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(self.url('dashboard'))
        self.assertTrue(r.url.startswith(reverse('login')))

    def test_role_is_per_institution(self):
        # The outsider is an admin elsewhere; invited here as technician they must not become admin.
        inv = Invitation.objects.create(email='out@o.io', company=self.company, role=Role.TECHNICIAN, token='tok')
        self.login(self.outsider)
        self.client.get(reverse('accept_invitation', args=[inv.token]))
        self.assertEqual(Membership.objects.get(user=self.outsider, company=self.company).role, Role.TECHNICIAN)
        self.assertEqual(self.client.get(self.url('review_queue')).status_code, 403)
        self.assertEqual(self.client.post(self.url('member_delete', self.warden.pk)).status_code, 403)

    def test_invitation_for_existing_user_requires_their_login(self):
        inv = Invitation.objects.create(email='out@o.io', company=self.company, token='tok2')
        self.client.get(reverse('accept_invitation', args=[inv.token]))  # anonymous
        self.assertFalse(Membership.objects.filter(user=self.outsider, company=self.company).exists())


class WaterQualityTests(DharaTestCase):
    def test_report_independent_of_maintenance(self):  # 10
        self.submit()
        event = ServiceRecord.objects.get()
        self.login(self.warden)
        r = self.client.post(self.url('report_create', self.tank.pk), {
            'lab_name': 'Example Lab (SAMPLE)', 'sample_date': timezone.localdate().isoformat(),
            'parameters': 'pH, TDS', 'file': pdf()})
        self.assertRedirects(r, self.url('tank_detail', self.tank.pk))
        report = WaterQualityReport.objects.get()
        self.assertEqual(report.review_status, WaterQualityReport.Review.UNREVIEWED)
        self.assertEqual(len(report.sha256), 64)
        event.refresh_from_db()
        self.assertEqual(event.review_status, ReviewStatus.PENDING)  # report did not touch maintenance
        services.review_event(event, self.warden, ReviewStatus.REJECTED, 'blurry')
        report.refresh_from_db()
        self.assertEqual(report.review_status, WaterQualityReport.Review.UNREVIEWED)  # and vice versa
        self.assertFalse(self.tank_dates().report_missing)

    def test_report_validation_and_permission(self):
        self.login(self.warden)
        r = self.client.post(self.url('report_create', self.tank.pk), {
            'lab_name': 'Lab', 'sample_date': timezone.localdate().isoformat(),
            'report_date': (timezone.localdate() - timedelta(days=3)).isoformat(),
            'file': SimpleUploadedFile('r.pdf', b'<html>', content_type='application/pdf')})
        self.assertIn('report_date', r.context['form'].errors)
        self.assertIn('file', r.context['form'].errors)
        self.login(self.tech)
        self.assertEqual(self.client.get(self.url('report_create', self.tank.pk)).status_code, 403)

    def test_missing_report_is_a_gap_not_a_claim(self):  # 11
        self.assertTrue(self.tank_dates().report_missing)
        self.login(self.warden)
        html = self.client.get(self.url('tank_detail', self.tank.pk)).content.decode()
        self.assertIn('No water-quality report linked.', html)
        self.assertIn('not a finding about the water', html)
        self.assertNotIn('contaminated', html.lower())


class ScheduleTests(DharaTestCase):
    def test_due_dates_follow_policy(self):  # 12
        self.assertEqual(self.tank_dates().maintenance_status, 'none')
        work = timezone.localdate() - timedelta(days=100)
        event = services.submit_event(self.tank, self.tech, {'event_type': 'cleaning', 'work_date': work},
                                      [('after', png())])
        self.assertEqual(self.tank_dates().maintenance_status, 'none')  # pending does not count
        services.review_event(event, self.warden, ReviewStatus.ACCEPTED)
        t = self.tank_dates()
        self.assertEqual(t.next_due_date, work + timedelta(days=90))
        self.assertEqual(t.maintenance_status, 'overdue')
        self.tank.maintenance_interval_days = 110
        self.tank.save()
        self.assertEqual(self.tank_dates().maintenance_status, 'due_soon')
        self.tank.maintenance_interval_days = 365
        self.tank.save()
        self.assertEqual(self.tank_dates().maintenance_status, 'ok')

    def test_rule_followups_assign_and_resolve(self):  # 13
        created = services.sync_rule_followups(self.company)
        kinds = {t.kind for t in created}
        self.assertEqual(kinds, {FollowUpTask.Kind.OVERDUE_MAINTENANCE, FollowUpTask.Kind.MISSING_REPORT})
        self.assertEqual(services.sync_rule_followups(self.company), [])  # idempotent
        task = FollowUpTask.objects.get(kind=FollowUpTask.Kind.OVERDUE_MAINTENANCE)
        self.assertEqual(task.assigned_to, self.tech)  # tank's responsible person
        self.login(self.warden)
        self.client.post(self.url('followup_assign', task.pk),
                         {'assigned_to': self.warden2.pk, 'due_date': timezone.localdate().isoformat()})
        task.refresh_from_db()
        self.assertEqual(task.assigned_to, self.warden2)
        self.login(self.tech)  # no longer assignee, not admin
        self.client.post(self.url('followup_resolve', task.pk), {'notes': 'done'})
        task.refresh_from_db()
        self.assertEqual(task.status, FollowUpTask.Status.OPEN)
        self.login(self.warden2)
        self.client.post(self.url('followup_resolve', task.pk), {'notes': ''})
        task.refresh_from_db()
        self.assertEqual(task.status, FollowUpTask.Status.OPEN)  # notes required
        self.client.post(self.url('followup_resolve', task.pk), {'notes': 'Cleaned, event #1 accepted.'})
        task.refresh_from_db()
        self.assertEqual(task.status, FollowUpTask.Status.RESOLVED)

    def test_no_report_followup_without_policy(self):
        self.tank.report_interval_days = None
        self.tank.save()
        kinds = {t.kind for t in services.sync_rule_followups(self.company)}
        self.assertNotIn(FollowUpTask.Kind.MISSING_REPORT, kinds)


class LegacyAndPagesTests(DharaTestCase):
    def test_register_login_and_core_pages_render(self):  # 18
        r = self.client.post(reverse('register'), {'email': 'new@x.io', 'company_name': 'New Hostel',
                                                   'password': 'Long-pass-123', 'password2': 'Long-pass-123'})
        self.assertEqual(r.status_code, 302)
        m = Membership.objects.get(user__email='new@x.io')
        self.assertEqual(m.role, Role.ADMIN)
        self.submit()
        event = ServiceRecord.objects.get()
        self.login(self.warden)
        for name, args in [('dashboard', []), ('tank_list', []), ('tank_create', []), ('tank_detail', [self.tank.pk]),
                           ('tank_update', [self.tank.pk]), ('event_create', [self.tank.pk]),
                           ('event_detail', [event.pk]), ('review_queue', []), ('report_list', []),
                           ('report_create', [self.tank.pk]), ('followup_list', []), ('activity_history', []),
                           ('manage_team', []), ('company_settings', []), ('evidence_file', [event.photos.first().pk])]:
            self.assertEqual(self.client.get(self.url(name, *args)).status_code, 200, name)
        for path in ('/', reverse('login'), reverse('register'), reverse('healthz')):
            self.client.logout()
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_billing_disabled_never_blocks(self):
        self.login(self.warden)
        self.assertEqual(self.client.get(self.url('dashboard')).status_code, 200)
        self.assertEqual(self.client.get(self.url('subscription_select')).status_code, 403)

    @override_settings(BILLING_ENABLED=True)
    def test_billing_gate_when_enabled(self):
        self.login(self.warden)
        self.assertRedirects(self.client.get(self.url('dashboard')), self.url('subscription_select'),
                             fetch_redirect_response=False)


@unittest.skipUnless(os.getenv('DHARA_S3_TEST_BUCKET'), 'set DHARA_S3_TEST_BUCKET (and AWS credentials) to run')
class LiveS3Tests(DharaTestCase):
    """Uploads to a real bucket. Run: DHARA_S3_TEST_BUCKET=my-test-bucket python manage.py test qr_app.tests.LiveS3Tests"""

    def test_round_trip(self):
        from storages.backends.s3 import S3Storage
        storage = S3Storage(bucket_name=os.environ['DHARA_S3_TEST_BUCKET'], default_acl=None, querystring_auth=True,
                            region_name=os.getenv('AWS_REGION', 'ap-south-1'), file_overwrite=False, location='dhara-test')
        f = png()
        digest = services.sha256_of(f)
        name = storage.save('evidence/live-test.png', f)
        try:
            with storage.open(name, 'rb') as fh:
                import hashlib
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), digest)
            self.assertIn('X-Amz-Signature', storage.url(name))  # private: presigned URL only
        finally:
            storage.delete(name)


class MockedS3Tests(DharaTestCase):
    """Exercises the real S3 code path (django-storages + boto3) against moto's in-memory S3."""

    def test_evidence_stored_privately_in_s3(self):
        try:
            from moto import mock_aws
        except ImportError:
            self.skipTest('moto not installed (pip install -r requirements-dev.txt)')
        import boto3
        from storages.backends.s3 import S3Storage

        with mock_aws():
            os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
            os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
            client = boto3.client('s3', region_name='ap-south-1')
            client.create_bucket(Bucket='dhara-test', CreateBucketConfiguration={'LocationConstraint': 'ap-south-1'})
            s3 = S3Storage(bucket_name='dhara-test', region_name='ap-south-1', default_acl=None,
                           querystring_auth=True, file_overwrite=False, location='dhara')
            field = ServiceRecordPhoto._meta.get_field('file')
            with mock.patch.object(field, 'storage', s3), override_settings(STORAGE_BACKEND='s3'):
                event = services.submit_event(self.tank, self.tech, {'event_type': 'cleaning',
                                              'work_date': timezone.localdate()}, [('after', png())])
                ev = event.photos.get()
                key = f'dhara/{ev.file.name}'
                head = client.head_object(Bucket='dhara-test', Key=key)
                self.assertEqual(head['ContentLength'], ev.size)
                acl = client.get_object_acl(Bucket='dhara-test', Key=key)
                self.assertFalse([g for g in acl['Grants'] if 'AllUsers' in g['Grantee'].get('URI', '')])
                self.assertTrue(services.verify_digest(ev))
                self.login(self.tech)
                r = self.client.get(self.url('evidence_file', ev.pk))
                self.assertEqual(r.status_code, 302)
                self.assertIn('X-Amz-Signature', r.url)


# --- Tank Test Priority -------------------------------------------------------------------

from datetime import date, datetime  # noqa: E402
from decimal import Decimal  # noqa: E402
from types import SimpleNamespace  # noqa: E402
import urllib.error  # noqa: E402

from django.conf import settings as dj_settings  # noqa: E402
from django.core.cache import cache  # noqa: E402

from . import priority as prio  # noqa: E402
from . import weather  # noqa: E402
from .models import TankObservation  # noqa: E402

CFG = {'CHLORINE_MIN_MG_L': 0.2, 'CHLORINE_NEAR_MARGIN_MG_L': 0.1, 'CHLORINE_MAX_MG_L': 4.0,
       'WATER_WARM_C': 25.0, 'FORECAST_HOT_C': 35.0, 'CHLORINE_MAX_AGE_HOURS': 72,
       'TEMP_MAX_AGE_HOURS': 72, 'WARM_RETEST_HOURS': 24}
NOW = timezone.make_aware(datetime(2026, 5, 20, 12, 0))
NO_WX = weather.unavailable('test: no forecast')


def hot(max_c=41.0):
    return weather.Forecast(available=True, daily_max_c=[(date(2026, 5, 20), max_c - 2), (date(2026, 5, 21), max_c)])


def tank_profile(placement='rooftop', shade='full_sun'):
    t = SimpleNamespace(placement=placement, shade=shade)
    t.sun_exposed = placement in ('rooftop', 'elevated', 'ground') and shade == 'full_sun'
    return t


def reading(value, hours_ago):
    return prio.Reading(value, NOW - timedelta(hours=hours_ago))


class UnitAndValidationTests(TestCase):
    K = TankObservation.Kind

    def test_conversions(self):
        self.assertEqual(services.to_canonical(self.K.WATER_TEMP, Decimal('98.6'), '°F'), Decimal('37.00'))
        self.assertEqual(services.to_canonical(self.K.WATER_TEMP, Decimal('32'), '°F'), Decimal('0.00'))
        self.assertEqual(services.to_canonical(self.K.WATER_TEMP, Decimal('31.456'), '°C'), Decimal('31.46'))
        self.assertEqual(services.to_canonical(self.K.FREE_CHLORINE, Decimal('0.5'), 'ppm'), Decimal('0.50'))
        with self.assertRaises(ValidationError):
            services.to_canonical(self.K.FREE_CHLORINE, Decimal('1'), '°C')  # wrong unit for kind

    def test_validation_rules(self):
        now = timezone.now()
        ok = services.validate_observation(self.K.FREE_CHLORINE, Decimal('0.4'), 'mg/L', 'dpd_strip', now)
        self.assertEqual(ok, Decimal('0.40'))
        bad = [
            (self.K.FREE_CHLORINE, '11', 'mg/L', 'dpd_strip', now),            # implausible
            (self.K.FREE_CHLORINE, '-0.1', 'mg/L', 'dpd_strip', now),          # negative
            (self.K.WATER_TEMP, '200', '°F', 'thermometer', now),              # 93.3 °C
            (self.K.WATER_TEMP, '30', '°C', 'dpd_strip', now),                 # method/kind mismatch
            (self.K.WATER_TEMP, '30', '°C', 'thermometer', now + timedelta(hours=1)),   # future
            (self.K.WATER_TEMP, '30', '°C', 'thermometer', now - timedelta(days=31)),   # too old
        ]
        for args in bad:
            with self.assertRaises(ValidationError, msg=str(args)):
                services.validate_observation(args[0], Decimal(args[1]), *args[2:])
        # range edges are inclusive
        services.validate_observation(self.K.WATER_TEMP, Decimal('70'), '°C', 'probe', now)
        services.validate_observation(self.K.FREE_CHLORINE, Decimal('0'), 'mg/L', 'photometer', now)

    def test_db_constraint_backs_up_validation(self):
        from django.db import IntegrityError, transaction
        c = Company.objects.create(name='C')
        u = User.objects.create_user(username='u@x.io', email='u@x.io', password='x-Strong-pass-1')
        t = Equipment.objects.create(company=c, tank_code='T', name='T', maintenance_interval_days=30)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TankObservation.objects.create(equipment=t, kind='free_chlorine', value=Decimal('12'), entered_value=12,
                                           entered_unit='mg/L', method='dpd_strip', measured_at=timezone.now(),
                                           entered_by=u)


class PriorityRuleTests(unittest.TestCase):
    def ev(self, chlorine=None, temp=None, forecast=NO_WX, tank=None):
        return prio.evaluate(tank or tank_profile(), chlorine, temp, forecast, CFG, NOW)

    def test_missing_reading(self):
        p = self.ev()
        self.assertEqual((p.level, p.action), ('medium', 'test'))
        self.assertEqual(self.ev(forecast=hot()).level, 'high')  # heat raises urgency of a missing reading

    def test_below_threshold_and_exact_boundary(self):
        p = self.ev(chlorine=reading(0.19, 2))
        self.assertEqual((p.level, p.action), ('urgent', 'review'))
        p = self.ev(chlorine=reading(0.2, 2))       # exactly the minimum is not below it...
        self.assertEqual(p.action, 'repeat')          # ...but it is within the near-margin
        self.assertFalse(self.ev(chlorine=reading(0.3, 2)).actionable)   # 0.3 = min + margin: not near

    def test_above_maximum(self):
        self.assertEqual((self.ev(chlorine=reading(4.5, 1)).action), 'review')

    def test_stale_boundary(self):
        self.assertFalse(self.ev(chlorine=reading(0.5, 72)).actionable)    # exactly 72 h: still fresh
        p = self.ev(chlorine=reading(0.5, 72.5))
        self.assertEqual((p.level, p.action), ('medium', 'test'))
        self.assertEqual(self.ev(chlorine=reading(0.5, 73), forecast=hot()).level, 'high')

    def test_stale_low_reading_is_retest_not_alarm(self):
        p = self.ev(chlorine=reading(0.1, 100))
        self.assertEqual(p.action, 'test')            # old data never produces an "urgent below" finding

    def test_temperature_and_forecast_boundaries(self):
        fine = reading(0.6, 30)                        # healthy but 30 h old
        self.assertFalse(self.ev(chlorine=fine, temp=reading(24.99, 1)).actionable)
        p = self.ev(chlorine=fine, temp=reading(25.0, 1))   # warm boundary is inclusive
        self.assertEqual((p.level, p.action), ('medium', 'repeat'))
        self.assertFalse(self.ev(chlorine=fine, forecast=hot(34.9)).actionable)
        self.assertEqual(self.ev(chlorine=fine, forecast=hot(35.0)).action, 'repeat')
        shaded = tank_profile('rooftop', 'shaded')
        self.assertFalse(self.ev(chlorine=reading(0.6, 24), forecast=hot(), tank=shaded).actionable)  # 24 h not > 24 h
        self.assertEqual(self.ev(chlorine=reading(0.6, 24.5), forecast=hot(), tank=shaded).action, 'repeat')

    def test_stale_temperature_is_not_heat_context(self):
        self.assertFalse(self.ev(chlorine=reading(0.6, 30), temp=reading(33, 80)).actionable)

    def test_weather_failure_degrades_gracefully(self):
        p = self.ev(chlorine=reading(0.6, 30))
        self.assertFalse(p.actionable)
        self.assertIn('Weather forecast unavailable', p.context[0])

    def test_sun_exposed_temperature_gap(self):
        p = self.ev(chlorine=reading(0.6, 2), forecast=hot())
        self.assertEqual((p.level, p.action), ('low', 'test'))
        shaded = self.ev(chlorine=reading(0.6, 2), forecast=hot(), tank=tank_profile('rooftop', 'shaded'))
        self.assertFalse(shaded.actionable)

    def test_unknown_profile_is_informational(self):
        p = self.ev(chlorine=reading(0.6, 2), tank=tank_profile('unknown', 'unknown'))
        self.assertEqual(p.action, 'profile')
        self.assertFalse(p.actionable)

    def test_ordering(self):
        levels = [self.ev(chlorine=c).rank for c in (reading(0.1, 1), None, reading(0.6, 1))]
        self.assertEqual(levels, sorted(levels))


class WeatherClientTests(TestCase):
    def setUp(self):
        cache.clear()

    def fake(self, body):
        resp = mock.MagicMock()
        resp.read.return_value = body if isinstance(body, bytes) else json.dumps(body).encode()
        resp.__enter__.return_value = resp
        return resp

    def test_success_parses_and_sends_timezone(self):
        body = {'daily': {'time': ['2026-05-20', '2026-05-21'], 'temperature_2m_max': [39.5, 41.2]}}
        with mock.patch('urllib.request.urlopen', return_value=self.fake(body)) as m:
            f = weather.fetch(28.61, 77.21)
            weather.fetch(28.61, 77.21)            # served from cache
        self.assertTrue(f.available)
        self.assertEqual(f.max_next_days, 41.2)
        self.assertEqual(m.call_count, 1)
        url = m.call_args[0][0]
        self.assertIn('timezone=Asia%2FKolkata', url)
        self.assertIn('temperature_2m_max', url)

    def test_failures_never_raise(self):
        cases = [urllib.error.URLError('down'), TimeoutError('slow'),
                 urllib.error.HTTPError('u', 500, 'err', {}, None)]
        for i, exc in enumerate(cases):
            with mock.patch('urllib.request.urlopen', side_effect=exc):
                f = weather.fetch(10 + i, 77)
            self.assertFalse(f.available, exc)
        for i, body in enumerate([b'not json', {'daily': {}}, {'daily': {'time': ['2026-05-20'],
                                                                         'temperature_2m_max': []}}]):
            with mock.patch('urllib.request.urlopen', return_value=self.fake(body)):
                self.assertFalse(weather.fetch(40 + i, 77).available)
        self.assertIn('location', weather.fetch(None, None).error)


@override_settings(DHARA_PRIORITY=CFG)
class TestPriorityWorkflowTests(DharaTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.tank.placement, self.tank.shade = 'rooftop', 'full_sun'
        self.tank.save()

    def record(self, user, value, unit='mg/L', kind='free_chlorine', method='dpd_strip', hours_ago=1):
        self.login(user)
        return self.client.post(self.url('observation_create', self.tank.pk), {
            'kind': kind, 'entered_value': value, 'entered_unit': unit, 'method': method,
            'measured_at': timezone.localtime(timezone.now() - timedelta(hours=hours_ago)).strftime('%Y-%m-%dT%H:%M')})

    def test_record_measurement_with_audit_and_conversion(self):
        r = self.record(self.tech, '86', unit='°F', kind='water_temp', method='thermometer')
        self.assertRedirects(r, self.url('tank_detail', self.tank.pk))
        obs = TankObservation.objects.get()
        self.assertEqual((obs.value, obs.entered_value, obs.entered_unit), (Decimal('30.00'), Decimal('86.00'), '°F'))
        self.assertEqual(obs.entered_by, self.tech)
        self.assertTrue(AuditEvent.objects.filter(action='observation.recorded', target_id=str(obs.pk)).exists())

    def test_invalid_measurement_shows_errors(self):
        r = self.record(self.tech, '15')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'outside the plausible range')
        self.assertEqual(TankObservation.objects.count(), 0)

    def test_outsider_cannot_record(self):
        self.client.force_login(self.outsider)
        r = self.client.post(self.url('observation_create', self.tank.pk), {})
        self.assertEqual(r.status_code, 403)

    def test_low_reading_creates_one_followup_and_no_duplicates(self):
        self.record(self.tech, '0.1')
        self.login(self.warden)
        r = self.client.get(self.url('test_priority'))
        self.assertContains(r, 'below the configured minimum')
        self.assertContains(r, 'Weather forecast unavailable')        # no location set: no network call
        tasks = FollowUpTask.objects.filter(kind=FollowUpTask.Kind.TEST_PRIORITY)
        self.assertEqual(tasks.count(), 1)
        task = tasks.get()
        self.assertEqual(task.assigned_to, self.tech)
        self.assertEqual(task.due_date, timezone.localdate())          # urgent: due today
        self.client.get(self.url('test_priority'))
        services.sync_priority_followups(self.company, services.compute_priorities(self.company)[1])
        self.assertEqual(tasks.count(), 1)                              # duplicates prevented
        services.resolve_followup(task, self.warden, 'Repeat strip read 0.4 mg/L; reviewed.')
        self.client.get(self.url('test_priority'))
        self.assertEqual(tasks.filter(status='open').count(), 1)        # still low -> new task after resolution

    def test_followup_audit_records_rule_reasons(self):
        self.login(self.warden)
        self.client.get(self.url('test_priority'))
        ev = AuditEvent.objects.get(action='followup.created', summary__contains='test priority')
        self.assertIn('No free-chlorine reading', ev.details['reasons'][0])

    def test_healthy_fresh_reading_needs_no_followup(self):
        self.record(self.tech, '0.6')
        self.login(self.warden)
        self.client.get(self.url('test_priority'))
        self.assertFalse(FollowUpTask.objects.filter(kind=FollowUpTask.Kind.TEST_PRIORITY).exists())

    def test_measurement_does_not_change_maintenance_or_lab_status(self):
        self.record(self.tech, '0.1')
        t = self.tank_dates()
        self.assertEqual(t.maintenance_status, 'none')
        self.assertTrue(t.report_missing)

    def test_forecast_with_location(self):
        self.company.latitude, self.company.longitude = Decimal('28.61'), Decimal('77.21')
        self.company.save()
        self.record(self.tech, '0.6', hours_ago=30)
        hot_fc = hot(42)
        with mock.patch.object(weather, 'fetch', return_value=hot_fc) as m:
            self.login(self.warden)
            r = self.client.get(self.url('test_priority'))
        m.assert_called_once_with(Decimal('28.61000'), Decimal('77.21000'))
        self.assertContains(r, 'This is air, not tank water')
        task = FollowUpTask.objects.get(kind=FollowUpTask.Kind.TEST_PRIORITY)
        self.assertIn('Repeat measurement', task.title)

    def test_pages_render(self):
        self.login(self.tech)
        for name in ('test_priority',):
            self.assertEqual(self.client.get(self.url(name)).status_code, 200)
        self.assertEqual(self.client.get(self.url('observation_create', self.tank.pk)).status_code, 200)
        self.assertContains(self.client.get(self.url('tank_detail', self.tank.pk)), 'not laboratory results')


# --- Thermal twin, sensors and interventions -----------------------------------------------
# All series below are SYNTHETIC TEST FIXTURES generated from known parameters, used only to check
# that the maths recovers what was put in. They are never shown in the app or used in the demo.

import random  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from . import twin as tw  # noqa: E402
from .models import SensorDevice, TankIntervention  # noqa: E402

TZ = ZoneInfo('Asia/Kolkata')
TRUE = (6.0, 0.12, -0.05)   # a (°C per kWh/m²), b (/h), c (°C/h)


def synthetic_weather(start, hours, air_base=30.0, air_amp=6.0, solar_peak=0.8):
    import math as m
    w = {}
    for k in range(hours):
        h = start + timedelta(hours=k)
        phase = (h.hour - 6) / 12 * m.pi
        g = max(0.0, m.sin(phase)) * solar_peak
        air = air_base + air_amp * m.sin((h.hour - 9) / 24 * 2 * m.pi)
        w[h] = (air, g)
    return w


def synthetic_readings(start, hours, weather, params=TRUE, noise=0.1, seed=1, shift=None):
    """Hourly readings from the model itself plus Gaussian noise; optional (from_hour, delta_a) change."""
    rnd = random.Random(seed)
    t, out = 28.0, []
    for k in range(hours):
        h = start + timedelta(hours=k)
        out.append((h + timedelta(minutes=10), t + rnd.gauss(0, noise)))
        p = params
        if shift and h >= shift[0]:
            p = (params[0] * shift[1], params[1], params[2])
        air, g = weather[h]
        t = tw.step(t, air, g, p)
    return out


START = datetime(2026, 5, 1, 0, 0, tzinfo=TZ)


class TwinMathTests(unittest.TestCase):
    def setUp(self):
        self.w = synthetic_weather(START, 24 * 10)

    def test_recovers_known_parameters_and_validates(self):
        r = synthetic_readings(START, 24 * 6, self.w)
        res = tw.calibrate(r, self.w, TZ)
        self.assertTrue(res.ok, res.message)
        for got, true in zip(res.params, TRUE):
            self.assertAlmostEqual(got, true, delta=abs(true) * 0.15 + 0.05)
        self.assertLess(res.holdout_mae, 0.5)
        self.assertEqual(res.n_train + res.n_holdout, 24 * 6 - 1)

    def test_insufficient_data(self):
        res = tw.calibrate(synthetic_readings(START, 60, self.w), self.w, TZ)
        self.assertEqual(res.status, 'insufficient')
        sparse = synthetic_readings(START, 24 * 6, self.w)[::2]     # every other hour: no consecutive steps
        self.assertEqual(tw.calibrate(sparse, self.w, TZ).status, 'insufficient')

    def test_noise_fails_validation_or_plausibility(self):
        rnd = random.Random(3)
        junk = [(START + timedelta(hours=k, minutes=5), 30 + rnd.uniform(-8, 8)) for k in range(24 * 6)]
        self.assertIn(tw.calibrate(junk, self.w, TZ).status, ('implausible', 'failed_validation'))

    def test_validation_limit_is_enforced(self):
        r = synthetic_readings(START, 24 * 6, self.w, noise=0.1)
        res = tw.calibrate(r, self.w, TZ, tw.TwinConfig(max_holdout_mae_c=0.001))
        self.assertEqual(res.status, 'failed_validation')
        self.assertIsNotNone(res.holdout_mae)

    def test_forecast_horizon_band_and_extrapolation(self):
        r = synthetic_readings(START, 24 * 6, self.w)
        hot_w = dict(self.w)
        last = START + timedelta(hours=24 * 6 - 1)
        for k in range(10, 20):           # make some future hours hotter than anything calibrated
            h = last + timedelta(hours=k)
            hot_w[h] = (60.0, hot_w[h][1])
        res = tw.forecast(tw.calibrate(r, self.w, TZ), r, hot_w, TZ, now=last + timedelta(minutes=30))
        self.assertTrue(res.ok)
        self.assertLessEqual(len(res.forecast), res.validated_horizon_h)
        self.assertTrue(all(lo < t < hi for _, t, lo, hi, _ in res.forecast))
        self.assertTrue(res.any_extrapolated)
        peak, when = res.forecast_max_in_range
        self.assertTrue(all(not ext for h, t, *_, ext in res.forecast if h == when))

    def test_stale_start_pauses_forecast(self):
        r = synthetic_readings(START, 24 * 6, self.w)
        res = tw.forecast(tw.calibrate(r, self.w, TZ), r, self.w, TZ, now=START + timedelta(days=8))
        self.assertEqual(res.status, 'stale')
        self.assertEqual(res.forecast, [])

    def test_solve_singular(self):
        self.assertIsNone(tw.solve3([[1, 2, 3], [2, 4, 6], [1, 1, 1]], [1, 2, 3]))

    def test_t_critical(self):
        self.assertEqual(tw.t_crit(1), 12.71)
        self.assertEqual(tw.t_crit(11), 2.18)    # conservative: uses df=12 entry
        self.assertEqual(tw.t_crit(500), 1.96)


class InterventionEffectTests(unittest.TestCase):
    def setUp(self):
        self.w = synthetic_weather(START, 24 * 12)
        self.applied = START + timedelta(days=7)

    def test_detects_known_cooling(self):
        r = synthetic_readings(START, 24 * 11, self.w, shift=(self.applied, 0.4), noise=0.05)  # 60% less solar gain
        ef = tw.intervention_effect(r, self.w, TZ, self.applied)
        self.assertEqual(ef.status, 'ok', ef.message)
        self.assertLess(ef.ci[1], 0)          # whole interval below zero: cooler than predicted
        self.assertGreater(ef.degree_hours_avoided, 0)

    def test_no_change_interval_includes_zero(self):
        r = synthetic_readings(START, 24 * 11, self.w, noise=0.05)
        ef = tw.intervention_effect(r, self.w, TZ, self.applied)
        self.assertEqual(ef.status, 'ok')
        self.assertLessEqual(ef.ci[0], 0.3)
        self.assertGreaterEqual(ef.ci[1], -0.3)

    def test_needs_days_after(self):
        r = synthetic_readings(START, 24 * 8, self.w)
        self.assertEqual(tw.intervention_effect(r, self.w, TZ, self.applied).status, 'insufficient')


class HourlyWeatherParseTests(unittest.TestCase):
    def test_solar_is_shifted_to_interval_start(self):
        payload = {'hourly': {'time': ['2026-05-01T11:00', '2026-05-01T12:00', '2026-05-01T13:00'],
                              'temperature_2m': [30, 31, 32], 'shortwave_radiation': [500, 700, 650]}}
        h = weather.parse_hourly(payload, TZ)
        self.assertTrue(h.available)
        k11 = datetime(2026, 5, 1, 11, tzinfo=TZ)
        self.assertEqual(h.rows[k11], (30.0, 0.7))      # 12:00 value = mean over 11:00-12:00
        self.assertNotIn(datetime(2026, 5, 1, 13, tzinfo=TZ), h.rows)  # no following hour
        self.assertFalse(weather.parse_hourly({'hourly': {}}, TZ).available)


class PriorityWithTwinTests(unittest.TestCase):
    def test_validated_forecast_raises_heat_only_when_ok(self):
        w = synthetic_weather(START, 24 * 8)
        r = synthetic_readings(START, 24 * 6, w)
        last = START + timedelta(hours=24 * 6 - 1)
        res = tw.forecast(tw.calibrate(r, w, TZ), r, w, TZ, now=last)
        cfg = dict(CFG, WATER_WARM_C=20.0)
        fresh = prio.Reading(0.6, NOW - timedelta(hours=30))
        p = prio.evaluate(tank_profile('rooftop', 'shaded'), fresh, None, NO_WX, cfg, NOW, water_forecast=res)
        self.assertEqual(p.action, 'repeat')
        self.assertIn('Thermal twin forecasts', ' '.join(p.context))
        res.status = 'failed_validation'
        p2 = prio.evaluate(tank_profile('rooftop', 'shaded'), fresh, None, NO_WX, cfg, NOW, water_forecast=res)
        self.assertFalse(p2.actionable)


class SensorIngestTests(DharaTestCase):
    def setUp(self):
        super().setUp()
        self.device, self.token = services.register_sensor(self.tank, self.warden, 'dhara-test-01')

    def post(self, body, token=None, header=True):
        kw = {'HTTP_AUTHORIZATION': f'Bearer {token or self.token}'} if header else {}
        return self.client.post(reverse('sensor_ingest'), data=json.dumps(body), content_type='application/json', **kw)

    def reading(self, minutes_ago, value):
        return {'measured_at': (timezone.now() - timedelta(minutes=minutes_ago)).isoformat(), 'water_temp_c': value}

    def test_token_stored_as_digest_only(self):
        self.assertNotEqual(self.device.token_sha256, self.token)
        self.assertEqual(len(self.device.token_sha256), 64)
        self.assertEqual(services.authenticate_device(self.token), self.device)
        self.assertIsNone(services.authenticate_device('wrong'))

    def test_ingest_validates_and_dedupes(self):
        dup = self.reading(5, 32.0)
        r = self.post({'readings': [self.reading(10, 31.5), dup, dict(dup),
                                    self.reading(1, 99), {'measured_at': '2026-05-01T10:00', 'water_temp_c': 30}]})
        data = r.json()
        self.assertEqual((data['created'], data['duplicates'], len(data['rejected'])), (2, 1, 2))
        obs = TankObservation.objects.filter(device=self.device)
        self.assertEqual(obs.count(), 2)
        self.assertTrue(all(o.entered_by_id is None and o.method == 'probe' for o in obs))
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)
        self.assertEqual(AuditEvent.objects.filter(action='sensor.ingested').count(), 1)

    def test_token_in_body_for_iot_rule_forwarding(self):
        r = self.post({'token': self.token, 'readings': [self.reading(3, 30.1)]}, header=False)
        self.assertEqual(r.json()['created'], 1)

    def test_auth_and_input_errors(self):
        self.assertEqual(self.post({'readings': [self.reading(1, 30)]}, token='nope').status_code, 401)
        self.device.active = False
        self.device.save()
        self.assertEqual(self.post({'readings': [self.reading(1, 30)]}).status_code, 401)
        self.device.active = True
        self.device.save()
        self.assertEqual(self.post({'readings': []}).status_code, 400)
        self.assertEqual(self.post({'readings': [self.reading(1, 30)] * 501}).status_code, 400)
        r = self.client.post(reverse('sensor_ingest'), data='{bad', content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get(reverse('sensor_ingest')).status_code, 405)

    def test_aws_iot_destination_confirmation(self):
        r = self.post({'confirmationToken': 'abc', 'enableUrl': 'https://iot.ap-south-1.amazonaws.com/x'}, header=False)
        self.assertEqual(r.json()['status'], 'confirmation logged')

    def test_register_sensor_page_shows_token_once(self):
        self.login(self.warden)
        r = self.client.post(self.url('sensor_create', self.tank.pk), {'thing_name': 'dhara-tank-a-02'})
        self.assertEqual(r['Cache-Control'], 'no-store')
        token = r.context['token']
        self.assertContains(r, token)
        self.assertNotContains(self.client.get(self.url('tank_detail', self.tank.pk)), token)
        self.login(self.tech)
        self.assertEqual(self.client.post(self.url('sensor_create', self.tank.pk),
                                          {'thing_name': 'x-1'}).status_code, 403)

    def test_db_requires_exactly_one_source(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            TankObservation.objects.create(equipment=self.tank, kind='water_temp', value=30, entered_value=30,
                                           entered_unit='°C', method='probe', measured_at=timezone.now(),
                                           entered_by=self.tech, device=self.device)


class ObservationPhotoAndInterventionTests(DharaTestCase):
    def test_photo_evidence_digest(self):
        self.login(self.tech)
        r = self.client.post(self.url('observation_create', self.tank.pk), {
            'kind': 'free_chlorine', 'entered_value': '0.4', 'entered_unit': 'mg/L', 'method': 'dpd_strip',
            'measured_at': timezone.localtime().strftime('%Y-%m-%dT%H:%M'), 'photo': png('strip.png')})
        self.assertEqual(r.status_code, 302)
        obs = TankObservation.objects.get()
        self.assertEqual(len(obs.photo_sha256), 64)
        with obs.photo.open('rb') as fh:
            import hashlib
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), obs.photo_sha256)

    def test_intervention_admin_only_and_audited(self):
        when = timezone.localtime().strftime('%Y-%m-%dT%H:%M')
        self.login(self.tech)
        self.assertEqual(self.client.post(self.url('intervention_create', self.tank.pk),
                                          {'kind': 'shade', 'applied_at': when}).status_code, 403)
        self.login(self.warden)
        self.client.post(self.url('intervention_create', self.tank.pk), {'kind': 'reflective_paint', 'applied_at': when})
        iv = TankIntervention.objects.get()
        self.assertTrue(AuditEvent.objects.filter(action='intervention.recorded', target_id=str(iv.pk)).exists())
        r = self.client.get(self.url('tank_detail', self.tank.pk))   # no location: twin explains, no crash
        self.assertEqual(r.status_code, 200)


# --- Redesign: server-side pieces of the new interface --------------------------------------

class InterfaceTests(DharaTestCase):
    def test_landing_links_live_demo_qr_only_when_demo_exists(self):
        r = self.client.get('/')
        self.assertContains(r, 'Water deserves more than a record.')
        self.assertIsNone(r.context['demo_qr_url'])
        from .management.commands.seed_demo import DEMO_INSTITUTION
        demo = Company.objects.create(name=DEMO_INSTITUTION)
        t = Equipment.objects.create(company=demo, tank_code='TANK-A', name='Demo', maintenance_interval_days=30)
        r = self.client.get('/')
        self.assertEqual(r.context['demo_qr_url'], reverse('public_tank_status', args=[t.public_token]))
        self.assertContains(r, 'Illustration of the drawing rules, not measured data')

    def test_series_chart_requires_two_points_and_draws_threshold(self):
        from .views import series_chart
        now = timezone.now()
        self.assertIsNone(series_chart([(now, 0.4)], 'mg/L', 0.2))
        c = series_chart([(now - timedelta(hours=5), 0.4), (now, 0.15)], 'mg/L', 0.2, 'configured minimum')
        self.assertEqual(len(c['pts']), 2)
        self.assertTrue(c['path'].startswith('M'))
        # threshold sits between the two readings on the y axis (SVG y grows downwards)
        ys = sorted(float(p['y']) for p in c['pts'])
        self.assertTrue(ys[0] < float(c['thr_y']) < ys[1])
        self.assertIn('0.15 mg/L', c['pts'][1]['label'])

    def test_tank_page_charts_and_empty_states(self):
        self.login(self.tech)
        r = self.client.get(self.url('tank_detail', self.tank.pk))
        self.assertContains(r, 'The chart appears after two temperature readings')
        for v, h in (('29.5', 3), ('31.0', 1)):
            services.record_observation(self.tank, self.tech, 'water_temp', Decimal(v), '°C', 'thermometer',
                                        timezone.now() - timedelta(hours=h))
        r = self.client.get(self.url('tank_detail', self.tank.pk))
        self.assertContains(r, 'class="s-water"')
        self.assertContains(r, 'Show tank-water temperature as a table')

    def test_form_fields_are_accessible(self):
        self.login(self.warden)
        r = self.client.post(self.url('tank_create'), {'tank_code': '', 'name': 'X', 'maintenance_interval_days': 30})
        html = r.content.decode()
        self.assertIn('aria-invalid="true"', html)
        self.assertIn('aria-describedby="id_tank_code_help id_tank_code_error"', html)
        self.assertIn('<span class="sr-only">(required)</span>', html)

    def test_no_cdn_runtime_and_assets_served(self):
        r = self.client.get('/')
        html = r.content.decode()
        self.assertNotIn('cdn.tailwindcss.com', html)
        self.assertNotIn('alpinejs', html)
        for path in ('css/tw.css', 'css/style.css', 'js/dhara.js', 'fonts/anek-latin-var.woff2'):
            from django.contrib.staticfiles import finders
            self.assertIsNotNone(finders.find(path), path)
