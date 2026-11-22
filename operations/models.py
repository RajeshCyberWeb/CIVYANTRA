from decimal import Decimal
from django.conf import settings
from django.db import models
from projects.models import Project


class Material(models.Model):
    material_code = models.CharField(max_length=30, unique=True, db_index=True)
    name = models.CharField(max_length=150, unique=True)
    category = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_materials',
    )

    class Meta:
        db_table = 'operations_material'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.material_code:
            last = Material.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.material_code = f"MAT-{next_id:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.material_code} - {self.name} ({self.unit})"


class ProjectMaterialInventory(models.Model):
    available_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='project_inventories',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='material_inventories',
    )

    class Meta:
        db_table = 'operations_projectmaterialinventory'
        ordering = ['project', 'material__name']
        constraints = [
            models.UniqueConstraint(fields=('project', 'material'), name='uq_project_material_inventory'),
            models.CheckConstraint(condition=models.Q(available_quantity__gte=Decimal('0.00')), name='chk_inventory_non_negative'),
            models.CheckConstraint(condition=models.Q(reorder_level__gte=Decimal('0.00')), name='chk_reorder_level_non_negative'),
        ]

    def __str__(self):
        return f"{self.project.project_code} - {self.material.name}: {self.available_quantity} {self.material.unit}"


class MaterialRequest(models.Model):
    class ProblemType(models.TextChoices):
        FINISHED = 'FINISHED', 'Material Finished'
        DAMAGED = 'DAMAGED', 'Material Damaged'
        INSUFFICIENT = 'INSUFFICIENT', 'Material Insufficient'
        MISSING = 'MISSING', 'Material Missing'

    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class OrderStatus(models.TextChoices):
        NOT_ORDERED = 'NOT_ORDERED', 'Not Ordered'
        ORDERED = 'ORDERED', 'Ordered'
        IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
        PARTIALLY_DELIVERED = 'PARTIALLY_DELIVERED', 'Partially Delivered'
        DELIVERED = 'DELIVERED', 'Delivered'

    request_code = models.CharField(max_length=30, unique=True, db_index=True)
    problem_type = models.CharField(max_length=20, choices=ProblemType.choices)
    required_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    total_received_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    description = models.TextField()
    photo = models.ImageField(upload_to='material_requests/%Y/%m/')
    approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING, db_index=True)
    order_status = models.CharField(max_length=25, choices=OrderStatus.choices, default=OrderStatus.NOT_ORDERED, db_index=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='material_requests',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='material_requests',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='submitted_material_requests',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='reviewed_material_requests',
    )

    class Meta:
        db_table = 'operations_materialrequest'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(total_received_quantity__gte=Decimal('0.00')), name='chk_mat_req_received_non_negative'),
            models.CheckConstraint(condition=models.Q(total_received_quantity__lte=models.F('required_quantity')), name='chk_mat_req_received_lte_required'),
        ]

    def save(self, *args, **kwargs):
        if not self.request_code:
            last = MaterialRequest.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.request_code = f"MREQ-{next_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.request_code} - {self.material.name} ({self.project.project_code})"


class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        IN = 'IN', 'Stock In (Delivery)'
        OUT = 'OUT', 'Stock Out (Consumption)'
        ADJUSTMENT = 'ADJUSTMENT', 'Stock Adjustment'

    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices, db_index=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    idempotency_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    delivery_challan_no = models.CharField(max_length=100, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='stock_transactions',
    )
    material_request = models.ForeignKey(
        MaterialRequest,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='stock_transactions',
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_transactions',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='stock_transactions',
    )

    class Meta:
        db_table = 'operations_stocktransaction'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=Decimal('0.00')), name='chk_stock_txn_qty_positive'),
            models.CheckConstraint(condition=models.Q(balance_after__gte=Decimal('0.00')), name='chk_stock_txn_balance_non_negative'),
        ]

    def __str__(self):
        return f"{self.transaction_type}: {self.quantity} {self.material.unit} - {self.material.name}"


class SiteProblemReport(models.Model):
    class Severity(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'

    problem_code = models.CharField(max_length=30, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.MEDIUM)
    description = models.TextField()
    photo = models.ImageField(upload_to='site_problems/%Y/%m/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='site_problems',
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='reported_site_problems',
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='resolved_site_problems',
    )

    class Meta:
        db_table = 'operations_siteproblemreport'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.problem_code:
            last = SiteProblemReport.objects.order_by('-id').first()
            next_id = (last.id + 1) if last else 1
            self.problem_code = f"PRB-{next_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.problem_code} - {self.title} ({self.status})"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        HALF_DAY = 'HALF_DAY', 'Half Day'
        INCOMPLETE_CHECKOUT = 'INCOMPLETE_CHECKOUT', 'Incomplete Check-Out'

    class VerificationMethod(models.TextChoices):
        PIN = 'PIN', 'Worker ID & PIN'
        RFID = 'RFID', 'RFID Card'
        BIOMETRIC = 'BIOMETRIC', 'Biometric'

    attendance_date = models.DateField(db_index=True)
    check_in_time = models.DateTimeField()
    check_out_time = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.PRESENT, db_index=True)
    verification_method = models.CharField(max_length=20, choices=VerificationMethod.choices, default=VerificationMethod.PIN)
    is_regularized = models.BooleanField(default=False)
    regularized_at = models.DateTimeField(blank=True, null=True)
    regularization_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='attendance_records',
    )
    regularized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='regularized_attendances',
    )
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='attendance_records',
    )

    class Meta:
        db_table = 'operations_attendance'
        ordering = ['-attendance_date', '-check_in_time']
        constraints = [
            models.UniqueConstraint(fields=('worker', 'project', 'attendance_date'), name='uq_worker_project_attendance_date'),
            models.CheckConstraint(
                condition=models.Q(check_out_time__isnull=True) | models.Q(check_out_time__gte=models.F('check_in_time')),
                name='chk_attendance_checkout_gte_checkin',
            ),
        ]

    def __str__(self):
        return f"{self.worker.username} - {self.project.project_code} ({self.attendance_date})"

