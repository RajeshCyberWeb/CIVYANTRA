from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render
from accounts.views import get_dashboard_url_for_role


PORTAL_META = {
    'ALL': {
        'title': 'CIVYANTRA Unified Login',
        'subtitle': 'Select your role portal below to sign in',
        'badge': 'All Portals',
        'accent': '#0B5B9E',
    },
    'ADMIN': {
        'title': 'Admin Control Login',
        'subtitle': 'Monitor supervisors, projects, and site-wide workforce progress',
        'badge': 'Admin Portal',
        'accent': '#0f172a',
    },
    'SUPERVISOR': {
        'title': 'Site Supervisor Login',
        'subtitle': 'View your portfolio, allocate tasks to workers, and verify work',
        'badge': 'Supervisor Portal',
        'accent': '#0B5B9E',
    },
    'WORKER': {
        'title': 'Worker Daily Login',
        'subtitle': 'Check tasks allocated by your supervisor and submit daily work',
        'badge': 'Worker Portal',
        'accent': '#198754',
    },
}


def role_login_view(request, portal_role='ALL'):
    if request.user.is_authenticated and request.user.is_active and not getattr(request.user, 'is_deleted', False):
        return redirect(get_dashboard_url_for_role(request.user))

    meta = PORTAL_META.get(portal_role, PORTAL_META['ALL'])
    next_url = request.GET.get('next') or request.POST.get('next', '')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, 'Invalid username or password. Please try again.')
        elif not user.is_active or getattr(user, 'is_deleted', False):
            messages.error(request, 'This account is inactive. Contact Admin.')
        elif portal_role != 'ALL' and getattr(user, 'role', '') != portal_role:
            messages.error(
                request,
                f'Access denied: "{user.username}" is registered as {user.get_role_display()}. '
                f'Please switch to the {user.get_role_display()} Login tab above.'
            )
        else:
            login(request, user)
            if next_url:
                return redirect(next_url)
            return redirect(get_dashboard_url_for_role(user))

    return render(request, 'accounts/login.html', {
        'portal_role': portal_role,
        'meta': meta,
        'next': next_url,
    })
