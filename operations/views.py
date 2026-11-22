from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from accounts.models import User
from core.utils import log_action, notify_user
from projects.models import Project, ProjectAssignment, Task
from .forms import AttendanceCheckInForm, MaterialForm, MaterialRequestForm, SiteProblemForm
from .models import Attendance, Material, MaterialRequest, ProjectMaterialInventory, SiteProblemReport, StockTransaction


def _notify_supervisors_and_admins(project, actor, message_text):
    recipients = set(User.objects.filter(role='ADMIN', is_active=True, is_deleted=False))
    if project and project.supervisor and project.supervisor.is_active:
        recipients.add(project.supervisor)
    recipients.discard(actor)
    for user in recipients:
        notify_user(user, message_text)


@login_required
def attendance_list(request):
    today = timezone.localdate()
    records = Attendance.objects.select_related('project', 'worker').all()
    if request.user.role == 'WORKER':
        records = records.filter(worker=request.user)

    form = AttendanceCheckInForm()
    form.fields['worker'].queryset = User.objects.filter(role='WORKER', is_active=True)

    if request.method == 'POST':
        form = AttendanceCheckInForm(request.POST)
        if form.is_valid():
            project = form.cleaned_data['project']
            worker = form.cleaned_data['worker']
            existing = Attendance.objects.filter(project=project, worker=worker, attendance_date=today).first()
            if existing:
                messages.warning(request, f"{worker.username} has already checked in for {project.project_code} today.")
            else:
                att = form.save(commit=False)
                att.attendance_date = today
                att.check_in_time = timezone.now()
                att.status = Attendance.Status.INCOMPLETE_CHECKOUT
                att.save()
                log_action(request.user, 'ATTENDANCE_CHECK_IN', f"Checked in {worker.username} at {project.project_code}")
                messages.success(request, f"Check-in recorded for {worker.username}.")
            return redirect('operations:attendance_list')

    return render(request, 'operations/attendance_list.html', {
        'records': records[:50],
        'form': form,
        'today': today,
    })


@login_required
def attendance_checkout(request, pk):
    att = get_object_or_404(Attendance, pk=pk)
    if request.method == 'POST' and not att.check_out_time:
        att.check_out_time = timezone.now()
        hours = (att.check_out_time - att.check_in_time).total_seconds() / 3600
        att.status = Attendance.Status.PRESENT if hours >= 4 else Attendance.Status.HALF_DAY
        att.save()
        log_action(request.user, 'ATTENDANCE_CHECK_OUT', f"Checked out {att.worker.username} ({att.status})")
        messages.success(request, f"Check-out recorded ({att.get_status_display()}).")
    return redirect('operations:attendance_list')


@login_required
def material_dashboard(request):
    inventories = ProjectMaterialInventory.objects.select_related('project', 'material').all()
    requests_qs = MaterialRequest.objects.select_related('project', 'material', 'requested_by', 'reviewed_by').all()

    if request.user.role == 'SUPERVISOR':
        inventories = inventories.filter(project__supervisor=request.user)
        requests_qs = requests_qs.filter(project__supervisor=request.user)
    elif request.user.role == 'WORKER':
        assigned_ids = ProjectAssignment.objects.filter(
            worker=request.user, is_active=True
        ).values_list('project_id', flat=True)
        inventories = inventories.filter(project_id__in=assigned_ids)
        requests_qs = requests_qs.filter(Q(requested_by=request.user) | Q(project_id__in=assigned_ids)).distinct()

    req_form = MaterialRequestForm()
    mat_form = MaterialForm()

    if request.user.role == 'SUPERVISOR':
        req_form.fields['project'].queryset = Project.objects.filter(supervisor=request.user, is_deleted=False)
    elif request.user.role == 'WORKER':
        assigned_ids = ProjectAssignment.objects.filter(
            worker=request.user, is_active=True
        ).values_list('project_id', flat=True)
        req_form.fields['project'].queryset = Project.objects.filter(id__in=assigned_ids, is_deleted=False)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_material' and request.user.role in ['ADMIN', 'SUPERVISOR']:
            mat_form = MaterialForm(request.POST)
            if mat_form.is_valid():
                mat = mat_form.save(commit=False)
                mat.created_by = request.user
                mat.save()
                messages.success(request, f"Material '{mat.name}' added to catalog.")
                return redirect('operations:material_dashboard')
        elif action == 'request_material' and request.user.role in ['SUPERVISOR', 'WORKER']:
            req_form = MaterialRequestForm(request.POST, request.FILES)
            if req_form.is_valid():
                mreq = req_form.save(commit=False)
                mreq.requested_by = request.user
                mreq.save()
                log_action(request.user, 'MATERIAL_REQUESTED', f"Requested {mreq.required_quantity} {mreq.material.unit} of {mreq.material.name}")
                _notify_supervisors_and_admins(
                    mreq.project,
                    request.user,
                    f"{request.user.get_display_name()} ({request.user.get_role_display()}) reported {mreq.get_problem_type_display()} for {mreq.material.name} ({mreq.required_quantity} {mreq.material.unit}) at {mreq.project.project_code}."
                )
                messages.success(request, f"Material report {mreq.request_code} sent to Supervisor & Admin.")
                return redirect('operations:material_dashboard')

    return render(request, 'operations/material_dashboard.html', {
        'inventories': inventories,
        'material_requests': requests_qs[:30],
        'req_form': req_form,
        'mat_form': mat_form,
    })


@login_required
def review_material_request(request, pk):
    mreq = get_object_or_404(MaterialRequest, pk=pk)
    if request.method == 'POST' and request.user.role in ['ADMIN', 'SUPERVISOR']:
        decision = request.POST.get('decision')
        notes = request.POST.get('review_notes', '')
        if decision == 'ORDER':
            mreq.approval_status = MaterialRequest.ApprovalStatus.APPROVED
            mreq.order_status = MaterialRequest.OrderStatus.ORDERED
            mreq.reviewed_by = request.user
            mreq.reviewed_at = timezone.now()
            mreq.review_notes = notes
            mreq.save()
            notify_user(mreq.requested_by, f"Material request {mreq.request_code} ({mreq.material.name}) has been approved and marked Ordered.")
            messages.success(request, f"{mreq.request_code} marked as Ordered (shopping in progress).")
        elif decision == 'APPROVE':
            mreq.approval_status = MaterialRequest.ApprovalStatus.APPROVED
            mreq.order_status = MaterialRequest.OrderStatus.DELIVERED
            mreq.total_received_quantity = mreq.required_quantity
            mreq.reviewed_by = request.user
            mreq.reviewed_at = timezone.now()
            mreq.review_notes = notes
            mreq.save()

            inv, _ = ProjectMaterialInventory.objects.get_or_create(
                project=mreq.project,
                material=mreq.material,
                defaults={'available_quantity': Decimal('0.00'), 'reorder_level': Decimal('10.00')},
            )
            inv.available_quantity += mreq.required_quantity
            inv.save()

            StockTransaction.objects.create(
                project=mreq.project,
                material=mreq.material,
                material_request=mreq,
                transaction_type=StockTransaction.TransactionType.IN,
                quantity=mreq.required_quantity,
                balance_after=inv.available_quantity,
                performed_by=request.user,
                remarks=f"Approved & delivered via {mreq.request_code}",
            )
            notify_user(mreq.requested_by, f"Material request {mreq.request_code} ({mreq.material.name}) was delivered and stocked.")
            messages.success(request, f"{mreq.request_code} delivered and added to project inventory.")
        elif decision == 'REJECT':
            mreq.approval_status = MaterialRequest.ApprovalStatus.REJECTED
            mreq.reviewed_by = request.user
            mreq.reviewed_at = timezone.now()
            mreq.review_notes = notes
            mreq.save()
            notify_user(mreq.requested_by, f"Material request {mreq.request_code} was rejected.")
            messages.info(request, f"{mreq.request_code} rejected.")
    return redirect('operations:material_dashboard')


@login_required
def problem_list(request):
    problems = SiteProblemReport.objects.select_related('project', 'reported_by', 'resolved_by').all()
    form = SiteProblemForm()

    if request.user.role == 'SUPERVISOR':
        problems = problems.filter(project__supervisor=request.user)
        form.fields['project'].queryset = Project.objects.filter(supervisor=request.user, is_deleted=False)
    elif request.user.role == 'WORKER':
        assigned_ids = ProjectAssignment.objects.filter(
            worker=request.user, is_active=True
        ).values_list('project_id', flat=True)
        problems = problems.filter(Q(reported_by=request.user) | Q(project_id__in=assigned_ids)).distinct()
        form.fields['project'].queryset = Project.objects.filter(id__in=assigned_ids, is_deleted=False)

    if request.method == 'POST' and request.user.role in ['SUPERVISOR', 'WORKER']:
        form = SiteProblemForm(request.POST, request.FILES)
        if form.is_valid():
            prob = form.save(commit=False)
            prob.reported_by = request.user
            prob.save()
            log_action(request.user, 'SITE_PROBLEM_REPORTED', f"Reported {prob.problem_code}: {prob.title}")
            _notify_supervisors_and_admins(
                prob.project,
                request.user,
                f"Site issue {prob.problem_code} ({prob.get_severity_display()}) reported by {request.user.get_display_name()} ({request.user.get_role_display()}) at {prob.project.project_code}: {prob.title}"
            )
            messages.success(request, f"Site issue {prob.problem_code} reported to Supervisor & Admin.")
            return redirect('operations:problem_list')

    return render(request, 'operations/problem_list.html', {
        'problems': problems[:30],
        'form': form,
    })


@login_required
def resolve_problem(request, pk):
    prob = get_object_or_404(SiteProblemReport, pk=pk)
    if request.method == 'POST' and request.user.role in ['ADMIN', 'SUPERVISOR']:
        prob.status = SiteProblemReport.Status.RESOLVED
        prob.resolved_by = request.user
        prob.resolved_at = timezone.now()
        prob.resolution_notes = request.POST.get('resolution_notes', 'Resolved on site.')
        prob.save()
        notify_user(prob.reported_by, f"Site issue {prob.problem_code} has been marked Resolved.")
        messages.success(request, f"{prob.problem_code} marked as Resolved.")
    return redirect('operations:problem_list')


@login_required
def operations_report(request):
    projects = Project.objects.all()
    report_rows = []
    for proj in projects:
        tasks = Task.objects.filter(project=proj)
        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status='COMPLETED').count()
        present_today = Attendance.objects.filter(project=proj, attendance_date=timezone.localdate()).count()
        pending_materials = MaterialRequest.objects.filter(project=proj, approval_status='PENDING').count()
        open_issues = SiteProblemReport.objects.filter(project=proj).exclude(status='RESOLVED').count()
        report_rows.append({
            'project': proj,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'present_today': present_today,
            'pending_materials': pending_materials,
            'open_issues': open_issues,
        })

    return render(request, 'operations/report.html', {
        'report_rows': report_rows,
        'total_projects': projects.count(),
        'total_workers': User.objects.filter(role='WORKER').count(),
        'total_attendance': Attendance.objects.count(),
        'total_requests': MaterialRequest.objects.count(),
    })
