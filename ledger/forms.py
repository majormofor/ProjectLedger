from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Project, Subproject

class RegisterForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].help_text = 'Use at least 8 characters; avoid a common password.'
        self.fields['password2'].help_text = ''
        self.fields['username'].help_text = ''

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'client', 'location']
        labels = {'name': 'Project name', 'client': 'Client name', 'location': 'Location (optional)'}
        widgets = {'name': forms.TextInput(attrs={'placeholder': 'e.g. Building a house'}), 'client': forms.TextInput(attrs={'placeholder': 'e.g. Chidi Okeke'}), 'location': forms.TextInput(attrs={'placeholder': 'e.g. Lekki, Lagos'})}

class SubprojectForm(forms.ModelForm):
    cost_type = forms.ChoiceField(label='Type', choices=[('', 'Choose type'), ('labour', 'Labour'), ('material', 'Material')])
    class Meta:
        model = Subproject
        fields = ['name', 'cost_type', 'cost', 'paid', 'expected_date']
        labels = {'name': 'Subproject name'}
        widgets = {'name': forms.TextInput(attrs={'placeholder': 'e.g. Foundation'}), 'cost': forms.NumberInput(attrs={'placeholder': '0.00', 'min': '0', 'step': '.01'}), 'paid': forms.NumberInput(attrs={'placeholder': '0.00', 'min': '0', 'step': '.01'}), 'expected_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')}

class PaidAmountForm(forms.ModelForm):
    class Meta:
        model = Subproject
        fields = ['paid']
        widgets = {'paid': forms.NumberInput(attrs={'min': '0', 'step': '.01'})}
