from django.apps import apps

def _write_audit(user, action, description=''):
    AuditModel = apps.get_model('core', 'AuditLog')
    field_names = {f.name for f in AuditModel._meta.fields}
    kwargs = {}
    if 'actor' in field_names:
        kwargs['actor'] = user if getattr(user, 'is_authenticated', False) else None
    elif 'user' in field_names:
        kwargs['user'] = user if getattr(user, 'is_authenticated', False) else None
    if 'action' in field_names:
        kwargs['action'] = action
    elif 'action_type' in field_names:
        kwargs['action_type'] = action
    if 'details' in field_names:
        kwargs['details'] = description
    elif 'description' in field_names:
        kwargs['description'] = description
    AuditModel.objects.create(**kwargs)

def log_audit(*args, **kwargs):
    if len(args) >= 2:
        user, action = args[0], args[1]
        desc = args[2] if len(args) > 2 else kwargs.get('details', kwargs.get('description', ''))
        _write_audit(user, action, desc)

def log_action(user, action_type, description=''):
    _write_audit(user, action_type, description)

def notify_user(user, message, title='Notification'):
    if not user:
        return
    NotifModel = apps.get_model('core', 'Notification')
    field_names = {f.name for f in NotifModel._meta.fields}
    kwargs = {}
    if 'recipient' in field_names:
        kwargs['recipient'] = user
    elif 'user' in field_names:
        kwargs['user'] = user
    if 'title' in field_names:
        kwargs['title'] = title
    if 'message' in field_names:
        kwargs['message'] = message
    NotifModel.objects.create(**kwargs)
