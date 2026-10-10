# qr_app/models.py
"""
Data model for DHARA. Adapted from the QRInvent starter:
  Company/Membership/User/Invitation  -> institution, staff, roles (role moved onto Membership)
  Equipment                          -> water tank
  ServiceRecord                      -> maintenance event (claimed work date + server submission time + review)
  ServiceRecordPhoto                 -> Evidence (before/after/document, SHA-256 digest)
New for DHARA: WaterQualityReport, FollowUpTask, AuditEvent.
"""
import secrets
import uuid
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Max, Q
from django.utils import timezone
from slugify import slugify

DUE_SOON_DAYS = 14

# Top-level URL segments that a company slug must never shadow (see project_qr/urls.py).
RESERVED_SLUGS = {
    'register', 'login', 'logout', 'invitations', 'select-company', 'qr', 'healthz',
    'yookassa', 'super-secret-control-panel', 'static', 'media', 'admin',
}


class User(AbstractUser):
    first_name = None
    last_name = None


class SubscriptionPlan(models.Model):
    """Upstream QRInvent billing. Only used when settings.BILLING_ENABLED is on."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_annually = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_equipment = models.PositiveIntegerField(default=10)
    max_users = models.PositiveIntegerField(default=3)

    def __str__(self):
        return self.name


class Company(models.Model):
    """An institution: hostel, school, campus."""
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    subscription_expires_on = models.DateField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    yookassa_payment_method_id = models.CharField(max_length=255, null=True, blank=True)
    members = models.ManyToManyField(User, through='Membership', related_name='companies')

    class Meta:
        verbose_name_plural = 'companies'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'institution'
            slug, counter = base_slug, 1
            while slug in RESERVED_SLUGS or Company.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def has_active_subscription(self):
        return (
            self.subscription_plan is not None and
            self.subscription_expires_on is not None and
            self.subscription_expires_on >= timezone.localdate()
        )

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    ADMIN = 'admin', 'Warden / Administrator'
    TECHNICIAN = 'technician', 'Technician / Service provider'


class Membership(models.Model):
    """A user's role is per institution, never global."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.TECHNICIAN)
    date_joined = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'company')

    @property
    def is_admin(self):
        return self.role == Role.ADMIN


class Invitation(models.Model):
    email = models.EmailField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.TECHNICIAN)
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invitation for {self.email} to {self.company.name}"


def new_public_token():
    return secrets.token_urlsafe(18)


class TankQuerySet(models.QuerySet):
    def with_dates(self):
        """Annotate the dates every status calculation needs, in one query."""
        return self.annotate(
            last_accepted_date=Max('records__work_date', filter=Q(records__review_status='accepted')),
            last_recorded_date=Max('records__work_date'),
            last_sample_date=Max('reports__sample_date'),
        )


class Equipment(models.Model):
    """A water-storage tank."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='equipment')
    tank_code = models.CharField(
        'tank ID', max_length=32,
        validators=[RegexValidator(r'^[A-Za-z0-9][A-Za-z0-9_-]*$', 'Use letters, numbers, - or _.')],
        help_text='Your institution\'s identifier, e.g. HB-OHT-01.')
    name = models.CharField('tank label', max_length=255)
    building = models.CharField('building / block', max_length=120, blank=True)
    location = models.CharField('location description', max_length=255, blank=True,
                                help_text='Internal only. Not shown on the public QR page.')
    capacity_litres = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10_000_000)])
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='responsible_tanks', verbose_name='responsible person')
    maintenance_interval_days = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text='Your institution\'s configured cleaning interval. DHARA does not assume a legal standard.')
    report_interval_days = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text='Optional: how often a water-quality report is expected. Leave empty for no expectation.')
    public_token = models.CharField(max_length=32, unique=True, default=new_public_token, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TankQuerySet.as_manager()

    class Meta:
        verbose_name = 'tank'
        ordering = ['tank_code']
        constraints = [
            models.UniqueConstraint(fields=['company', 'tank_code'], name='unique_tank_code_per_company'),
        ]

    def __str__(self):
        return f"{self.tank_code} · {self.name}"

    # --- Due-date engine. Requires TankQuerySet.with_dates() annotations. ---
    @property
    def next_due_date(self):
        """Last *accepted* maintenance + configured interval. None if nothing accepted yet."""
        if self.last_accepted_date:
            return self.last_accepted_date + timedelta(days=self.maintenance_interval_days)
        return None

    @property
    def maintenance_status(self):
        """'none' (no accepted maintenance on record), 'overdue', 'due_soon' or 'ok'."""
        due = self.next_due_date
        if due is None:
            return 'none'
        today = timezone.localdate()
        if due < today:
            return 'overdue'
        if due <= today + timedelta(days=DUE_SOON_DAYS):
            return 'due_soon'
        return 'ok'

    @property
    def needs_maintenance(self):
        return self.maintenance_status in ('none', 'overdue')

    @property
    def next_report_due_date(self):
        if self.report_interval_days and self.last_sample_date:
            return self.last_sample_date + timedelta(days=self.report_interval_days)
        return None

    @property
    def report_missing(self):
        """True when a report is expected by policy but none is current. A documentation gap,
        never an inference about water safety."""
        if not self.report_interval_days:
            return False
        due = self.next_report_due_date
        return due is None or due < timezone.localdate()


class EventType(models.TextChoices):
    CLEANING = 'cleaning', 'Cleaning'
    DISINFECTION = 'disinfection', 'Disinfection'
    INSPECTION = 'inspection', 'Inspection'
    REPAIR = 'repair', 'Repair'
    OTHER = 'other', 'Other'


class ReviewStatus(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    CHANGES_REQUESTED = 'changes_requested', 'Changes requested'


class ServiceRecord(models.Model):
    """A maintenance event. `work_date` is claimed by the submitter; `created_at` is set by the server."""
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='records', verbose_name='tank')
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name='submitted_records',
                               verbose_name='submitted by')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='submitted at')
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.CLEANING)
    work_date = models.DateField('claimed work date')
    provider_name = models.CharField('technician / provider', max_length=160, blank=True)
    notes = models.TextField('maintenance notes', blank=True)
    amends = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True,
                               related_name='amendments', help_text='Earlier event this one corrects.')

    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name='reviewed_records')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'maintenance event'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['review_status', 'created_at'])]
        constraints = [
            models.CheckConstraint(
                name='review_decision_has_reviewer',
                condition=Q(review_status='pending') | Q(reviewed_by__isnull=False, reviewed_at__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} on {self.work_date} ({self.equipment.tank_code})"

    @property
    def evidence_status(self):
        return 'attached' if self.photos.exists() else 'missing'


def evidence_upload_path(instance, filename):
    """Generated object key; the uploaded filename is never trusted as a path."""
    return f"evidence/{instance.record.equipment.company_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class EvidenceKind(models.TextChoices):
    BEFORE = 'before', 'Before photo'
    AFTER = 'after', 'After photo'
    DOCUMENT = 'document', 'Supporting document'


class ServiceRecordPhoto(models.Model):
    """Evidence attached to a maintenance event."""
    record = models.ForeignKey(ServiceRecord, on_delete=models.PROTECT, related_name='photos')
    kind = models.CharField(max_length=10, choices=EvidenceKind.choices, default=EvidenceKind.AFTER)
    file = models.FileField(upload_to=evidence_upload_path, max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, related_name='+')
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'evidence file'

    def __str__(self):
        return f"{self.get_kind_display()} for event #{self.record_id}"


def report_upload_path(instance, filename):
    return f"reports/{instance.equipment.company_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class WaterQualityReport(models.Model):
    """A laboratory report, kept separate from maintenance and its review."""
    class Review(models.TextChoices):
        UNREVIEWED = 'unreviewed', 'Uploaded, not yet reviewed'
        REVIEWED = 'reviewed', 'Reviewed by institution'

    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='reports', verbose_name='tank')
    lab_name = models.CharField('laboratory', max_length=200)
    sample_date = models.DateField()
    report_date = models.DateField(null=True, blank=True)
    parameters = models.CharField('parameters tested', max_length=500, blank=True,
                                  help_text='As listed on the report, e.g. pH, TDS, total coliform, E. coli.')
    results_summary = models.TextField('results as reported', blank=True,
                                       help_text='Copy what the report states. Do not interpret.')
    notes = models.TextField('provenance / notes', blank=True,
                             help_text='Who collected the sample, where it was drawn from, report reference.')
    file = models.FileField(upload_to=report_upload_path, max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(max_length=12, choices=Review.choices, default=Review.UNREVIEWED)
    reviewed_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sample_date', '-uploaded_at']
        constraints = [
            models.CheckConstraint(name='report_date_after_sample',
                                   condition=Q(report_date__isnull=True) | Q(report_date__gte=models.F('sample_date'))),
        ]

    def __str__(self):
        return f"{self.lab_name} sample {self.sample_date} ({self.equipment.tank_code})"


class FollowUpTask(models.Model):
    class Kind(models.TextChoices):
        OVERDUE_MAINTENANCE = 'overdue_maintenance', 'Maintenance overdue'
        MISSING_REPORT = 'missing_report', 'Water-quality report missing'
        EVIDENCE_REQUESTED = 'evidence_requested', 'Reviewer requested changes'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved'

    AUTO_KINDS = (Kind.OVERDUE_MAINTENANCE, Kind.MISSING_REPORT)

    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='followups', verbose_name='tank')
    kind = models.CharField(max_length=24, choices=Kind.choices)
    title = models.CharField(max_length=200)
    due_date = models.DateField()
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='followups')
    related_event = models.ForeignKey(ServiceRecord, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name='followups')
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+',
                                   help_text='Empty when created by the configured schedule rule.')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['status', 'due_date']
        constraints = [
            models.UniqueConstraint(fields=['equipment', 'kind'],
                                    condition=Q(status='open', kind__in=['overdue_maintenance', 'missing_report']),
                                    name='one_open_rule_task_per_tank_kind'),
            models.CheckConstraint(name='resolved_task_has_resolver',
                                   condition=Q(status='open') | Q(resolved_by__isnull=False, resolved_at__isnull=False)),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        return self.status == self.Status.OPEN and self.due_date < timezone.localdate()


class AuditEvent(models.Model):
    """Append-only by convention (no edit/delete UI). This is an ordinary DB table, not a tamper-proof log."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='audit_events')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=40)
    summary = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.summary


class Payment(models.Model):
    """Upstream QRInvent YooKassa payment record (billing mode only)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    yookassa_payment_id = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payments')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Payment {self.id} {self.amount} for {self.company.name}"
