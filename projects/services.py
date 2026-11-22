import re
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from accounts.models import User
from core.utils import log_action, notify_user
from projects.models import Project, ProjectAssignment, Task, TaskDelayReport, TaskProgressHistory, TaskQuantityAdjustment


def generate_next_project_code():
    codes = Project.objects.values_list('project_code', flat=True)
    max_num = 0
    for code in codes:
        match = re.match(r'^PRJ-([0-9]+)$', code or '')
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f'PRJ-{max_num + 1:03d}'


@transaction.atomic
def create_project(*, name, location, description, supervisor, start_date, expected_end_date, status, working_days_mask, created_by):
    project = Project.objects.create(
        project_code=generate_next_project_code(),
        name=name,
        location=location,
        description=description,
        supervisor=supervisor,
        created_by=created_by,
        start_date=start_date,
        expected_end_date=expected_end_date,
        status=status,
        working_days_mask=working_days_mask,
    )
    notify_user(supervisor, f'You were assigned as Site Supervisor for {project.project_code} ({project.name}).')
    log_action(created_by, 'PROJECT_CREATED', f'Created project {project.project_code} - {project.name}')
    return project


@transaction.atomic
def update_project(project, *, name, location, description, supervisor, start_date, expected_end_date, status, working_days_mask, updated_by):
    project.name = name
    project.location = location
    project.description = description
    project.supervisor = supervisor
    project.start_date = start_date
    project.expected_end_date = expected_end_date
    project.status = status
    project.working_days_mask = working_days_mask
    project.save()
    log_action(updated_by, 'PROJECT_UPDATED', f'Updated project {project.project_code}')
    return project


@transaction.atomic
def assign_worker_to_project(*, project, worker, assigned_by, assigned_date, notes=''):
    if ProjectAssignment.objects.filter(project=project, worker=worker, is_active=True).exists():
        raise ValidationError('This worker is already actively assigned to this project.')
    try:
        assignment = ProjectAssignment.objects.create(
            project=project,
            worker=worker,
            assigned_by=assigned_by,
            assigned_date=assigned_date,
            notes=notes,
            is_active=True,
        )
    except IntegrityError:
        raise ValidationError('This worker is already actively assigned to this project.')
    notify_user(worker, f'You have been assigned to site {project.project_code} ({project.name}).')
    log_action(assigned_by, 'WORKER_ASSIGNED', f'Assigned {worker.username} to {project.project_code}')
    return assignment


@transaction.atomic
def deactivate_worker_assignment(assignment, *, deactivated_by):
    assignment.is_active = False
    assignment.deactivated_date = timezone.localdate()
    assignment.save(update_fields=['is_active', 'deactivated_date'])
    log_action(deactivated_by, 'WORKER_UNASSIGNED', f'Ended assignment of {assignment.worker.username} on {assignment.project.project_code}')
    return assignment


@transaction.atomic
def create_task(*, project, assigned_to, assigned_by, title, category, unit, assigned_quantity, priority, deadline, description=''):
    if not ProjectAssignment.objects.filter(project=project, worker=assigned_to, is_active=True).exists():
        raise ValidationError('Tasks can only be assigned to workers actively assigned to this site.')
    task = Task.objects.create(
        project=project,
        assigned_to=assigned_to,
        assigned_by=assigned_by,
        title=title,
        category=category,
        unit=unit,
        assigned_quantity=assigned_quantity,
        priority=priority,
        deadline=deadline,
        description=description,
    )
    notify_user(assigned_to, f'New task assigned on {project.project_code}: {task.title} ({task.assigned_quantity} {task.unit}).')
    log_action(assigned_by, 'TASK_CREATED', f'Assigned task "{task.title}" to {assigned_to.username} on {project.project_code}')
    return task


def _recalculate_task_progress(task):
    total = task.progress_entries.filter(status=TaskProgressHistory.ApprovalStatus.APPROVED).aggregate(s=Sum('quantity_submitted'))['s'] or Decimal('0.00')
    task.cached_approved_quantity = total
    if total >= task.assigned_quantity and task.assigned_quantity > 0:
        task.status = Task.Status.COMPLETED
    elif total > 0 and task.status == Task.Status.PENDING:
        task.status = Task.Status.IN_PROGRESS
    task.save(update_fields=['cached_approved_quantity', 'status', 'updated_at'])


@transaction.atomic
def submit_task_progress(*, task, submitted_by, work_date, quantity_submitted, remarks='', proof_photo=None):
    if quantity_submitted <= 0:
        raise ValidationError('Submitted quantity must be greater than zero.')
    entry = TaskProgressHistory.objects.create(
        task=task,
        submitted_by=submitted_by,
        work_date=work_date,
        quantity_submitted=quantity_submitted,
        remarks=remarks,
        proof_photo=proof_photo,
    )
    if task.status == Task.Status.PENDING:
        task.status = Task.Status.IN_PROGRESS
        task.save(update_fields=['status', 'updated_at'])
    notify_user(task.project.supervisor, f'Progress submitted on {task.project.project_code} for "{task.title}" (+{quantity_submitted} {task.unit}).')
    log_action(submitted_by, 'TASK_PROGRESS_SUBMITTED', f'Submitted {quantity_submitted} {task.unit} on task #{task.id}')
    return entry


@transaction.atomic
def review_task_progress(*, entry, reviewed_by, decision, review_notes=''):
    if decision not in (TaskProgressHistory.ApprovalStatus.APPROVED, TaskProgressHistory.ApprovalStatus.REJECTED):
        raise ValidationError('Invalid review decision.')
    entry.status = decision
    entry.reviewed_by = reviewed_by
    entry.reviewed_at = timezone.now()
    entry.review_notes = review_notes
    entry.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])
    _recalculate_task_progress(entry.task)
    notify_user(entry.submitted_by, f'Your progress entry for "{entry.task.title}" was {decision}.')
    log_action(reviewed_by, 'TASK_PROGRESS_REVIEWED', f'Marked progress #{entry.id} as {decision}')
    return entry


@transaction.atomic
def adjust_task_quantity(*, task, adjusted_by, new_quantity, reason):
    if new_quantity <= 0:
        raise ValidationError('New target quantity must be greater than zero.')
    prev = task.assigned_quantity
    adj = TaskQuantityAdjustment.objects.create(
        task=task,
        adjusted_by=adjusted_by,
        previous_quantity=prev,
        new_quantity=new_quantity,
        reason=reason,
    )
    task.assigned_quantity = new_quantity
    task.save(update_fields=['assigned_quantity', 'updated_at'])
    _recalculate_task_progress(task)
    notify_user(task.assigned_to, f'Target quantity for "{task.title}" updated from {prev} to {new_quantity} {task.unit}.')
    log_action(adjusted_by, 'TASK_QUANTITY_ADJUSTED', f'Adjusted task #{task.id} target from {prev} to {new_quantity}')
    return adj


@transaction.atomic
def report_task_delay(*, task, reported_by, expected_completion_date, reason):
    delay = TaskDelayReport.objects.create(
        task=task,
        reported_by=reported_by,
        expected_completion_date=expected_completion_date,
        reason=reason,
    )
    if task.status != Task.Status.COMPLETED:
        task.status = Task.Status.DELAYED
        task.save(update_fields=['status', 'updated_at'])
    notify_user(task.project.supervisor, f'Delay reported on {task.project.project_code} for "{task.title}".')
    log_action(reported_by, 'TASK_DELAY_REPORTED', f'Reported delay on task #{task.id}')
    return delay


@transaction.atomic
def acknowledge_task_delay(*, delay, acknowledged_by):
    delay.is_acknowledged = True
    delay.acknowledged_by = acknowledged_by
    delay.acknowledged_at = timezone.now()
    delay.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at'])
    notify_user(delay.reported_by, f'Your delay report for "{delay.task.title}" was acknowledged.')
    log_action(acknowledged_by, 'TASK_DELAY_ACKNOWLEDGED', f'Acknowledged delay #{delay.id}')
    return delay
