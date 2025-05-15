from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
import json
from .models import Habit, HabitRecord, Task
from .forms import UserRegisterForm, HabitForm, TaskForm, DateRangeForm

def register(request):
    """Vista de registro de usuario"""
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'¡Cuenta creada para {username}! Ahora puedes iniciar sesión.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'tracker/register.html', {'form': form})

@login_required
def dashboard(request):
    """Vista principal del dashboard"""
    today = timezone.now().date()
    
    # Obtener todas las tareas no completadas del usuario
    tasks = Task.objects.filter(user=request.user, completed=False).order_by('order', 'priority')
    
    # Obtener todos los hábitos del usuario
    habits = Habit.objects.filter(user=request.user).order_by('order')
    
    # Preparar los registros de hábitos para la semana actual
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    
    habit_records = {}
    for habit in habits:
        habit_records[habit.id] = {}
        for day in week_days:
            try:
                record = HabitRecord.objects.get(habit=habit, date=day)
                habit_records[habit.id][day] = record.completed
            except HabitRecord.DoesNotExist:
                # Crear un registro vacío para este día
                record = HabitRecord(habit=habit, date=day, completed=False)
                record.save()
                habit_records[habit.id][day] = False
    
    # Calcular estadísticas
    completed_tasks = Task.objects.filter(user=request.user, completed=True).count()
    total_tasks = completed_tasks + tasks.count()
    task_completion_rate = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    
    # Calcular tasas de completado para cada hábito
    habit_completion_rates = {}
    for habit in habits:
        completed_days = HabitRecord.objects.filter(habit=habit, completed=True).count()
        total_days = HabitRecord.objects.filter(habit=habit).count()
        habit_completion_rates[habit.id] = int((completed_days / total_days) * 100) if total_days > 0 else 0
    
    context = {
        'tasks': tasks,
        'habits': habits,
        'week_days': week_days,
        'habit_records': habit_records,
        'task_completion_rate': task_completion_rate,
        'habit_completion_rates': habit_completion_rates,
        'today': today,
    }
    
    return render(request, 'tracker/dashboard.html', context)

@login_required
def habit_list(request):
    """Vista para gestionar hábitos"""
    habits = Habit.objects.filter(user=request.user).order_by('order')
    
    if request.method == 'POST':
        form = HabitForm(request.POST)
        if form.is_valid():
            habit = form.save(commit=False)
            habit.user = request.user
            habit.save()
            messages.success(request, 'Hábito añadido correctamente.')
            return redirect('habit_list')
    else:
        form = HabitForm()
    
    context = {
        'habits': habits,
        'form': form,
    }
    
    return render(request, 'tracker/habit_list.html', context)

@login_required
def edit_habit(request, habit_id):
    """Vista para editar un hábito"""
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    
    if request.method == 'POST':
        form = HabitForm(request.POST, instance=habit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Hábito actualizado correctamente.')
            return redirect('habit_list')
    else:
        form = HabitForm(instance=habit)
    
    context = {
        'form': form,
        'habit': habit,
    }
    
    return render(request, 'tracker/edit_habit.html', context)

@login_required
def delete_habit(request, habit_id):
    """Vista para eliminar un hábito"""
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    
    if request.method == 'POST':
        habit.delete()
        messages.success(request, 'Hábito eliminado correctamente.')
        return redirect('habit_list')
    
    context = {
        'habit': habit,
    }
    
    return render(request, 'tracker/delete_habit.html', context)
@login_required
def toggle_habit_record(request, record_id):
    """Vista para marcar/desmarcar un registro de hábito"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            record = get_object_or_404(HabitRecord, id=record_id, habit__user=request.user)
            
            # Parsear el cuerpo de la solicitud JSON
            data = json.loads(request.body)
            completed = data.get('completed', False)
            
            # Actualizar el estado del registro
            record.completed = completed
            record.save()
            
            return JsonResponse({'status': 'success', 'completed': record.completed})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def task_list(request):
    """Vista para gestionar tareas"""
    tasks = Task.objects.filter(user=request.user, completed=False).order_by('order', 'priority')
    completed_tasks = Task.objects.filter(user=request.user, completed=True).order_by('-created_at')[:5]
    
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, 'Tarea añadida correctamente.')
            return redirect('task_list')
    else:
        form = TaskForm()
    
    context = {
        'tasks': tasks,
        'completed_tasks': completed_tasks,
        'form': form,
    }
    
    return render(request, 'tracker/task_list.html', context)

@login_required
def edit_task(request, task_id):
    """Vista para editar una tarea"""
    task = get_object_or_404(Task, id=task_id, user=request.user)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tarea actualizada correctamente.')
            return redirect('task_list')
    else:
        form = TaskForm(instance=task)
    
    context = {
        'form': form,
        'task': task,
    }
    
    return render(request, 'tracker/edit_task.html', context)

@login_required
def delete_task(request, task_id):
    """Vista para eliminar una tarea"""
    task = get_object_or_404(Task, id=task_id, user=request.user)
    
    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Tarea eliminada correctamente.')
        return redirect('task_list')
    
    context = {
        'task': task,
    }
    
    return render(request, 'tracker/delete_task.html', context)

@login_required
def complete_task(request, task_id):
    """Vista para marcar una tarea como completada"""
    task = get_object_or_404(Task, id=task_id, user=request.user)
    
    if request.method == 'POST':
        task.completed = True
        task.save()
        messages.success(request, 'Tarea marcada como completada.')
        return redirect('task_list')
    
    return redirect('task_list')

@login_required
def uncomplete_task(request, task_id):
    """Vista para marcar una tarea como no completada"""
    task = get_object_or_404(Task, id=task_id, user=request.user)
    
    if request.method == 'POST':
        task.completed = False
        task.save()
        messages.success(request, 'Tarea marcada como no completada.')
        return redirect('task_list')
    
    return redirect('task_list')

@login_required
def reorder_task(request):
    """Vista para reordenar tareas mediante AJAX"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        task_ids = request.POST.getlist('task_ids[]')
        
        for index, task_id in enumerate(task_ids):
            task = get_object_or_404(Task, id=task_id, user=request.user)
            task.order = index
            task.save()
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def reorder_habit(request):
    """Vista para reordenar hábitos mediante AJAX"""
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        habit_ids = request.POST.getlist('habit_ids[]')
        
        for index, habit_id in enumerate(habit_ids):
            habit = get_object_or_404(Habit, id=habit_id, user=request.user)
            habit.order = index
            habit.save()
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def progress_report(request):
    """Vista para el informe de progreso"""
    today = timezone.now().date()
    
    # Forma predeterminada: último mes
    end_date = today
    start_date = end_date - timedelta(days=30)
    
    form = DateRangeForm(request.GET or None, initial={
        'start_date': start_date,
        'end_date': end_date,
    })
    
    if form.is_valid():
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
    
    # Obtener datos para gráficos
    habits = Habit.objects.filter(user=request.user)
    habit_data = []
    chart_labels = []
    
    for habit in habits:
        # Calcular la tasa de completado en el rango de fechas
        total_days = (end_date - start_date).days + 1
        date_range = [start_date + timedelta(days=i) for i in range(total_days)]
        
        # Generar etiquetas para el gráfico (solo una vez)
        if not chart_labels:
            chart_labels = [date.strftime('%Y-%m-%d') for date in date_range]
        
        completion_by_date = {}
        for date in date_range:
            try:
                record = HabitRecord.objects.get(habit=habit, date=date)
                completion_by_date[date] = 1 if record.completed else 0
            except HabitRecord.DoesNotExist:
                completion_by_date[date] = 0
        
        # Calcular el progreso acumulado
        cumulative_progress = []
        completed_count = 0
        
        for i, date in enumerate(date_range):
            completed_count += completion_by_date[date]
            percentage = (completed_count / (i + 1)) * 100
            cumulative_progress.append({
                'date': date.strftime('%Y-%m-%d'),
                'percentage': round(percentage, 1)
            })
        
        # Preparar datos para la gráfica
        chart_data = [progress['percentage'] for progress in cumulative_progress]
        
        habit_data.append({
            'habit': habit,
            'daily_completion': completion_by_date,
            'cumulative_progress': cumulative_progress,
            'chart_data': chart_data,
        })
    
    # Calcular estadísticas de tareas
    completed_tasks = Task.objects.filter(
        user=request.user, 
        completed=True,
        created_at__date__range=[start_date, end_date]
    ).count()
    
    total_tasks = completed_tasks + Task.objects.filter(
        user=request.user, 
        completed=False,
        created_at__date__range=[start_date, end_date]
    ).count()
    
    task_completion_rate = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    
    context = {
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
        'habit_data': habit_data,
        'chart_labels': chart_labels,
        'completed_tasks': completed_tasks,
        'total_tasks': total_tasks,
        'task_completion_rate': task_completion_rate,
    }
    
    return render(request, 'tracker/progress_report.html', context)

@login_required
def weekly_view(request):
    """Vista semanal tipo agenda"""
    today = timezone.now().date()
    
    # Calcular el inicio de la semana (lunes)
    start_of_week = today - timedelta(days=today.weekday())
    
    # Crear lista de días como diccionarios
    week_days = [
        {'date_obj': start_of_week + timedelta(days=i), 'date_str': (start_of_week + timedelta(days=i)).strftime('%Y-%m-%d')}
        for i in range(7)
    ]
    
    # Obtener tareas para la semana
    tasks_by_day = {
        day['date_obj']: Task.objects.filter(
            user=request.user,
            due_date=day['date_obj']
        ).order_by('priority')
        for day in week_days
    }
    
    # Obtener hábitos y sus registros
    habits = Habit.objects.filter(user=request.user).order_by('order')
    
    habit_records = {}
    for habit in habits:
        habit_records[habit.id] = {}
        existing_records = HabitRecord.objects.filter(
            habit=habit,
            date__in=[day['date_obj'] for day in week_days]
        )
        
        records_dict = {record.date: record for record in existing_records}
        
        for day in week_days:
            record = records_dict.get(day['date_obj'])
            if not record:
                record = HabitRecord.objects.create(
                    habit=habit,
                    date=day['date_obj'],
                    completed=False
                )
            habit_records[habit.id][day['date_str']] = {
                'id': record.id,
                'completed': record.completed
            }
    
    context = {
        'week_days': week_days,
        'tasks_by_day': tasks_by_day,
        'habits': habits,
        'habit_records': habit_records,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': start_of_week + timedelta(days=6),
    }
    
    return render(request, 'tracker/weekly_view.html', context)