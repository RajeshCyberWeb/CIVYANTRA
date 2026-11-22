from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, SupervisorProfile, WorkerProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active', 'is_deleted')
    list_filter = ('role', 'is_active', 'is_deleted')
    fieldsets = UserAdmin.fieldsets + (
        ('CIVYANTRA Role & Status', {'fields': ('role', 'phone_number', 'is_deleted', 'deleted_at', 'created_by')}),
    )


admin.site.register(SupervisorProfile)
admin.site.register(WorkerProfile)

