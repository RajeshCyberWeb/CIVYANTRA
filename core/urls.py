from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/supervisor/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('dashboard/worker/', views.worker_dashboard, name='worker_dashboard'),
    path('dashboard/live-stats/', views.dashboard_live_stats, name='dashboard_live_stats'),
]
