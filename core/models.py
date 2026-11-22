from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Category(models.TextChoices):
        TASK = 'TASK', 'Task Update'
        DELAY = 'DELAY', 'Task Delay'
        MATERIAL = 'MATERIAL', 'Material Request'
        ATTENDANCE = 'ATTENDANCE', 'Attendance'
        SITE_PROBLEM = 'SITE_PROBLEM', 'Site Problem'
        PROJECT = 'PROJECT', 'Project Assignment'
        GENERAL = 'GENERAL', 'General'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.GENERAL,
        db_index=True,
    )
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_notification'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.recipient} - {self.title}'


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=100, db_index=True)
    target_model = models.CharField(max_length=100, db_index=True)
    target_id = models.CharField(max_length=50, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'core_auditlog'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.created_at:%Y-%m-%d %H:%M}] {self.action} - {self.target_model}'
