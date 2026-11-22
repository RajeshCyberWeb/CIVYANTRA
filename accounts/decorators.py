from functools import wraps
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect, render
from accounts.models import User


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f'{settings.LOGIN_URL}?next={request.path}')
            if not request.user.is_active or request.user.is_deleted:
                logout(request)
                return redirect(settings.LOGIN_URL)
            if request.user.role not in allowed_roles:
                return render(request, '403.html', status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def admin_required(view_func):
    return role_required(User.Role.ADMIN)(view_func)


def supervisor_required(view_func):
    return role_required(User.Role.SUPERVISOR)(view_func)


def worker_required(view_func):
    return role_required(User.Role.WORKER)(view_func)
