from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

PRIORITY_CHOICES = (
    ('alta', 'Alta'),
    ('media', 'Media'),
    ('baja', 'Baja'),
)

PRIORITY_COLORS = {
    'alta': 'danger',
    'media': 'warning',
    'baja': 'info',
}

# Orden lógico de prioridades (alfabéticamente "alta" < "baja" < "media", que no sirve)
PRIORITY_ORDER = models.Case(
    models.When(priority='alta', then=0),
    models.When(priority='media', then=1),
    models.When(priority='baja', then=2),
    default=3,
    output_field=models.IntegerField(),
)


def priority_color(priority):
    return PRIORITY_COLORS.get(priority, 'secondary')


def compute_streaks(completed_dates, today):
    """Devuelve (racha_actual, mejor_racha) a partir de un conjunto de fechas completadas.

    La racha actual sigue viva si hoy aún no se ha marcado pero ayer sí.
    """
    dates = sorted(d for d in set(completed_dates) if d <= today)
    if not dates:
        return 0, 0

    best = run = 1
    for prev, curr in zip(dates, dates[1:]):
        run = run + 1 if curr - prev == timedelta(days=1) else 1
        best = max(best, run)

    completed = set(dates)
    day = today if today in completed else today - timedelta(days=1)
    current = 0
    while day in completed:
        current += 1
        day -= timedelta(days=1)
    return current, best


class Habit(models.Model):
    """Modelo para los hábitos que el usuario quiere seguir"""
    PRIORITY_CHOICES = PRIORITY_CHOICES

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habits')
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    priority = models.CharField(max_length=5, choices=PRIORITY_CHOICES, default='media', verbose_name="Prioridad")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    order = models.IntegerField(default=0, verbose_name="Orden")
    archived = models.BooleanField(default=False, verbose_name="Archivado")

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = "Hábito"
        verbose_name_plural = "Hábitos"

    def __str__(self):
        return self.name

    def get_priority_color(self):
        return priority_color(self.priority)

    def start_date(self):
        """Primer día que cuenta para las estadísticas (creación o primer registro)."""
        created = timezone.localdate(self.created_at) if self.created_at else timezone.localdate()
        first_record = self.records.order_by('date').values_list('date', flat=True).first()
        return min(created, first_record) if first_record else created

    def completed_dates(self):
        return set(self.records.filter(completed=True).values_list('date', flat=True))

    def completion_rate(self):
        """Porcentaje de días completados desde que existe el hábito hasta hoy"""
        today = timezone.localdate()
        start = self.start_date()
        total_days = (today - start).days + 1
        if total_days <= 0:
            return 0
        completed = self.records.filter(completed=True, date__range=(start, today)).count()
        return int((completed / total_days) * 100)

    def streaks(self):
        return compute_streaks(self.completed_dates(), timezone.localdate())

    def current_streak(self):
        return self.streaks()[0]

    def best_streak(self):
        return self.streaks()[1]


class HabitRecord(models.Model):
    """Registro diario de seguimiento de hábitos"""
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='records')
    date = models.DateField(default=timezone.localdate, verbose_name="Fecha")
    completed = models.BooleanField(default=False, verbose_name="Completado")

    class Meta:
        unique_together = ('habit', 'date')
        ordering = ['-date']
        verbose_name = "Registro de hábito"
        verbose_name_plural = "Registros de hábitos"

    def __str__(self):
        return f"{self.habit.name} - {self.date.strftime('%d/%m/%Y')}"


class Task(models.Model):
    """Modelo para tareas específicas del usuario"""
    PRIORITY_CHOICES = PRIORITY_CHOICES

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=100, verbose_name="Título")
    description = models.TextField(blank=True, verbose_name="Descripción")
    priority = models.CharField(max_length=5, choices=PRIORITY_CHOICES, default='media', verbose_name="Prioridad")
    due_date = models.DateField(null=True, blank=True, verbose_name="Fecha límite")
    completed = models.BooleanField(default=False, verbose_name="Completada")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de completado")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    order = models.IntegerField(default=0, verbose_name="Orden")

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"

    def __str__(self):
        return self.title

    def get_priority_color(self):
        """Devuelve el color CSS según la prioridad"""
        return priority_color(self.priority)

    @property
    def is_overdue(self):
        return bool(self.due_date and not self.completed and self.due_date < timezone.localdate())

    @property
    def is_due_today(self):
        return bool(self.due_date and not self.completed and self.due_date == timezone.localdate())

    def mark_completed(self, completed=True):
        self.completed = completed
        self.completed_at = timezone.now() if completed else None
        self.save(update_fields=['completed', 'completed_at'])
