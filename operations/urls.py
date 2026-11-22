from django.urls import path
from . import views

app_name = 'operations'

urlpatterns = [
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/<int:pk>/checkout/', views.attendance_checkout, name='attendance_checkout'),
    path('materials/', views.material_dashboard, name='material_dashboard'),
    path('materials/<int:pk>/review/', views.review_material_request, name='review_material_request'),
    path('problems/', views.problem_list, name='problem_list'),
    path('problems/<int:pk>/resolve/', views.resolve_problem, name='resolve_problem'),
    path('reports/', views.operations_report, name='operations_report'),
]
