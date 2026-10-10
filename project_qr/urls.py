# project_qr/urls.py
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django_otp.admin import OTPAdminSite

from qr_app import views

admin.site.__class__ = OTPAdminSite

# Any first segment used here must be listed in qr_app.models.RESERVED_SLUGS.
urlpatterns = [
    path('super-secret-control-panel/', admin.site.urls),
    path('healthz/', views.healthz, name='healthz'),
    path('api/sensors/ingest/', views.sensor_ingest, name='sensor_ingest'),
    path('yookassa/webhook/', views.yookassa_webhook_view, name='yookassa_webhook_global'),
    path('', views.LandingPageView.as_view(), name='landing_page'),
    path('qr/<str:token>/', views.public_tank_status, name='public_tank_status'),
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html',
                                                redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('invitations/accept/<str:token>/', views.accept_invitation_view, name='accept_invitation'),
    path('select-company/', views.select_company_view, name='select_company'),
    path('<slug:company_slug>/', include('qr_app.urls', namespace='qr_app')),
]
handler500 = 'qr_app.views.custom_server_error_view'
# No static()/media routes: evidence is private and only served through access-checked views.
