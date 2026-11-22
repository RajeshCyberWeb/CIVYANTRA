from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.decorators import role_required
from accounts.models import User
from .forms import (
    ProjectAssignmentForm, ProjectForm, ProjectHolidayForm,
    TaskDelayReportForm, TaskForm, TaskProgressForm, TaskQuantityAdjustmentForm,
)
from .models import Project, ProjectAssignment, ProjectHoliday, Task, TaskDelayReport, TaskProgressHistory
from .services import (
    acknowledge_task_delay, adjust_task_quantity, assign_worker_to_project,
    create_project, create_task, deactivate_worker_assignment,
    report_task_delay, review_task_progress, submit_task_progress, update_project,
)

DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def _can_manage_project(user, project):
    if user.role == User.Role.ADMIN:
        return True
    return user.role == User.Role.SUPERVISOR and project.supervisor_id == user.id


def _can_view_project(user, project):
    if _can_manage_project(user, project):
        return True
    if user.role == User.Role.WORKER:
        return ProjectAssignment.objects.filter(project=project, worker=user, is_active=True).exists()
    return False


@login_required
def project_list(request):
    qs = Project.objects.select_related('supervisor').annotate(
        active_workers_count=Count('assignments', filter=Q(assignments__is_active=True))
    )
    if request.user.role == User.Role.SUPERVISOR:
        qs = qs.filter(supervisor=request.user)
    elif request.user.role == User.Role.WORKER:
        qs = qs.filter(assignments__worker=request.user, assignments__is_active=True).distinct()

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        qs = qs.filter(status=status_filter)

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(Q(project_code__icontains=query) | Q(name__icontains=query) | Q(location__icontains=query))

    return render(request, 'projects/project_list.html', {
        'projects': qs,
        'status_filter': status_filter,
        'query': query,
        'status_choices': Project.Status.choices,
    })


@role_required(User.Role.ADMIN)
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        project = create_project(
            name=cd['name'],
            location=cd['location'],
            description=cd['description'],
            supervisor=cd['supervisor'],
            start_date=cd['start_date'],
            expected_end_date=cd['expected_end_date'],
            status=cd['status'],
            working_days_mask=form.get_working_days_mask(),
            created_by=request.user,
        )
        messages.success(request, f'Project {project.project_code} created successfully.')
        return redirect('projects:project_detail', project_id=project.id)
    return render(request, 'projects/project_form.html', {'form': form, 'is_edit': False})


@role_required(User.Role.ADMIN)
def project_edit(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        update_project(
            project,
            name=cd['name'],
            location=cd['location'],
            description=cd['description'],
            supervisor=cd['supervisor'],
            start_date=cd['start_date'],
            expected_end_date=cd['expected_end_date'],
            status=cd['status'],
            working_days_mask=form.get_working_days_mask(),
            updated_by=request.user,
        )
        messages.success(request, f'Project {project.project_code} updated.')
        return redirect('projects:project_detail', project_id=project.id)
    return render(request, 'projects/project_form.html', {'form': form, 'project': project, 'is_edit': True})


@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project.objects.select_related('supervisor'), id=project_id)
    if not _can_view_project(request.user, project):
        raise PermissionDenied('You do not have access to this project.')

    manageable = _can_manage_project(request.user, project)
    active_assignments = project.assignments.filter(is_active=True).select_related('worker', 'worker__worker_profile')
    past_assignments = project.assignments.filter(is_active=False).select_related('worker', 'worker__worker_profile')
    holidays = project.holidays.all()
    tasks = project.tasks.select_related('assigned_to', 'assigned_to__worker_profile')
    if request.user.role == User.Role.WORKER:
        tasks = tasks.filter(assigned_to=request.user)

    working_day_names = [DAY_LABELS[i] for i in range(7) if int(project.working_days_mask or 0) & (1 << i)]
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'manageable': manageable,
        'active_assignments': active_assignments,
        'past_assignments': past_assignments,
        'holidays': holidays,
        'tasks': tasks,
        'working_day_names': working_day_names,
        'assignment_form': ProjectAssignmentForm(project=project, initial={'assigned_date': timezone.localdate()}),
        'holiday_form': ProjectHolidayForm(),
    })


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def assign_worker(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not _can_manage_project(request.user, project):
        raise PermissionDenied('Only the assigned supervisor or admin can manage site workers.')
    if request.method == 'POST':
        form = ProjectAssignmentForm(request.POST, project=project)
        if form.is_valid():
            try:
                assign_worker_to_project(
                    project=project,
                    worker=form.cleaned_data['worker'],
                    assigned_by=request.user,
                    assigned_date=form.cleaned_data['assigned_date'],
                    notes=form.cleaned_data['notes'],
                )
                messages.success(request, 'Worker assigned to project.')
            except ValidationError as exc:
                messages.error(request, exc.message)
        else:
            messages.error(request, 'Please select a valid worker and start date.')
    return redirect('projects:project_detail', project_id=project.id)


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def deactivate_assignment(request, project_id, assignment_id):
    project = get_object_or_404(Project, id=project_id)
    if not _can_manage_project(request.user, project):
        raise PermissionDenied('Only the assigned supervisor or admin can manage site workers.')
    if request.method == 'POST':
        assignment = get_object_or_404(ProjectAssignment, id=assignment_id, project=project)
        deactivate_worker_assignment(assignment, deactivated_by=request.user)
        messages.warning(request, f'Assignment ended for {assignment.worker.get_display_name()}.')
    return redirect('projects:project_detail', project_id=project.id)


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def add_holiday(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not _can_manage_project(request.user, project):
        raise PermissionDenied('Only the assigned supervisor or admin can manage site holidays.')
    if request.method == 'POST':
        form = ProjectHolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save(commit=False)
            holiday.project = project
            holiday.created_by = request.user
            try:
                holiday.save()
                messages.success(request, f'Holiday "{holiday.title}" added.')
            except Exception:
                messages.error(request, 'A holiday is already recorded on that date.')
    return redirect('projects:project_detail', project_id=project.id)


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def delete_holiday(request, project_id, holiday_id):
    project = get_object_or_404(Project, id=project_id)
    if not _can_manage_project(request.user, project):
        raise PermissionDenied('Only the assigned supervisor or admin can manage site holidays.')
    if request.method == 'POST':
        holiday = get_object_or_404(ProjectHoliday, id=holiday_id, project=project)
        holiday.delete()
        messages.info(request, 'Site holiday removed.')
    return redirect('projects:project_detail', project_id=project.id)


@login_required
def task_list(request):
    qs = Task.objects.select_related('project', 'assigned_to', 'assigned_to__worker_profile')
    if request.user.role == User.Role.SUPERVISOR:
        qs = qs.filter(project__supervisor=request.user)
    elif request.user.role == User.Role.WORKER:
        qs = qs.filter(assigned_to=request.user)

    status_filter = request.GET.get('status', 'ALL')
    if status_filter != 'ALL':
        qs = qs.filter(status=status_filter)

    query = request.GET.get('q', '').strip()
    if query:
        qs = qs.filter(Q(title__icontains=query) | Q(category__icontains=query) | Q(project__project_code__icontains=query))

    return render(request, 'projects/task_list.html', {
        'tasks': qs,
        'status_filter': status_filter,
        'query': query,
        'status_choices': Task.Status.choices,
    })


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def task_create(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if not _can_manage_project(request.user, project):
        raise PermissionDenied('Only the assigned supervisor or admin can assign tasks.')

    form = TaskForm(request.POST or None, project=project)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        try:
            task = create_task(
                project=project,
                assigned_to=cd['assigned_to'],
                assigned_by=request.user,
                title=cd['title'],
                category=cd['category'],
                unit=cd['unit'],
                assigned_quantity=cd['assigned_quantity'],
                priority=cd['priority'],
                deadline=cd['deadline'],
                description=cd['description'],
            )
            messages.success(request, f'Task "{task.title}" assigned to {task.assigned_to.get_display_name()}.')
            return redirect('projects:task_detail', task_id=task.id)
        except ValidationError as exc:
            messages.error(request, exc.message)

    return render(request, 'projects/task_form.html', {'form': form, 'project': project})


@login_required
def task_detail(request, task_id):
    task = get_object_or_404(Task.objects.select_related('project', 'assigned_to', 'assigned_by'), id=task_id)
    manageable = _can_manage_project(request.user, task.project)
    is_assignee = request.user.role == User.Role.WORKER and task.assigned_to_id == request.user.id
    if not (manageable or is_assignee):
        raise PermissionDenied('You do not have access to this task.')

    can_submit = manageable or is_assignee
    pct = 0
    if task.assigned_quantity and task.assigned_quantity > 0:
        pct = min(100, round((task.cached_approved_quantity / task.assigned_quantity) * 100, 1))

    return render(request, 'projects/task_detail.html', {
        'task': task,
        'manageable': manageable,
        'can_submit': can_submit,
        'completion_pct': pct,
        'progress_entries': task.progress_entries.select_related('submitted_by', 'reviewed_by'),
        'adjustments': task.quantity_adjustments.select_related('adjusted_by'),
        'delay_reports': task.delay_reports.select_related('reported_by', 'acknowledged_by'),
        'progress_form': TaskProgressForm(initial={'work_date': timezone.localdate()}),
        'adjustment_form': TaskQuantityAdjustmentForm(initial={'new_quantity': task.assigned_quantity}),
        'delay_form': TaskDelayReportForm(),
    })


@login_required
def submit_progress(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    manageable = _can_manage_project(request.user, task.project)
    is_assignee = request.user.role == User.Role.WORKER and task.assigned_to_id == request.user.id
    if not (manageable or is_assignee):
        raise PermissionDenied('You cannot submit progress for this task.')

    if request.method == 'POST':
        form = TaskProgressForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                submit_task_progress(
                    task=task,
                    submitted_by=request.user,
                    work_date=cd['work_date'],
                    quantity_submitted=cd['quantity_submitted'],
                    remarks=cd['remarks'],
                    proof_photo=cd.get('proof_photo'),
                )
                messages.success(request, 'Work progress submitted for supervisor verification.')
            except ValidationError as exc:
                messages.error(request, exc.message)
        else:
            messages.error(request, 'Please enter a valid work date and positive quantity.')
    return redirect('projects:task_detail', task_id=task.id)


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def review_progress(request, task_id, entry_id):
    task = get_object_or_404(Task, id=task_id)
    if not _can_manage_project(request.user, task.project):
        raise PermissionDenied('Only the assigned supervisor or admin can verify work progress.')

    if request.method == 'POST':
        entry = get_object_or_404(TaskProgressHistory, id=entry_id, task=task)
        decision = request.POST.get('decision')
        review_notes = request.POST.get('review_notes', '')
        try:
            review_task_progress(entry=entry, reviewed_by=request.user, decision=decision, review_notes=review_notes)
            messages.success(request, f'Progress entry marked as {decision}.')
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect('projects:task_detail', task_id=task.id)


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def adjust_quantity(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    if not _can_manage_project(request.user, task.project):
        raise PermissionDenied('Only the assigned supervisor or admin can adjust task quantities.')

    if request.method == 'POST':
        form = TaskQuantityAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                adjust_task_quantity(
                    task=task,
                    adjusted_by=request.user,
                    new_quantity=form.cleaned_data['new_quantity'],
                    reason=form.cleaned_data['reason'],
                )
                messages.success(request, 'Target task quantity updated.')
            except ValidationError as exc:
                messages.error(request, exc.message)
        else:
            messages.error(request, 'Enter a valid target quantity and reason.')
    return redirect('projects:task_detail', task_id=task.id)


@login_required
def report_delay(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    manageable = _can_manage_project(request.user, task.project)
    is_assignee = request.user.role == User.Role.WORKER and task.assigned_to_id == request.user.id
    if not (manageable or is_assignee):
        raise PermissionDenied('You cannot report delays for this task.')

    if request.method == 'POST':
        form = TaskDelayReportForm(request.POST)
        if form.is_valid():
            report_task_delay(
                task=task,
                reported_by=request.user,
                expected_completion_date=form.cleaned_data['expected_completion_date'],
                reason=form.cleaned_data['reason'],
            )
            messages.warning(request, 'Task delay reported and supervisor notified.')
        else:
            messages.error(request, 'Provide a valid completion date and delay reason.')
    return redirect('projects:task_detail', task_id=task.id)


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def acknowledge_delay(request, task_id, delay_id):
    task = get_object_or_404(Task, id=task_id)
    if not _can_manage_project(request.user, task.project):
        raise PermissionDenied('Only the assigned supervisor or admin can acknowledge delays.')

    if request.method == 'POST':
        delay = get_object_or_404(TaskDelayReport, id=delay_id, task=task)
        acknowledge_task_delay(delay=delay, acknowledged_by=request.user)
        messages.info(request, 'Delay report acknowledged.')
    return redirect('projects:task_detail', task_id=task.id)

@login_required
def mark_task_done(request, task_id):
    task = get_object_or_404(Task, id=task_id)
    manageable = _can_manage_project(request.user, task.project)
    is_assignee = request.user.role == User.Role.WORKER and task.assigned_to_id == request.user.id
    if not (manageable or is_assignee):
        raise PermissionDenied('You cannot complete this task.')
    if request.method == 'POST':
        remaining = task.remaining_quantity if getattr(task, 'remaining_quantity', 0) > 0 else task.assigned_quantity
        try:
            submit_task_progress(task=task, submitted_by=request.user, work_date=timezone.localdate(), quantity_submitted=remaining, remarks='Marked as Done by worker')
            messages.success(request, f'Work {task.title} marked as Done! Notification sent to Supervisor and Admin.')
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect(request.META.get('HTTP_REFERER') or 'core:dashboard')
