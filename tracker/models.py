from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Habit(models.Model):
    """Modelo para los hábitos que el usuario quiere seguir"""
    PRIORITY_CHOICES = (
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habits')
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    priority = models.CharField(max_length=5, choices=PRIORITY_CHOICES, default='media', verbose_name="Prioridad")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    order = models.IntegerField(default=0, verbose_name="Orden")
    
    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = "Hábito"
        verbose_name_plural = "Hábitos"
        
    def __str__(self):
        return self.name
        
    def completion_rate(self):
        """Calcula el porcentaje de días completados"""
        total_records = self.habitrecord_set.count()
        if total_records == 0:
            return 0
        completed = self.habitrecord_set.filter(completed=True).count()
        return int((completed / total_records) * 100)

class HabitRecord(models.Model):
    """Registro diario de seguimiento de hábitos"""
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now, verbose_name="Fecha")
    completed = models.BooleanField(default=False, verbose_name="Completado")
    
    class Meta:
        unique_together = ('habit', 'date')
        verbose_name = "Registro de hábito"
        verbose_name_plural = "Registros de hábitos"
        
    def __str__(self):
        return f"{self.habit.name} - {self.date.strftime('%d/%m/%Y')}"

class Task(models.Model):
    """Modelo para tareas específicas del usuario"""
    PRIORITY_CHOICES = (
        ('alta', 'Alta'),
        ('media', 'Media'),
        ('baja', 'Baja'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=100, verbose_name="Título")
    description = models.TextField(blank=True, verbose_name="Descripción")
    priority = models.CharField(max_length=5, choices=PRIORITY_CHOICES, default='media', verbose_name="Prioridad")
    due_date = models.DateField(null=True, blank=True, verbose_name="Fecha límite")
    completed = models.BooleanField(default=False, verbose_name="Completada")
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
        priority_colors = {
            'alta': 'danger',
            'media': 'warning',
            'baja': 'info',
        }
        return priority_colors.get(self.priority, 'secondary')