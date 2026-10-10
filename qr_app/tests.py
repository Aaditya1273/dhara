# qr_app/tests.py
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
