from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Notification
from operations.models import MaterialRequest, SiteProblemReport
from projects.models import ProjectAssignment, Task, TaskDelayReport

User = get_user_model()


def _notify(recipient, title, message, category="GENERAL", link_url="/"):
    if not recipient:
        return
    # Avoid duplicate identical unread notifications
    if Notification.objects.filter(
        recipient=recipient, title=title, message=message, is_read=False
    ).exists():
        return
    Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        category=category,
        link_url=link_url,
    )


def _get_admins_and_supervisor(project=None):
    recipients = list(User.objects.filter(role="ADMIN", is_active=True, is_deleted=False))
    if project and getattr(project, "supervisor", None):
        if project.supervisor not in recipients:
            recipients.append(project.supervisor)
    return recipients


@receiver(post_save, sender=ProjectAssignment)
def notify_worker_on_project_assignment(sender, instance, created, **kwargs):
    if created and instance.is_active and instance.worker:
        assigner = instance.assigned_by.get_full_name() or instance.assigned_by.username if instance.assigned_by else "Admin/Supervisor"
        _notify(
            recipient=instance.worker,
            title=f"Assigned to Site: {instance.project.name}",
            message=f"{assigner} assigned you ({instance.worker.get_full_name() or instance.worker.username}) to site {instance.project.name} ({instance.project.project_code}).",
            category="PROJECT",
            link_url="/",
        )


@receiver(post_save, sender=Task)
def notify_worker_on_task_assigned(sender, instance, created, **kwargs):
    if created and instance.assigned_to and not instance.is_deleted:
        assigner = instance.assigned_by.get_full_name() or instance.assigned_by.username if instance.assigned_by else "Supervisor"
        qty_info = f" ({instance.assigned_quantity} {instance.unit})" if instance.assigned_quantity else ""
        _notify(
            recipient=instance.assigned_to,
            title=f"New Task Assigned: {instance.title}",
            message=f"{assigner} assigned you '{instance.title}'{qty_info} on site {instance.project.name}.",
            category="TASK",
            link_url="/",
        )


@receiver(post_save, sender=MaterialRequest)
def notify_worker_on_material_update(sender, instance, created, **kwargs):
    if not instance.requested_by:
        return
    worker = instance.requested_by
    if getattr(worker, "role", "") == "WORKER":
        item_name = instance.material.name if instance.material else instance.request_code
        if created:
            _notify(
                recipient=worker,
                title=f"Material Item Logged: {item_name}",
                message=f"Material entry '{item_name}' ({instance.required_quantity}) was added under your name for {instance.project.name}.",
                category="MATERIAL",
                link_url="/",
            )
        elif instance.approval_status in ("APPROVED", "REJECTED"):
            _notify(
                recipient=worker,
                title=f"Material {instance.approval_status.title()}: {item_name}",
                message=f"Your material item '{item_name}' for {instance.project.name} is now {instance.approval_status}.",
                category="MATERIAL",
                link_url="/",
            )


@receiver(post_save, sender=SiteProblemReport)
def notify_admins_and_supervisor_on_complaint(sender, instance, created, **kwargs):
    if created:
        reporter = instance.reported_by.get_full_name() or instance.reported_by.username if instance.reported_by else "Worker"
        site_name = instance.project.name if instance.project else "Site"
        title = f"Worker Complaint / Issue [{instance.severity}]: {instance.title}"
        message = f"{reporter} filed report {instance.problem_code} on {site_name}: {instance.description[:140]}"
        for recipient in _get_admins_and_supervisor(instance.project):
            _notify(
                recipient=recipient,
                title=title,
                message=message,
                category="ISSUE",
                link_url="/",
            )


@receiver(post_save, sender=TaskDelayReport)
def notify_admins_and_supervisor_on_delay(sender, instance, created, **kwargs):
    if created:
        reporter = instance.reported_by.get_full_name() or instance.reported_by.username if instance.reported_by else "Worker"
        project = instance.task.project if instance.task else None
        title = f"Task Delay Reported: {instance.task.title}"
        message = f"{reporter} reported a delay on '{instance.task.title}': {instance.reason[:140]}"
        for recipient in _get_admins_and_supervisor(project):
            _notify(
                recipient=recipient,
                title=title,
                message=message,
                category="ISSUE",
                link_url="/",
            )
