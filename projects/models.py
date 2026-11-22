from decimal import Decimal
from django.conf import settings
from django.db import models


class Project(models.Model):
    class Status(models.TextChoices):
        PLANNING = 'PLANNING', 'Planning'
        ACTIVE = 'ACTIVE', 'Active'
        ON_HOLD = 'ON_HOLD', 'On Hold'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    project_code = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='managed_projects',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_projects',
    )
    start_date = models.DateField()
    expected_end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    working_days_mask = models.CharField(max_length=20, default='0,1,2,3,4,5')
    kiosk_device_name = models.CharField(max_length=100, blank=True)
    kiosk_token_hash = models.CharField(max_length=255, blank=True)
    kiosk_session_version = models.PositiveIntegerField(default=1)
    kiosk_is_active = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects_project'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expected_end_date__gte=models.F('start_date')),
                name='chk_project_dates_valid',
            ),
        ]

    def get_working_weekdays(self):
        return {int(d.strip()) for d in self.working_days_mask.split(',') if d.strip().isdigit()}

    def __str__(self):
        return f'{self.project_code} - {self.name}'


class ProjectHoliday(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='holidays',
    )
    holiday_date = models.DateField()
    title = models.CharField(max_length=150)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_holidays',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'projects_projectholiday'
        ordering = ['holiday_date']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'holiday_date'],
                name='uq_project_holiday_date',
            ),
        ]

    def __str__(self):
        return f'{self.project.project_code} - {self.holiday_date} ({self.title})'


class ProjectAssignment(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='assignments',
    )
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='project_assignments',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_workers',
    )
    assigned_date = models.DateField()
    deactivated_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    active_slot = models.GeneratedField(
        expression=models.Case(
            models.When(is_active=True, then=models.Value(1)),
            default=models.Value(None),
        ),
        output_field=models.PositiveSmallIntegerField(),
        db_persist=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects_projectassignment'
        ordering = ['-assigned_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'worker', 'active_slot'],
                name='uq_active_project_worker_slot',
            ),
        ]

    def __str__(self):
        state = 'Active' if self.is_active else 'Inactive'
        return f'{self.worker} -> {self.project.project_code} ({state})'


class Task(models.Model):
    class Unit(models.TextChoices):
        SQ_M = 'SQ_M', 'Square Metres (sq.m)'
        METRES = 'METRES', 'Metres (m)'
        PIECES = 'PIECES', 'Pieces (pcs)'
        HOURS = 'HOURS', 'Hours (hrs)'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        DELAYED = 'DELAYED', 'Delayed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='tasks',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_tasks',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_tasks',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=20, choices=Unit.choices)
    assigned_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    cached_approved_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    priority = models.CharField(
        max_length=15,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    deadline = models.DateField()
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'projects_task'
        ordering = ['deadline', '-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(assigned_quantity__gt=Decimal('0.00')),
                name='chk_task_assigned_qty_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(cached_approved_quantity__gte=Decimal('0.00')),
                name='chk_task_approved_qty_non_negative',
            ),
            models.CheckConstraint(
                condition=models.Q(cached_approved_quantity__lte=models.F('assigned_quantity')),
                name='chk_task_approved_lte_assigned',
            ),
        ]

    @property
    def remaining_quantity(self):
        return max(Decimal('0.00'), self.assigned_quantity - self.cached_approved_quantity)

    def __str__(self):
        return f'{self.title} ({self.project.project_code})'


class TaskProgressHistory(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Verification'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name='progress_entries',
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_progress',
    )
    work_date = models.DateField()
    quantity_submitted = models.DecimalField(max_digits=10, decimal_places=2)
    remarks = models.TextField(blank=True)
    proof_photo = models.ImageField(upload_to='task_proofs/%Y/%m/', null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reviewed_progress',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'projects_taskprogresshistory'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_submitted__gt=Decimal('0.00')),
                name='chk_progress_qty_positive',
            ),
        ]

    def __str__(self):
        return f'{self.task.title}: {self.quantity_submitted} {self.task.unit} ({self.status})'


class TaskQuantityAdjustment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name='quantity_adjustments',
    )
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='task_adjustments',
    )
    previous_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    new_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'projects_taskquantityadjustment'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(new_quantity__gt=Decimal('0.00')),
                name='chk_adjustment_new_qty_positive',
            ),
        ]

    def __str__(self):
        return f'{self.task.title}: {self.previous_quantity} -> {self.new_quantity}'


class TaskDelayReport(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name='delay_reports',
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reported_delays',
    )
    reason = models.TextField()
    expected_completion_date = models.DateField()
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='acknowledged_delays',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'projects_taskdelayreport'
        ordering = ['-created_at']

    def __str__(self):
        return f'Delay: {self.task.title} (Expected: {self.expected_completion_date})'
