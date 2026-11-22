from django.urls import path
from . import views, portal_views

app_name = 'accounts'

urlpatterns = [
    path('login/', portal_views.role_login_view, {'portal_role': 'ALL'}, name='login'),
    path('login/admin/', portal_views.role_login_view, {'portal_role': 'ADMIN'}, name='admin_login'),
    path('login/supervisor/', portal_views.role_login_view, {'portal_role': 'SUPERVISOR'}, name='supervisor_login'),
    path('login/worker/', portal_views.role_login_view, {'portal_role': 'WORKER'}, name='worker_login'),
    path('logout/', views.logout_view, name='logout'),
    path('users/', views.user_list_view, name='user_list'),
    path('users/create-supervisor/', views.create_supervisor_view, name='create_supervisor'),
    path('users/create-worker/', views.create_worker_view, name='create_worker'),
    path('users/<int:user_id>/edit/', views.edit_user_view, name='edit_user'),
    path('users/<int:user_id>/toggle-status/', views.toggle_user_status_view, name='toggle_user_status'),
    path('users/<int:user_id>/reset-pin/', views.reset_worker_pin_view, name='reset_worker_pin'),
    path('users/<int:user_id>/delete/', views.delete_user_view, name='delete_user'),
]
