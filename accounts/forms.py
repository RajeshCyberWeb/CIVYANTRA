import re
from django import forms
from accounts.models import User, WorkerProfile


class BaseUserCreateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. rahul.sharma'}),
    )
    first_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
    )
    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 9876543210'}),
    )
    password = forms.CharField(
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Minimum 6 characters'}),
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username


class SupervisorCreateForm(BaseUserCreateForm):
    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Civil & Structural'}),
    )


class WorkerCreateForm(BaseUserCreateForm):
    trade_skill = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mason, Electrician, Plumber'}),
    )
    attendance_pin = forms.CharField(
        min_length=4,
        max_length=4,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'maxlength': '4', 'placeholder': '4-digit Smart Tab PIN'}),
    )
    rfid_card_uid = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional RFID Card UID'}),
    )

    def clean_attendance_pin(self):
        pin = self.cleaned_data['attendance_pin'].strip()
        if not re.match(r'^\d{4}$', pin):
            raise forms.ValidationError('Attendance PIN must be exactly 4 numeric digits (0-9).')
        return pin

    def clean_rfid_card_uid(self):
        uid = self.cleaned_data.get('rfid_card_uid', '').strip()
        if uid and WorkerProfile.objects.filter(rfid_card_uid=uid).exists():
            raise forms.ValidationError('This RFID Card UID is already assigned to another worker.')
        return uid


class UserEditForm(forms.Form):
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone_number = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    department = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    trade_skill = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    rfid_card_uid = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, user_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_obj = user_obj

    def clean_rfid_card_uid(self):
        uid = self.cleaned_data.get('rfid_card_uid', '').strip()
        if uid and self.user_obj and hasattr(self.user_obj, 'worker_profile'):
            qs = WorkerProfile.objects.filter(rfid_card_uid=uid).exclude(pk=self.user_obj.worker_profile.pk)
            if qs.exists():
                raise forms.ValidationError('This RFID Card UID is already assigned to another worker.')
        return uid


class WorkerPinResetForm(forms.Form):
    new_pin = forms.CharField(
        min_length=4,
        max_length=4,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'maxlength': '4', 'placeholder': 'Enter new 4-digit PIN'}),
    )
    confirm_pin = forms.CharField(
        min_length=4,
        max_length=4,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'maxlength': '4', 'placeholder': 'Re-enter 4-digit PIN'}),
    )

    def clean(self):
        cleaned = super().clean()
        pin1 = cleaned.get('new_pin', '').strip()
        pin2 = cleaned.get('confirm_pin', '').strip()
        if pin1 and not re.match(r'^\d{4}$', pin1):
            self.add_error('new_pin', 'PIN must be exactly 4 numeric digits.')
        if pin1 and pin2 and pin1 != pin2:
            self.add_error('confirm_pin', 'PINs do not match.')
        return cleaned


# --- CIVYANTRA Input Limits & Validation ---
from django.core.exceptions import ValidationError as _ValidationError
from django.core.validators import MaxLengthValidator as _MaxLen, MinLengthValidator as _MinLen

def _apply_civyantra_field_rules(form_cls):
    orig_init = form_cls.__init__

    def new_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        for fname in ('username', 'first_name', 'last_name'):
            if fname in self.fields:
                field = self.fields[fname]
                field.max_length = 25
                field.validators = [v for v in field.validators if not isinstance(v, _MaxLen)] + [_MaxLen(25)]
                field.widget.attrs.update({
                    'maxlength': '25',
                    'oninput': 'this.value=this.value.slice(0,25);',
                })
        if 'phone_number' in self.fields:
            pfield = self.fields['phone_number']
            pfield.max_length = 10
            pfield.min_length = 10
            pfield.validators = [v for v in pfield.validators if not isinstance(v, (_MaxLen, _MinLen))] + [_MaxLen(10), _MinLen(10)]
            pfield.widget.attrs.update({
                'maxlength': '10',
                'minlength': '10',
                'pattern': '[0-9]{10}',
                'inputmode': 'numeric',
                'placeholder': '10-digit mobile number',
                'oninput': 'this.value=this.value.replace(/[^0-9]/g,"").slice(0,10);',
            })

    def clean_username(self):
        val = (self.cleaned_data.get('username') or '').strip()
        if len(val) > 25:
            raise _ValidationError('Username cannot exceed 25 characters.')
        return val

    def clean_first_name(self):
        val = (self.cleaned_data.get('first_name') or '').strip()
        if len(val) > 25:
            raise _ValidationError('First name cannot exceed 25 characters.')
        return val

    def clean_last_name(self):
        val = (self.cleaned_data.get('last_name') or '').strip()
        if len(val) > 25:
            raise _ValidationError('Last name cannot exceed 25 characters.')
        return val

    def clean_phone_number(self):
        val = (self.cleaned_data.get('phone_number') or '').strip()
        if not val and not self.fields['phone_number'].required:
            return val
        if not val.isdigit() or len(val) != 10:
            raise _ValidationError('Phone number must be exactly 10 digits (numbers only).')
        return val

    form_cls.__init__ = new_init
    if not hasattr(form_cls, 'clean_username'):
        form_cls.clean_username = clean_username
    if not hasattr(form_cls, 'clean_first_name'):
        form_cls.clean_first_name = clean_first_name
    if not hasattr(form_cls, 'clean_last_name'):
        form_cls.clean_last_name = clean_last_name
    form_cls.clean_phone_number = clean_phone_number

for _obj in list(globals().values()):
    if isinstance(_obj, type) and issubclass(_obj, forms.BaseForm) and _obj is not forms.BaseForm:
        _apply_civyantra_field_rules(_obj)
