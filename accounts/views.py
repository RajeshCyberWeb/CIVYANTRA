from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.decorators import admin_required, role_required
from accounts.forms import SupervisorCreateForm, UserEditForm, WorkerCreateForm, WorkerPinResetForm
from accounts.models import User
from accounts.services import create_supervisor_account, create_worker_account, reset_worker_pin
from core.utils import log_audit


def get_dashboard_url_for_role(user):
    if user.role == User.Role.ADMIN:
        return 'core:admin_dashboard'
    if user.role == User.Role.SUPERVISOR:
        return 'core:supervisor_dashboard'
    return 'core:worker_dashboard'


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_active and not request.user.is_deleted:
            return redirect(get_dashboard_url_for_role(request.user))
        logout(request)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active or user.is_deleted:
                messages.error(request, 'This account has been deactivated. Contact your Administrator.')
            else:
                login(request, user)
                log_audit(user, 'USER_LOGIN', 'User', user.id, f'{user.username} logged in.', request)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect(get_dashboard_url_for_role(user))
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'accounts/login.html', {'next': request.GET.get('next', '')})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        log_audit(request.user, 'USER_LOGOUT', 'User', request.user.id, f'{request.user.username} logged out.', request)
        logout(request)
        messages.success(request, 'You have been logged out securely.')
    return redirect('accounts:login')


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
def user_list_view(request):
    role_filter = request.GET.get('role', 'ALL').upper()
    query = request.GET.get('q', '').strip()
    users = User.objects.select_related('supervisor_profile', 'worker_profile').all()

    if request.user.role == User.Role.SUPERVISOR:
        users = users.filter(role=User.Role.WORKER)
        role_filter = User.Role.WORKER
    elif role_filter in (User.Role.ADMIN, User.Role.SUPERVISOR, User.Role.WORKER):
        users = users.filter(role=role_filter)

    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(supervisor_profile__supervisor_code__icontains=query)
            | Q(worker_profile__worker_code__icontains=query)
        )

    context = {
        'users': users,
        'role_filter': role_filter,
        'query': query,
    }
    return render(request, 'accounts/user_list.html', context)


@admin_required
def create_supervisor_view(request):
    if request.method == 'POST':
        form = SupervisorCreateForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user, profile = create_supervisor_account(
                username=cd['username'],
                password=cd['password'],
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                email=cd['email'],
                phone_number=cd['phone_number'],
                department=cd['department'],
                created_by=request.user,
            )
            log_audit(request.user, 'CREATE_SUPERVISOR', 'User', user.id, f'Created supervisor {profile.supervisor_code} ({user.username}).', request)
            messages.success(request, f'Supervisor {user.get_display_name()} created with ID {profile.supervisor_code}.')
            return redirect('accounts:user_list')
    else:
        form = SupervisorCreateForm()
    return render(request, 'accounts/create_supervisor.html', {'form': form})


@admin_required
def create_worker_view(request):
    if request.method == 'POST':
        form = WorkerCreateForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            user, profile = create_worker_account(
                username=cd['username'],
                password=cd['password'],
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                email=cd['email'],
                phone_number=cd['phone_number'],
                trade_skill=cd['trade_skill'],
                pin=cd['attendance_pin'],
                rfid_card_uid=cd['rfid_card_uid'],
                created_by=request.user,
            )
            log_audit(request.user, 'CREATE_WORKER', 'User', user.id, f'Created worker {profile.worker_code} ({user.username}).', request)
            messages.success(request, f'Worker {user.get_display_name()} created with Permanent ID {profile.worker_code}.')
            return redirect('accounts:user_list')
    else:
        form = WorkerCreateForm()
    return render(request, 'accounts/create_worker.html', {'form': form})


@admin_required
def edit_user_view(request, user_id):
    target_user = get_object_or_404(User.objects.select_related('supervisor_profile', 'worker_profile'), pk=user_id)
    initial = {
        'first_name': target_user.first_name,
        'last_name': target_user.last_name,
        'email': target_user.email,
        'phone_number': target_user.phone_number,
        'department': getattr(getattr(target_user, 'supervisor_profile', None), 'department', ''),
        'trade_skill': getattr(getattr(target_user, 'worker_profile', None), 'trade_skill', ''),
        'rfid_card_uid': getattr(getattr(target_user, 'worker_profile', None), 'rfid_card_uid', '') or '',
    }
    if request.method == 'POST':
        form = UserEditForm(request.POST, user_obj=target_user)
        if form.is_valid():
            cd = form.cleaned_data
            target_user.first_name = cd['first_name']
            target_user.last_name = cd['last_name']
            target_user.email = cd['email']
            target_user.phone_number = cd['phone_number']
            target_user.save(update_fields=['first_name', 'last_name', 'email', 'phone_number', 'updated_at'])

            if hasattr(target_user, 'supervisor_profile'):
                sp = target_user.supervisor_profile
                sp.department = cd['department']
                sp.save(update_fields=['department', 'updated_at'])
            elif hasattr(target_user, 'worker_profile'):
                wp = target_user.worker_profile
                wp.trade_skill = cd['trade_skill']
                wp.rfid_card_uid = cd['rfid_card_uid'] or None
                wp.save(update_fields=['trade_skill', 'rfid_card_uid', 'updated_at'])

            log_audit(request.user, 'EDIT_USER', 'User', target_user.id, f'Updated profile for {target_user.username}.', request)
            messages.success(request, f'Updated profile for {target_user.get_display_name()}.')
            return redirect('accounts:user_list')
    else:
        form = UserEditForm(initial=initial, user_obj=target_user)
    return render(request, 'accounts/user_edit.html', {'form': form, 'target_user': target_user})


@admin_required
@require_POST
def toggle_user_status_view(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    if target_user.pk == request.user.pk:
        messages.error(request, 'You cannot deactivate your own Admin account.')
        return redirect('accounts:user_list')

    if target_user.is_active and not target_user.is_deleted:
        target_user.is_active = False
        target_user.is_deleted = True
        target_user.deleted_at = timezone.now()
        action_label = 'DEACTIVATE_USER'
        msg = f'{target_user.get_display_name()} has been deactivated.'
    else:
        target_user.is_active = True
        target_user.is_deleted = False
        target_user.deleted_at = None
        action_label = 'REACTIVATE_USER'
        msg = f'{target_user.get_display_name()} has been reactivated.'

    target_user.save(update_fields=['is_active', 'is_deleted', 'deleted_at', 'updated_at'])
    log_audit(request.user, action_label, 'User', target_user.id, msg, request)
    messages.success(request, msg)
    return redirect('accounts:user_list')


@admin_required
def reset_worker_pin_view(request, user_id):
    target_user = get_object_or_404(User.objects.select_related('worker_profile'), pk=user_id, role=User.Role.WORKER)
    worker_profile = target_user.worker_profile
    if request.method == 'POST':
        form = WorkerPinResetForm(request.POST)
        if form.is_valid():
            reset_worker_pin(worker_profile, form.cleaned_data['new_pin'])
            log_audit(request.user, 'RESET_WORKER_PIN', 'WorkerProfile', worker_profile.id, f'Reset Smart Tab PIN for {worker_profile.worker_code}.', request)
            messages.success(request, f'4-digit Smart Tab PIN reset for {worker_profile.worker_code} ({target_user.get_display_name()}).')
            return redirect('accounts:user_list')
    else:
        form = WorkerPinResetForm()
    return render(request, 'accounts/reset_pin.html', {'form': form, 'target_user': target_user, 'worker_profile': worker_profile})


@role_required(User.Role.ADMIN, User.Role.SUPERVISOR)
@require_POST
def delete_user_view(request, user_id):
    from django.db import transaction
    from accounts.models import SupervisorProfile, WorkerProfile
    from core.models import AuditLog, Notification
    from operations.models import Attendance, Material, MaterialRequest, SiteProblemReport, StockTransaction
    from projects.models import (
        Project, ProjectAssignment, ProjectHoliday,
        Task, TaskDelayReport, TaskProgressHistory, TaskQuantityAdjustment,
    )

    target_user = get_object_or_404(User, pk=user_id)
    if target_user.pk == request.user.pk or target_user.role == User.Role.ADMIN:
        messages.error(request, 'Admin accounts cannot be deleted here.')
        return redirect('accounts:user_list')
    if request.user.role == User.Role.SUPERVISOR and target_user.role != User.Role.WORKER:
        messages.error(request, 'Supervisors can only delete Worker accounts.')
        return redirect('accounts:user_list')
    if Project.objects.filter(supervisor=target_user).exists():
        messages.error(request, 'Reassign this supervisor from active projects before deleting their account.')
        return redirect('accounts:user_list')

    display_name = target_user.get_display_name()
    username = target_user.username

    with transaction.atomic():
        User.objects.filter(created_by=target_user).update(created_by=None)
        AuditLog.objects.filter(actor=target_user).update(actor=None)
        Notification.objects.filter(recipient=target_user).delete()

        Attendance.objects.filter(worker=target_user).delete()
        Attendance.objects.filter(regularized_by=target_user).update(regularized_by=None)

        ProjectAssignment.objects.filter(worker=target_user).delete()
        ProjectAssignment.objects.filter(assigned_by=target_user).update(assigned_by=request.user)

        worker_tasks = Task.objects.filter(assigned_to=target_user)
        TaskProgressHistory.objects.filter(task__in=worker_tasks).delete()
        TaskQuantityAdjustment.objects.filter(task__in=worker_tasks).delete()
        TaskDelayReport.objects.filter(task__in=worker_tasks).delete()
        worker_tasks.delete()

        Task.objects.filter(assigned_by=target_user).update(assigned_by=request.user)
        TaskProgressHistory.objects.filter(submitted_by=target_user).update(submitted_by=request.user)
        TaskProgressHistory.objects.filter(reviewed_by=target_user).update(reviewed_by=None)
        TaskQuantityAdjustment.objects.filter(adjusted_by=target_user).update(adjusted_by=request.user)
        TaskDelayReport.objects.filter(reported_by=target_user).update(reported_by=request.user)
        TaskDelayReport.objects.filter(acknowledged_by=target_user).update(acknowledged_by=None)

        Project.objects.filter(created_by=target_user).update(created_by=request.user)
        ProjectHoliday.objects.filter(created_by=target_user).update(created_by=request.user)

        Material.objects.filter(created_by=target_user).update(created_by=request.user)
        MaterialRequest.objects.filter(requested_by=target_user).update(requested_by=request.user)
        MaterialRequest.objects.filter(reviewed_by=target_user).update(reviewed_by=None)
        StockTransaction.objects.filter(performed_by=target_user).update(performed_by=request.user)
        SiteProblemReport.objects.filter(reported_by=target_user).update(reported_by=request.user)
        SiteProblemReport.objects.filter(resolved_by=target_user).update(resolved_by=None)

        WorkerProfile.objects.filter(user=target_user).delete()
        SupervisorProfile.objects.filter(user=target_user).delete()
        target_user.delete()

    log_audit(request.user, 'DELETE_USER', 'User', user_id, f'Deleted user {username} ({display_name}).', request)
    messages.success(request, f'Worker "{display_name}" has been permanently deleted.')
    next_url = request.POST.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('accounts:user_list')
