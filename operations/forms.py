from django import forms
from .models import Attendance, Material, MaterialRequest, SiteProblemReport


class AttendanceCheckInForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['project', 'worker', 'verification_method']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'worker': forms.Select(attrs={'class': 'form-select'}),
            'verification_method': forms.Select(attrs={'class': 'form-select'}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'category', 'unit', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. OPC 53 Grade Cement'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Binding Material'}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Bags, Tons, Kg'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MaterialRequestForm(forms.ModelForm):
    class Meta:
        model = MaterialRequest
        fields = ['project', 'material', 'problem_type', 'required_quantity', 'description', 'photo']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'material': forms.Select(attrs={'class': 'form-select'}),
            'problem_type': forms.Select(attrs={'class': 'form-select'}),
            'required_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }


class SiteProblemForm(forms.ModelForm):
    class Meta:
        model = SiteProblemReport
        fields = ['project', 'title', 'severity', 'description', 'photo']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Short summary of the site issue'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
