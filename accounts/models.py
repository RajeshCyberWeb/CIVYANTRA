from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        SUPERVISOR = 'SUPERVISOR', 'Site Supervisor'
        WORKER = 'WORKER', 'Construction Worker'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.WORKER,
        db_index=True,
    )
    phone_number = models.CharField(max_length=20, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='created_users',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_user'
        ordering = ['-created_at']

    def get_display_name(self):
        full_name = self.get_full_name().strip()
        return full_name if full_name else self.username

    def __str__(self):
        return f"{self.get_display_name()} ({self.get_role_display()})"


class SupervisorProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name='supervisor_profile',
    )
    supervisor_code = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_supervisorprofile'

    def __str__(self):
        return f"{self.supervisor_code} - {self.user.get_display_name()}"


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        related_name='worker_profile',
    )
    worker_code = models.CharField(max_length=20, unique=True, db_index=True)
    trade_skill = models.CharField(max_length=100, blank=True)
    attendance_pin_hash = models.CharField(max_length=255)
    failed_pin_attempts = models.PositiveSmallIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)
    pin_updated_at = models.DateTimeField(auto_now_add=True)

    # Reserved fields for future physical ID scanner / biometric integration
    rfid_card_uid = models.CharField(max_length=100, unique=True, null=True, blank=True)
    biometric_template_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_workerprofile'

    def __str__(self):
        return f"{self.worker_code} - {self.user.get_display_name()}"