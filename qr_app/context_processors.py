# qr_app/context_processors.py
from django.conf import settings

from .models import Membership


def current_company(request):
    ctx = {'billing_enabled': settings.BILLING_ENABLED}
    match = request.resolver_match
    if not (match and 'company_slug' in match.kwargs and request.user.is_authenticated):
        return ctx
    membership = getattr(request, 'membership', None) or Membership.objects.filter(
        user=request.user, company__slug=match.kwargs['company_slug']).select_related('company').first()
    if membership:
        ctx.update(company=membership.company, membership=membership)
    return ctx
