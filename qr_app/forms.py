# qr_app/forms.py
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import services
from .models import (
    Company, Equipment, Invitation, ReviewStatus, ServiceRecord, User, WaterQualityReport,
)

DATE = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


class PasswordPairMixin:
    def clean(self):
        cd = super().clean()
        if cd.get('password') and cd.get('password') != cd.get('password2'):
            self.add_error('password2', 'Passwords do not match.')
        elif cd.get('password'):
            try:
                validate_password(cd['password'])
            except ValidationError as e:
                self.add_error('password', e)
        return cd


class UserRegistrationForm(PasswordPairMixin, forms.ModelForm):
    company_name = forms.CharField(max_length=100, label='Institution name')
    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm password')

    class Meta:
        model = User
        fields = ('email',)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email


class InvitedUserRegistrationForm(PasswordPairMixin, forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label='Choose a password')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirm password')


class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ['email', 'role']
        labels = {'email': 'Email address'}


class CompanySettingsForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name']
        labels = {'name': 'Institution name'}


def member_choices(company):
    return User.objects.filter(membership__company=company).order_by('email')


class TankForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = ['tank_code', 'name', 'building', 'location', 'capacity_litres', 'responsible',
                  'maintenance_interval_days', 'report_interval_days']

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields['responsible'].queryset = member_choices(company)
        self.fields['responsible'].label_from_instance = lambda u: u.email

    def clean_tank_code(self):
        code = self.cleaned_data['tank_code'].strip().upper()
        clash = Equipment.objects.filter(company=self.company, tank_code__iexact=code).exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError('Another tank in this institution already uses this ID.')
        return code


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, max_files=3, **kwargs):
        self.max_files = max_files
        kwargs.setdefault('widget', MultipleFileInput())
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = [f for f in (data if isinstance(data, (list, tuple)) else [data]) if f]
        if len(files) > self.max_files:
            raise ValidationError(f'Attach at most {self.max_files} files here.')
        return [super(MultipleFileField, self).clean(f, initial) for f in files]


class EvidenceFieldsMixin:
    """Validates each uploaded file's type, size and real content at the form layer."""
    evidence_fields = {'before_photos': ('before', services.IMAGE_TYPES),
                       'after_photos': ('after', services.IMAGE_TYPES),
                       'documents': ('document', {**services.IMAGE_TYPES, **services.PDF_TYPES})}

    def _clean_files(self, name):
        files = self.cleaned_data.get(name) or []
        for f in files:
            services.validate_upload(f, self.evidence_fields[name][1])
        return files

    def clean_before_photos(self):
        return self._clean_files('before_photos')

    def clean_after_photos(self):
        return self._clean_files('after_photos')

    def clean_documents(self):
        return self._clean_files('documents')

    def evidence(self):
        return [(self.evidence_fields[name][0], f)
                for name in self.evidence_fields if name in self.fields
                for f in self.cleaned_data.get(name, [])]


class MaintenanceEventForm(EvidenceFieldsMixin, forms.ModelForm):
    before_photos = MultipleFileField(label='Before photos', help_text='JPG or PNG, up to 3, 8 MB each.')
    after_photos = MultipleFileField(label='After photos', help_text='JPG or PNG, up to 3, 8 MB each.')
    documents = MultipleFileField(label='Supporting documents', help_text='Invoice, checklist: PDF/JPG/PNG.')

    class Meta:
        model = ServiceRecord
        fields = ['event_type', 'work_date', 'provider_name', 'notes']
        widgets = {'work_date': DATE, 'notes': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'work_date': 'When the work was done. Your submission time is recorded separately.'}

    def clean_work_date(self):
        d = self.cleaned_data['work_date']
        if d > timezone.localdate():
            raise ValidationError('The work date cannot be in the future.')
        return d


class RespondForm(EvidenceFieldsMixin, forms.Form):
    note = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label='Response to reviewer')
    after_photos = MultipleFileField(label='Additional photos')
    documents = MultipleFileField(label='Additional documents')


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[
        (ReviewStatus.ACCEPTED, 'Accept'),
        (ReviewStatus.CHANGES_REQUESTED, 'Request more evidence'),
        (ReviewStatus.REJECTED, 'Reject'),
    ], widget=forms.RadioSelect)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False, label='Review note',
                            help_text='Required when rejecting or requesting more evidence.')


class WaterQualityReportForm(forms.ModelForm):
    class Meta:
        model = WaterQualityReport
        fields = ['lab_name', 'sample_date', 'report_date', 'parameters', 'results_summary', 'notes', 'file']
        widgets = {'sample_date': DATE, 'report_date': DATE,
                   'results_summary': forms.Textarea(attrs={'rows': 3}), 'notes': forms.Textarea(attrs={'rows': 2})}
        labels = {'file': 'Original report (PDF, JPG or PNG)'}

    def clean_file(self):
        f = self.cleaned_data['file']
        services.validate_upload(f, {**services.PDF_TYPES, **services.IMAGE_TYPES})
        return f

    def clean(self):
        cd = super().clean()
        sample, report = cd.get('sample_date'), cd.get('report_date')
        if sample and sample > timezone.localdate():
            self.add_error('sample_date', 'The sample date cannot be in the future.')
        if sample and report and report < sample:
            self.add_error('report_date', 'The report date cannot be before the sample date.')
        return cd


class FollowUpAssignForm(forms.Form):
    assigned_to = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label='Assign to')
    due_date = forms.DateField(widget=DATE)

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = member_choices(company)
        self.fields['assigned_to'].label_from_instance = lambda u: u.email


class ResolveForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), label='Resolution notes')

