from django.contrib.auth import logout
from django.shortcuts import redirect


class KioskIsolationMiddleware:
    COOKIE_NAME = 'mcm_kiosk_device'
    ALLOWED_PREFIXES = ('/kiosk/', '/static/', '/media/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.COOKIES.get(self.COOKIE_NAME):
            if request.user.is_authenticated:
                logout(request)
            if not request.path.startswith(self.ALLOWED_PREFIXES):
                return redirect('/kiosk/')
        return self.get_response(request)
