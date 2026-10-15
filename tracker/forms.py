from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import PRIORITY_CHOICES, Habit, Task

MAX_REPORT_DAYS = 366


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(label="Correo electrónico")

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email


class HabitForm(forms.ModelForm):
    class Meta:
        model = Habit
        fields = ['name', 'description', 'priority']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Ej. Leer 20 minutos', 'autofocus': True}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Ej. Entregar informe'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def clean_title(self):
        return self.cleaned_data['title'].strip()

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        # Solo se impide una fecha pasada al crear o al cambiar la fecha
        changed = self.instance.pk is None or due_date != self.instance.due_date
        if due_date and changed and due_date < timezone.localdate():
            raise forms.ValidationError("La fecha límite no puede estar en el pasado.")
        return due_date


class TaskFilterForm(forms.Form):
    STATUS_CHOICES = (
        ('', 'Todas'),
        ('overdue', 'Vencidas'),
        ('today', 'Para hoy'),
        ('upcoming', 'Próximas'),
        ('no_date', 'Sin fecha'),
    )

    q = forms.CharField(required=False, label="Buscar",
                        widget=forms.TextInput(attrs={'placeholder': 'Buscar tareas...'}))
    priority = forms.ChoiceField(required=False, label="Prioridad",
                                 choices=(('', 'Todas'),) + PRIORITY_CHOICES)
    status = forms.ChoiceField(required=False, label="Estado", choices=STATUS_CHOICES)


class DateRangeForm(forms.Form):
    start_date = forms.DateField(label="Desde", widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    end_date = forms.DateField(label="Hasta", widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date:
            if start_date > end_date:
                raise forms.ValidationError("La fecha inicial debe ser anterior o igual a la fecha final.")
            if (end_date - start_date).days + 1 > MAX_REPORT_DAYS:
                raise forms.ValidationError(f"El rango máximo es de {MAX_REPORT_DAYS} días.")
        return cleaned_data
