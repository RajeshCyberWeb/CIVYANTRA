from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from accounts.decorators import admin_required, supervisor_required, worker_required
from accounts.models import User
from accounts.views import get_dashboard_url_for_role
from operations.models import (
    Attendance,
    Material,
    MaterialRequest,
    ProjectMaterialInventory,
    SiteProblemReport,
)
from projects.models import Project, ProjectAssignment, Task, TaskProgressHistory


def _calc_pct(approved, assigned):
    if not assigned or assigned <= Decimal('0'):
        return 0
    pct = int(round((float(approved) / float(assigned)) * 100))
    return min(100, max(0, pct))


def home_redirect(request):
    if request.user.is_authenticated and request.user.is_active and not request.user.is_deleted:
        return redirect(get_dashboard_url_for_role(request.user))
    return redirect('accounts:login')


@admin_required
def admin_dashboard(request):
    today = timezone.localdate()
    supervisors = User.objects.filter(role=User.Role.SUPERVISOR, is_active=True, is_deleted=False)
    workers = User.objects.filter(role=User.Role.WORKER, is_active=True, is_deleted=False)
    projects = Project.objects.filter(is_deleted=False).select_related('supervisor')

    all_tasks = Task.objects.filter(is_deleted=False).select_related('project', 'assigned_to')
    task_status_counts = {
        'pending': all_tasks.filter(status=Task.Status.PENDING).count(),
        'in_progress': all_tasks.filter(status=Task.Status.IN_PROGRESS).count(),
        'delayed': all_tasks.filter(status=Task.Status.DELAYED).count(),
        'completed': all_tasks.filter(status=Task.Status.COMPLETED).count(),
        'total': all_tasks.count(),
    }
    recent_tasks = all_tasks.order_by('-updated_at')[:4]

    today_present_count = Attendance.objects.filter(attendance_date=today).values('worker_id').distinct().count()
    open_problems = SiteProblemReport.objects.filter(
        status__in=[SiteProblemReport.Status.OPEN, SiteProblemReport.Status.IN_PROGRESS],
        project__is_deleted=False,
    ).select_related('project', 'reported_by')
    pending_material_count = MaterialRequest.objects.filter(
        approval_status=MaterialRequest.ApprovalStatus.PENDING,
        project__is_deleted=False,
    ).count()
    low_stock_count = ProjectMaterialInventory.objects.filter(
        available_quantity__lte=F('reorder_level'),
        project__is_deleted=False,
    ).count()
    material_count = Material.objects.filter(is_active=True).count()
    db_table_count = len(connection.introspection.table_names())

    supervisor_tracking = []
    for sup in supervisors:
        sup_projects = [p for p in projects if p.supervisor_id == sup.id]
        sup_tasks = Task.objects.filter(project__supervisor=sup, is_deleted=False)
        total_t = sup_tasks.count()
        completed_t = sup_tasks.filter(status=Task.Status.COMPLETED).count()
        pending_reviews = TaskProgressHistory.objects.filter(
            task__project__supervisor=sup,
            status=TaskProgressHistory.Status.PENDING
        ).count()
        active_workers_count = ProjectAssignment.objects.filter(
            project__supervisor=sup,
            is_active=True,
            project__is_deleted=False
        ).values('worker_id').distinct().count()
        pct = int(round((completed_t / total_t) * 100)) if total_t else 0
        supervisor_tracking.append({
            'supervisor': sup,
            'projects': sup_projects,
            'project_count': len(sup_projects),
            'worker_count': active_workers_count,
            'total_tasks': total_t,
            'completed_tasks': completed_t,
            'pending_reviews': pending_reviews,
            'completion_pct': pct,
        })

    worker_tracking = []
    for w in workers:
        active_assigns = ProjectAssignment.objects.filter(
            worker=w, is_active=True, project__is_deleted=False
        ).select_related('project', 'project__supervisor')
        w_tasks = Task.objects.filter(assigned_to=w, is_deleted=False)
        total_wt = w_tasks.count()
        completed_wt = w_tasks.filter(status=Task.Status.COMPLETED).count()
        in_prog_wt = w_tasks.filter(status__in=[Task.Status.PENDING, Task.Status.IN_PROGRESS]).count()
        pct_w = int(round((completed_wt / total_wt) * 100)) if total_wt else 0
        checked_in_today = Attendance.objects.filter(worker=w, attendance_date=today).exists()
        worker_tracking.append({
            'worker': w,
            'assignments': active_assigns,
            'total_tasks': total_wt,
            'completed_tasks': completed_wt,
            'active_tasks': in_prog_wt,
            'completion_pct': pct_w,
            'checked_in_today': checked_in_today,
        })

    context = {
        'supervisor_count': supervisors.count(),
        'worker_count': workers.count(),
        'project_count': projects.count(),
        'db_table_count': db_table_count,
        'today_present_count': today_present_count,
        'open_problems_count': open_problems.count(),
        'recent_problems': open_problems[:5],
        'pending_material_count': pending_material_count,
        'low_stock_count': low_stock_count,
        'material_count': material_count,
        'task_status_counts': task_status_counts,
        'recent_tasks': recent_tasks,
        'supervisor_tracking': supervisor_tracking,
        'worker_tracking': worker_tracking,
    }
    return render(request, 'core/dashboard_admin.html', context)


@supervisor_required
def supervisor_dashboard(request):
    today = timezone.localdate()
    projects = Project.objects.filter(supervisor=request.user, is_deleted=False)
    tasks = Task.objects.filter(
        project__in=projects, is_deleted=False
    ).select_related('project', 'assigned_to').order_by('deadline', '-created_at')

    pending_submissions = TaskProgressHistory.objects.filter(
        task__project__in=projects,
        status=TaskProgressHistory.Status.PENDING
    ).select_related('task', 'task__project', 'submitted_by').order_by('-created_at')

    today_present_count = Attendance.objects.filter(
        project__in=projects, attendance_date=today
    ).values('worker_id').distinct().count()

    open_problems = SiteProblemReport.objects.filter(
        project__in=projects,
        status__in=[SiteProblemReport.Status.OPEN, SiteProblemReport.Status.IN_PROGRESS],
    ).select_related('project', 'reported_by')

    low_stock_items = ProjectMaterialInventory.objects.filter(
        project__in=projects,
        available_quantity__lte=F('reorder_level'),
    ).select_related('project', 'material')

    portfolio = []
    total_tasks_all = 0
    completed_tasks_all = 0
    for p in projects:
        p_tasks = [t for t in tasks if t.project_id == p.id]
        p_workers = ProjectAssignment.objects.filter(project=p, is_active=True).select_related('worker')
        total_pt = len(p_tasks)
        done_pt = sum(1 for t in p_tasks if t.status == Task.Status.COMPLETED)
        total_tasks_all += total_pt
        completed_tasks_all += done_pt
        pct = int(round((done_pt / total_pt) * 100)) if total_pt else 0
        portfolio.append({
            'project': p,
            'workers': p_workers,
            'worker_count': p_workers.count(),
            'total_tasks': total_pt,
            'completed_tasks': done_pt,
            'pending_tasks': total_pt - done_pt,
            'completion_pct': pct,
        })

    task_rows = []
    for t in tasks:
        task_rows.append({
            'task': t,
            'pct': _calc_pct(t.cached_approved_quantity, t.assigned_quantity),
        })

    active_worker_count = ProjectAssignment.objects.filter(
        project__in=projects, is_active=True
    ).values('worker_id').distinct().count()

    overall_pct = int(round((completed_tasks_all / total_tasks_all) * 100)) if total_tasks_all else 0

    completed_worker_tasks = Task.objects.filter(status='COMPLETED').select_related('assigned_to', 'project').order_by('-id')[:30]
    context['completed_worker_tasks'] = completed_worker_tasks
    return render(request, 'core/dashboard_supervisor.html', {
        'projects': projects,
        'portfolio': portfolio,
        'task_rows': task_rows,
        'pending_submissions': pending_submissions,
        'active_worker_count': active_worker_count,
        'today_present_count': today_present_count,
        'open_problems': open_problems[:5],
        'open_problems_count': open_problems.count(),
        'low_stock_items': low_stock_items[:5],
        'low_stock_count': low_stock_items.count(),
        'total_tasks_all': total_tasks_all,
        'completed_tasks_all': completed_tasks_all,
        'overall_pct': overall_pct,
    })


@worker_required
def worker_dashboard(request):
    today = timezone.localdate()
    assignments = ProjectAssignment.objects.filter(
        worker=request.user, is_active=True, project__is_deleted=False
    ).select_related('project', 'project__supervisor')

    today_attendance = Attendance.objects.filter(
        worker=request.user, attendance_date=today
    ).select_related('project').first()

    my_tasks = Task.objects.filter(
        assigned_to=request.user, is_deleted=False
    ).select_related('project', 'assigned_by').order_by('deadline', '-created_at')

    task_cards = []
    completed_count = 0
    for t in my_tasks:
        if t.status == Task.Status.COMPLETED:
            completed_count += 1
        task_cards.append({
            'task': t,
            'pct': _calc_pct(t.cached_approved_quantity, t.assigned_quantity),
        })

    recent_submissions = TaskProgressHistory.objects.filter(
        submitted_by=request.user
    ).select_related('task', 'task__project', 'reviewed_by').order_by('-created_at')[:10]

    my_open_problems_count = SiteProblemReport.objects.filter(
        reported_by=request.user,
        status__in=[SiteProblemReport.Status.OPEN, SiteProblemReport.Status.IN_PROGRESS],
    ).count()

    return render(request, 'core/dashboard_worker.html', {
        'assignments': assignments,
        'today_attendance': today_attendance,
        'my_open_problems_count': my_open_problems_count,
        'task_cards': task_cards,
        'total_tasks': len(task_cards),
        'completed_count': completed_count,
        'pending_count': len(task_cards) - completed_count,
        'recent_submissions': recent_submissions,
    })


@login_required
def dashboard_live_stats(request):
    today = timezone.localdate()
    user = request.user
    if user.role == User.Role.ADMIN:
        all_tasks = Task.objects.filter(is_deleted=False)
        return JsonResponse({
            'role': 'ADMIN',
            'supervisor_count': User.objects.filter(role=User.Role.SUPERVISOR, is_active=True, is_deleted=False).count(),
            'worker_count': User.objects.filter(role=User.Role.WORKER, is_active=True, is_deleted=False).count(),
            'project_count': Project.objects.filter(is_deleted=False).count(),
            'today_present_count': Attendance.objects.filter(attendance_date=today).values('worker_id').distinct().count(),
            'open_problems_count': SiteProblemReport.objects.filter(status__in=['OPEN', 'IN_PROGRESS'], project__is_deleted=False).count(),
            'pending_material_count': MaterialRequest.objects.filter(approval_status='PENDING', project__is_deleted=False).count(),
            'tasks_pending': all_tasks.filter(status=Task.Status.PENDING).count(),
            'tasks_in_progress': all_tasks.filter(status=Task.Status.IN_PROGRESS).count(),
            'tasks_delayed': all_tasks.filter(status=Task.Status.DELAYED).count(),
            'tasks_completed': all_tasks.filter(status=Task.Status.COMPLETED).count(),
        })
    elif user.role == User.Role.SUPERVISOR:
        projects = Project.objects.filter(supervisor=user, is_deleted=False)
        tasks = Task.objects.filter(project__in=projects, is_deleted=False)
        total_t = tasks.count()
        done_t = tasks.filter(status=Task.Status.COMPLETED).count()
        return JsonResponse({
            'role': 'SUPERVISOR',
            'site_count': projects.count(),
            'active_worker_count': ProjectAssignment.objects.filter(project__in=projects, is_active=True).values('worker_id').distinct().count(),
            'today_present_count': Attendance.objects.filter(project__in=projects, attendance_date=today).values('worker_id').distinct().count(),
            'completed_tasks': done_t,
            'total_tasks': total_t,
            'overall_pct': int(round((done_t / total_t) * 100)) if total_t else 0,
            'pending_approvals': TaskProgressHistory.objects.filter(task__project__in=projects, status=TaskProgressHistory.Status.PENDING).count(),
            'open_problems_count': SiteProblemReport.objects.filter(project__in=projects, status__in=['OPEN', 'IN_PROGRESS']).count(),
        })
    else:
        my_tasks = Task.objects.filter(assigned_to=user, is_deleted=False)
        total_t = my_tasks.count()
        done_t = my_tasks.filter(status=Task.Status.COMPLETED).count()
        return JsonResponse({
            'role': 'WORKER',
            'site_count': ProjectAssignment.objects.filter(worker=user, is_active=True, project__is_deleted=False).count(),
            'total_tasks': total_t,
            'pending_count': total_t - done_t,
            'completed_count': done_t,
            'checked_in_today': Attendance.objects.filter(worker=user, attendance_date=today).exists(),
        })
