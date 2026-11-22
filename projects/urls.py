from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('create/', views.project_create, name='project_create'),
    path('<int:project_id>/', views.project_detail, name='project_detail'),
    path('<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('<int:project_id>/assign/', views.assign_worker, name='assign_worker'),
    path('<int:project_id>/assignments/<int:assignment_id>/deactivate/', views.deactivate_assignment, name='deactivate_assignment'),
    path('<int:project_id>/holidays/add/', views.add_holiday, name='add_holiday'),
    path('<int:project_id>/holidays/<int:holiday_id>/delete/', views.delete_holiday, name='delete_holiday'),
    path('tasks/', views.task_list, name='task_list'),
    path('<int:project_id>/tasks/create/', views.task_create, name='task_create'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/progress/', views.submit_progress, name='submit_progress'),
    path('tasks/<int:task_id>/done/', views.mark_task_done, name='mark_task_done'),
    path('tasks/<int:task_id>/progress/<int:entry_id>/review/', views.review_progress, name='review_progress'),
    path('tasks/<int:task_id>/adjust/', views.adjust_quantity, name='adjust_quantity'),
    path('tasks/<int:task_id>/delay/', views.report_delay, name='report_delay'),
    path('tasks/<int:task_id>/delay/<int:delay_id>/acknowledge/', views.acknowledge_delay, name='acknowledge_delay'),
]
