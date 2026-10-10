# qr_app/admin.py
from django.contrib import admin

from .models import (
    AuditEvent, Company, Equipment, FollowUpTask, Invitation, Membership, ServiceRecord, ServiceRecordPhoto,
    SubscriptionPlan, User, WaterQualityReport,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_staff', 'date_joined')
    search_fields = ('email',)


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ('user',)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    readonly_fields = ('slug',)
    inlines = (MembershipInline,)


@admin.register(Equipment)
class TankAdmin(admin.ModelAdmin):
    list_display = ('tank_code', 'name', 'company', 'building', 'maintenance_interval_days')
    list_filter = ('company',)
    search_fields = ('tank_code', 'name')
    readonly_fields = ('public_token', 'created_at', 'updated_at')


class EvidenceInline(admin.TabularInline):
    model = ServiceRecordPhoto
    extra = 0
    readonly_fields = ('kind', 'file', 'original_name', 'sha256', 'uploaded_by', 'uploaded_at')
    can_delete = False


@admin.register(ServiceRecord)
class MaintenanceEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'equipment', 'event_type', 'work_date', 'author', 'review_status', 'created_at')
    list_filter = ('review_status', 'event_type')
    readonly_fields = ('created_at',)
    inlines = (EvidenceInline,)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'company', 'actor', 'action', 'summary')
    list_filter = ('action',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register([SubscriptionPlan, Invitation, WaterQualityReport, FollowUpTask])
