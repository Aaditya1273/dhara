# qr_app/templatetags/dhara.py
from django import template
from django.utils.html import format_html

register = template.Library()

BADGES = {
    'maintenance': {
        'none': ('No accepted maintenance on record', 'bad'),
        'overdue': ('Maintenance overdue', 'bad'),
        'due_soon': ('Due soon', 'warn'),
        'ok': ('Schedule up to date', 'good'),
    },
    'review': {
        'pending': ('Pending review', 'info'),
        'accepted': ('Accepted', 'good'),
        'rejected': ('Rejected', 'bad'),
        'changes_requested': ('Changes requested', 'warn'),
    },
    'evidence': {
        'attached': ('Evidence attached', 'good'),
        'missing': ('No evidence attached', 'warn'),
    },
    'report': {
        'unreviewed': ('Uploaded, not yet reviewed', 'info'),
        'reviewed': ('Reviewed by institution', 'good'),
    },
    'task': {
        'open': ('Open', 'warn'),
        'resolved': ('Resolved', 'good'),
    },
}


@register.simple_tag
def badge(kind, value):
    label, tone = BADGES[kind].get(value, (value, 'neutral'))
    return format_html('<span class="badge badge-{}">{}</span>', tone, label)
