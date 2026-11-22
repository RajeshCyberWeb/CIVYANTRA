import re
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
from accounts.models import SupervisorProfile, User, WorkerProfile


def generate_next_supervisor_code():
    codes = SupervisorProfile.objects.values_list('supervisor_code', flat=True)
    max_num = 0
    for code in codes:
        match = re.match(r'^SUP-(\d+)$', code or '')
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f'SUP-{max_num + 1:03d}'


def generate_next_worker_code():
    codes = WorkerProfile.objects.values_list('worker_code', flat=True)
    max_num = 0
    for code in codes:
        match = re.match(r'^WRK-(\d+)$', code or '')
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f'WRK-{max_num + 1:03d}'


@transaction.atomic
def create_supervisor_account(*, username, password, first_name, last_name, email, phone_number, department, created_by):
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        role=User.Role.SUPERVISOR,
        created_by=created_by,
    )
    profile = SupervisorProfile.objects.create(
        user=user,
        supervisor_code=generate_next_supervisor_code(),
        department=department,
    )
    return user, profile


@transaction.atomic
def create_worker_account(*, username, password, first_name, last_name, email, phone_number, trade_skill, pin, rfid_card_uid, created_by):
    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        role=User.Role.WORKER,
        created_by=created_by,
    )
    profile = WorkerProfile.objects.create(
        user=user,
        worker_code=generate_next_worker_code(),
        trade_skill=trade_skill,
        attendance_pin_hash=make_password(pin),
        rfid_card_uid=rfid_card_uid or None,
    )
    return user, profile


def reset_worker_pin(worker_profile, new_pin):
    worker_profile.attendance_pin_hash = make_password(new_pin)
    worker_profile.failed_pin_attempts = 0
    worker_profile.pin_locked_until = None
    worker_profile.pin_updated_at = timezone.now()
    worker_profile.save(update_fields=[
        'attendance_pin_hash',
        'failed_pin_attempts',
        'pin_locked_until',
        'pin_updated_at',
        'updated_at',
    ])
