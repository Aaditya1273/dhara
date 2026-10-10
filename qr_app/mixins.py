# qr_app/mixins.py
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from .models import Company, Membership


class CompanyRequiredMixin:
    """Resolves `company_slug`, requires membership, sets self.company and self.membership.
    Every company-scoped queryset must filter on self.company."""
    company = None
    membership = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        self.company = get_object_or_404(Company, slug=kwargs.get('company_slug'))
        self.membership = Membership.objects.filter(user=request.user, company=self.company).first()
        if not self.membership:
            raise PermissionDenied('You are not a member of this institution.')
        request.membership = self.membership
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin:
    """Use after CompanyRequiredMixin. Role is checked per institution."""

    def dispatch(self, request, *args, **kwargs):
        if not self.membership.is_admin:
            raise PermissionDenied('Only a warden/administrator can do this.')
        return super().dispatch(request, *args, **kwargs)


class ActiveSubscriptionRequiredMixin:
    """Upstream billing gate. A no-op unless settings.BILLING_ENABLED is on."""

    def dispatch(self, request, *args, **kwargs):
        if settings.BILLING_ENABLED and not self.company.has_active_subscription:
            messages.warning(request, 'Your subscription is inactive. Choose a plan to continue.')
            return redirect(reverse('qr_app:subscription_select', kwargs={'company_slug': self.company.slug}))
        return super().dispatch(request, *args, **kwargs)


class BillingEnabledMixin:
    def dispatch(self, request, *args, **kwargs):
        if not settings.BILLING_ENABLED:
            raise PermissionDenied('Billing is disabled on this deployment.')
        return super().dispatch(request, *args, **kwargs)
