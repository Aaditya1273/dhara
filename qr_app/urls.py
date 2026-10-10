# qr_app/urls.py  (all routes are scoped to /<company_slug>/)
from django.urls import path

from . import views

app_name = 'qr_app'

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),

    path('tanks/', views.TankListView.as_view(), name='tank_list'),
    path('tanks/new/', views.TankFormView.as_view(), name='tank_create'),
    path('tanks/<int:pk>/', views.TankDetailView.as_view(), name='tank_detail'),
    path('tanks/<int:pk>/edit/', views.TankFormView.as_view(), name='tank_update'),
    path('tanks/<int:pk>/qr.png', views.TankQRView.as_view(), name='tank_qr'),
    path('tanks/<int:pk>/maintenance/new/', views.EventCreateView.as_view(), name='event_create'),
    path('tanks/<int:pk>/reports/new/', views.ReportCreateView.as_view(), name='report_create'),

    path('maintenance/<int:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    path('maintenance/<int:pk>/review/', views.EventReviewView.as_view(), name='event_review'),
    path('maintenance/<int:pk>/respond/', views.EventRespondView.as_view(), name='event_respond'),
    path('review/', views.ReviewQueueView.as_view(), name='review_queue'),

    path('reports/', views.ReportListView.as_view(), name='report_list'),
    path('reports/<int:pk>/reviewed/', views.ReportReviewView.as_view(), name='report_review'),

    path('follow-ups/', views.FollowUpListView.as_view(), name='followup_list'),
    path('follow-ups/<int:pk>/assign/', views.FollowUpAssignView.as_view(), name='followup_assign'),
    path('follow-ups/<int:pk>/resolve/', views.FollowUpResolveView.as_view(), name='followup_resolve'),

    path('files/evidence/<int:pk>/', views.EvidenceFileView.as_view(), name='evidence_file'),
    path('files/evidence/<int:pk>/verify/', views.EvidenceVerifyView.as_view(), name='evidence_verify'),
    path('files/report/<int:pk>/', views.ReportFileView.as_view(), name='report_file'),

    path('activity/', views.ActivityHistoryView.as_view(), name='activity_history'),
    path('team/', views.TeamManageView.as_view(), name='manage_team'),
    path('team/member/<int:pk>/remove/', views.MemberRemoveView.as_view(), name='member_delete'),
    path('team/invitation/<int:pk>/revoke/', views.InvitationRevokeView.as_view(), name='invitation_revoke'),
    path('settings/', views.CompanySettingsView.as_view(), name='company_settings'),

    # Upstream QRInvent billing; every view 403s unless BILLING_ENABLED=True.
    path('subscription/', views.SubscriptionManageView.as_view(), name='subscription_manage'),
    path('subscription/select/', views.SubscriptionSelectView.as_view(), name='subscription_select'),
    path('subscription/activate/', views.SubscriptionActivateView.as_view(), name='subscription_activate'),
    path('subscription/toggle-renew/', views.ToggleAutoRenewView.as_view(), name='subscription_toggle_renew'),
    path('subscription/cancel/', views.CancelSubscriptionView.as_view(), name='subscription_cancel'),
    path('subscription/result/', views.PaymentResultView.as_view(), name='payment_result'),
]
