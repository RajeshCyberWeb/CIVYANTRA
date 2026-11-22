from django import forms
from accounts.models import User
from .models import Project, ProjectAssignment, ProjectHoliday, Task, TaskDelayReport, TaskProgressHistory, TaskQuantityAdjustment


class ProjectForm(forms.ModelForm):
    MON = forms.BooleanField(required=False, initial=True, label='Mon')
    TUE = forms.BooleanField(required=False, initial=True, label='Tue')
    WED = forms.BooleanField(required=False, initial=True, label='Wed')
    THU = forms.BooleanField(required=False, initial=True, label='Thu')
    FRI = forms.BooleanField(required=False, initial=True, label='Fri')
    SAT = forms.BooleanField(required=False, initial=True, label='Sat')
    SUN = forms.BooleanField(required=False, initial=False, label='Sun')

    class Meta:
        model = Project
        fields = ['name', 'location', 'description', 'supervisor', 'start_date', 'expected_end_date', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'supervisor': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supervisor'].queryset = User.objects.filter(role=User.Role.SUPERVISOR, is_active=True)
        if self.instance and self.instance.pk:
            raw_mask = self.instance.working_days_mask
            try:
                mask = int(raw_mask) if raw_mask not in (None, '') else 63
            except (ValueError, TypeError):
                mask = 63
            for idx, day in enumerate(['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']):
                self.fields[day].initial = bool(mask & (1 << idx))

    def get_working_days_mask(self):
        mask = 0
        for idx, day in enumerate(['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']):
            if self.cleaned_data.get(day):
                mask |= (1 << idx)
        return mask or 63


class ProjectAssignmentForm(forms.ModelForm):
    class Meta:
        model = ProjectAssignment
        fields = ['worker', 'assigned_date', 'notes']
        widgets = {
            'worker': forms.Select(attrs={'class': 'form-select'}),
            'assigned_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional note'}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(role=User.Role.WORKER, is_active=True)
        if project:
            assigned_ids = ProjectAssignment.objects.filter(project=project, is_active=True).values_list('worker_id', flat=True)
            qs = qs.exclude(id__in=assigned_ids)
        self.fields['worker'].queryset = qs


class ProjectHolidayForm(forms.ModelForm):
    class Meta:
        model = ProjectHoliday
        fields = ['holiday_date', 'title']
        widgets = {
            'holiday_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Republic Day'}),
        }


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['assigned_to', 'title', 'category', 'unit', 'assigned_quantity', 'priority', 'deadline', 'description']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Ground Floor Brickwork'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Masonry / Electrical'}),
            'unit': forms.Select(attrs={'class': 'form-select'}),
            'assigned_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(role=User.Role.WORKER, is_active=True)
        if project:
            active_ids = ProjectAssignment.objects.filter(project=project, is_active=True).values_list('worker_id', flat=True)
            qs = qs.filter(id__in=active_ids)
        self.fields['assigned_to'].queryset = qs


class TaskProgressForm(forms.ModelForm):
    class Meta:
        model = TaskProgressHistory
        fields = ['work_date', 'quantity_submitted', 'proof_photo', 'remarks']
        widgets = {
            'work_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'quantity_submitted': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'proof_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'remarks': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Describe completed work'}),
        }


class TaskQuantityAdjustmentForm(forms.ModelForm):
    class Meta:
        model = TaskQuantityAdjustment
        fields = ['new_quantity', 'reason']
        widgets = {
            'new_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for target change'}),
        }


class TaskDelayReportForm(forms.ModelForm):
    class Meta:
        model = TaskDelayReport
        fields = ['expected_completion_date', 'reason']
        widgets = {
            'expected_completion_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Material shortage, weather, etc.'}),
        }
