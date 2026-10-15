import calendar
import csv
import json
from collections import defaultdict
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Min, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import DateRangeForm, HabitForm, TaskFilterForm, TaskForm, UserRegisterForm
from .models import PRIORITY_ORDER, Habit, HabitRecord, Task, compute_streaks


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _safe_redirect(request, fallback):
    """Redirige a ?next= / campo next si es una URL interna, si no a `fallback`."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(fallback)


def _read_payload(request):
    """Lee el cuerpo como JSON o, si no lo es, como formulario. Lanza ValueError si el JSON es inválido."""
    if request.content_type == 'application/json' or not request.POST:
        if not request.body:
            return {}
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError('Invalid JSON') from exc
        if not isinstance(data, dict):
            raise ValueError('Invalid JSON')
        return data
    return request.POST


def _to_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'on', 'yes')
    return bool(value)


def _records_by_habit(habits, start, end):
    """{habit_id: {fecha: completado}} para el rango, en una sola consulta."""
    result = defaultdict(dict)
    rows = HabitRecord.objects.filter(
        habit__in=habits, date__range=(start, end)
    ).values_list('habit_id', 'date', 'completed')
    for habit_id, day, completed in rows:
        result[habit_id][day] = completed
    return result


def _completed_dates_by_habit(habits):
    """{habit_id: set(fechas completadas)} en una sola consulta."""
    result = defaultdict(set)
    rows = HabitRecord.objects.filter(habit__in=habits, completed=True).values_list('habit_id', 'date')
    for habit_id, day in rows:
        result[habit_id].add(day)
    return result


def _habit_start_dates(habits):
    """{habit_id: primer día que cuenta} (creación o primer registro, lo que sea antes)."""
    first_records = dict(
        HabitRecord.objects.filter(habit__in=habits)
        .values('habit_id').annotate(first=Min('date')).values_list('habit_id', 'first')
    )
    starts = {}
    for habit in habits:
        created = timezone.localdate(habit.created_at)
        first = first_records.get(habit.id)
        starts[habit.id] = min(created, first) if first else created
    return starts


def _daily_completion(habits, start, end, today):
    """Para cada día del rango devuelve (hábitos completados, hábitos que aplicaban ese día).

    Un hábito solo cuenta a partir de su fecha de inicio y nunca en días futuros.
    """
    starts = _habit_start_dates(habits)
    records = _records_by_habit(habits, start, end)
    stats = {}
    day = start
    while day <= end:
        if day > today:
            stats[day] = (0, 0)
        else:
            eligible = [h for h in habits if starts[h.id] <= day]
            done = sum(1 for h in eligible if records.get(h.id, {}).get(day))
            stats[day] = (done, len(eligible))
        day += timedelta(days=1)
    return stats, records, starts


def _heat_level(done, eligible):
    """Nivel 0-4 para colorear calendarios (None si no aplica ningún hábito)."""
    if not eligible:
        return None
    ratio = done / eligible
    if ratio == 0:
        return 0
    if ratio < 0.34:
        return 1
    if ratio < 0.67:
        return 2
    if ratio < 1:
        return 3
    return 4


def _week_bounds(reference):
    start = reference - timedelta(days=reference.weekday())
    return start, start + timedelta(days=6)


def _pending_tasks(user):
    return Task.objects.filter(user=user, completed=False).order_by('order', PRIORITY_ORDER, 'due_date')


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------

def register(request):
    """Vista de registro de usuario"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.username}! Tu cuenta se ha creado correctamente.')
            return redirect('dashboard')
    else:
        form = UserRegisterForm()
    return render(request, 'tracker/register.html', {'form': form})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """Vista principal del dashboard"""
    today = timezone.localdate()
    start_of_week, end_of_week = _week_bounds(today)
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]

    pending = _pending_tasks(request.user)
    pending_count = pending.count()
    overdue_count = pending.filter(due_date__lt=today).count()
    due_today_count = pending.filter(due_date=today).count()
    completed_count = Task.objects.filter(user=request.user, completed=True).count()
    total_tasks = completed_count + pending_count
    task_completion_rate = int((completed_count / total_tasks) * 100) if total_tasks else 0

    habits = list(Habit.objects.filter(user=request.user, archived=False))
    week_records = _records_by_habit(habits, start_of_week, end_of_week)
    completed_dates = _completed_dates_by_habit(habits)

    elapsed_days = [d for d in week_days if d <= today]
    habits_with_data = []
    for habit in habits:
        records = week_records.get(habit.id, {})
        done_this_week = sum(1 for d in elapsed_days if records.get(d))
        current_streak, best_streak = compute_streaks(completed_dates.get(habit.id, set()), today)
        habits_with_data.append({
            'habit': habit,
            'days': [{'date': d, 'completed': records.get(d, False), 'future': d > today} for d in week_days],
            'completion_rate': int((done_this_week / len(elapsed_days)) * 100) if elapsed_days else 0,
            'current_streak': current_streak,
            'best_streak': best_streak,
            'done_today': records.get(today, False),
        })

    habits_done_today = sum(1 for h in habits_with_data if h['done_today'])

    context = {
        'today': today,
        'week_days': week_days,
        'tasks': pending[:6],
        'pending_count': pending_count,
        'overdue_count': overdue_count,
        'due_today_count': due_today_count,
        'completed_count': completed_count,
        'total_tasks': total_tasks,
        'task_completion_rate': task_completion_rate,
        'habits_with_data': habits_with_data,
        'habits_done_today': habits_done_today,
        'habits_total': len(habits_with_data),
        'best_current_streak': max((h['current_streak'] for h in habits_with_data), default=0),
    }
    return render(request, 'tracker/dashboard.html', context)


# ---------------------------------------------------------------------------
# Hábitos
# ---------------------------------------------------------------------------

@login_required
def habit_list(request):
    """Vista para gestionar hábitos"""
    if request.method == 'POST':
        form = HabitForm(request.POST)
        if form.is_valid():
            habit = form.save(commit=False)
            habit.user = request.user
            last = Habit.objects.filter(user=request.user).order_by('-order').values_list('order', flat=True).first()
            habit.order = (last or 0) + 1
            habit.save()
            messages.success(request, 'Hábito añadido correctamente.')
            return redirect('habit_list')
    else:
        form = HabitForm()

    habits = list(Habit.objects.filter(user=request.user, archived=False))
    archived_habits = Habit.objects.filter(user=request.user, archived=True)
    today = timezone.localdate()
    completed_dates = _completed_dates_by_habit(habits)
    for habit in habits:
        habit.streak, habit.best = compute_streaks(completed_dates.get(habit.id, set()), today)

    context = {
        'habits': habits,
        'archived_habits': archived_habits,
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

    return render(request, 'tracker/edit_habit.html', {'form': form, 'habit': habit})


@login_required
def delete_habit(request, habit_id):
    """Vista para eliminar un hábito"""
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)

    if request.method == 'POST':
        habit.delete()
        messages.success(request, 'Hábito eliminado correctamente.')
        return redirect('habit_list')

    return render(request, 'tracker/delete_habit.html', {'habit': habit})


@login_required
@require_POST
def archive_habit(request, habit_id):
    """Archiva o restaura un hábito (se conserva su historial)"""
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    habit.archived = not habit.archived
    habit.save(update_fields=['archived'])
    if habit.archived:
        messages.info(request, f'Hábito "{habit.name}" archivado. Su historial se conserva.')
    else:
        messages.success(request, f'Hábito "{habit.name}" restaurado.')
    return redirect('habit_list')


@login_required
def habit_detail(request, habit_id):
    """Historial y estadísticas de un hábito (últimas 12 semanas)"""
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    today = timezone.localdate()
    weeks = 12
    start = _week_bounds(today)[0] - timedelta(weeks=weeks - 1)
    records = _records_by_habit([habit], start, today + timedelta(days=6 - today.weekday())).get(habit.id, {})

    # Cuadrícula tipo "heatmap": filas = día de la semana, columnas = semanas
    grid = []
    for weekday in range(7):
        row = []
        for week in range(weeks):
            day = start + timedelta(weeks=week, days=weekday)
            row.append({'date': day, 'completed': records.get(day, False), 'future': day > today})
        grid.append(row)

    current_streak, best_streak = habit.streaks()
    total_completed = habit.records.filter(completed=True).count()

    context = {
        'habit': habit,
        'grid': grid,
        'current_streak': current_streak,
        'best_streak': best_streak,
        'total_completed': total_completed,
        'completion_rate': habit.completion_rate(),
        'start_date': habit.start_date(),
        'today': today,
    }
    return render(request, 'tracker/habit_detail.html', context)


@login_required
@require_POST
def toggle_habit(request, habit_id):
    """Marca/desmarca un hábito para una fecha (JSON: {"date": "YYYY-MM-DD", "completed": bool}).

    Crea el registro si no existe, de modo que no hace falta generar registros vacíos por adelantado.
    """
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    try:
        data = _read_payload(request)
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    today = timezone.localdate()
    day = _parse_date(data.get('date')) if data.get('date') else today
    if day is None:
        return JsonResponse({'status': 'error', 'message': 'Fecha inválida'}, status=400)
    if day > today:
        return JsonResponse({'status': 'error', 'message': 'No se pueden marcar días futuros'}, status=400)

    completed = _to_bool(data.get('completed', False))
    HabitRecord.objects.update_or_create(habit=habit, date=day, defaults={'completed': completed})

    current_streak, best_streak = habit.streaks()
    return JsonResponse({
        'status': 'success',
        'completed': completed,
        'date': day.isoformat(),
        'current_streak': current_streak,
        'best_streak': best_streak,
    })


@login_required
def toggle_habit_record(request, record_id):
    """Marca/desmarca un registro de hábito existente (compatibilidad con la API anterior)"""
    if request.method != 'POST' or not _is_ajax(request):
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    try:
        record = HabitRecord.objects.get(id=record_id, habit__user=request.user)
    except HabitRecord.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

    try:
        data = _read_payload(request)
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    record.completed = _to_bool(data.get('completed', False))
    record.save(update_fields=['completed'])
    return JsonResponse({'status': 'success', 'completed': record.completed})


def _reorder(request, model, key):
    if request.method != 'POST' or not _is_ajax(request):
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    try:
        data = _read_payload(request)
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    raw_ids = data.getlist(f'{key}[]') if hasattr(data, 'getlist') else data.get(key, [])
    try:
        ids = [int(i) for i in raw_ids]
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'IDs inválidos'}, status=400)

    objects = {obj.id: obj for obj in model.objects.filter(user=request.user, id__in=ids)}
    if len(objects) != len(set(ids)):
        return JsonResponse({'status': 'error', 'message': 'Not found'}, status=404)

    for index, obj_id in enumerate(ids):
        objects[obj_id].order = index
    with transaction.atomic():
        model.objects.bulk_update(objects.values(), ['order'])
    return JsonResponse({'status': 'success'})


@login_required
def reorder_habit(request):
    """Vista para reordenar hábitos mediante AJAX"""
    return _reorder(request, Habit, 'habit_ids')


# ---------------------------------------------------------------------------
# Tareas
# ---------------------------------------------------------------------------

@login_required
def task_list(request):
    """Vista para gestionar tareas (con búsqueda y filtros)"""
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, 'Tarea añadida correctamente.')
            return redirect('task_list')
    else:
        initial = {}
        due = _parse_date(request.GET.get('due'))
        if due:
            initial['due_date'] = due
        form = TaskForm(initial=initial)

    today = timezone.localdate()
    tasks = _pending_tasks(request.user)
    filter_form = TaskFilterForm(request.GET or None)
    filtering = False
    if filter_form.is_valid():
        q = filter_form.cleaned_data.get('q')
        priority = filter_form.cleaned_data.get('priority')
        status = filter_form.cleaned_data.get('status')
        if q:
            tasks = tasks.filter(Q(title__icontains=q) | Q(description__icontains=q))
        if priority:
            tasks = tasks.filter(priority=priority)
        if status == 'overdue':
            tasks = tasks.filter(due_date__lt=today)
        elif status == 'today':
            tasks = tasks.filter(due_date=today)
        elif status == 'upcoming':
            tasks = tasks.filter(due_date__gt=today)
        elif status == 'no_date':
            tasks = tasks.filter(due_date__isnull=True)
        filtering = bool(q or priority or status)

    completed_tasks = Task.objects.filter(user=request.user, completed=True).order_by('-completed_at', '-created_at')
    context = {
        'tasks': tasks,
        'completed_tasks': completed_tasks[:10],
        'completed_total': completed_tasks.count(),
        'form': form,
        'filter_form': filter_form,
        'filtering': filtering,
        'today': today,
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

    return render(request, 'tracker/edit_task.html', {'form': form, 'task': task})


@login_required
def delete_task(request, task_id):
    """Vista para eliminar una tarea"""
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if request.method == 'POST':
        task.delete()
        messages.success(request, 'Tarea eliminada correctamente.')
        return _safe_redirect(request, 'task_list')

    return render(request, 'tracker/delete_task.html', {'task': task})


@login_required
def complete_task(request, task_id):
    """Vista para marcar una tarea como completada"""
    task = get_object_or_404(Task, id=task_id, user=request.user)
    if request.method == 'POST':
        task.mark_completed(True)
        messages.success(request, f'Tarea "{task.title}" completada.')
    return _safe_redirect(request, 'task_list')


@login_required
def uncomplete_task(request, task_id):
    """Vista para marcar una tarea como no completada"""
    task = get_object_or_404(Task, id=task_id, user=request.user)
    if request.method == 'POST':
        task.mark_completed(False)
        messages.success(request, f'Tarea "{task.title}" marcada como pendiente.')
    return _safe_redirect(request, 'task_list')


@login_required
@require_POST
def clear_completed_tasks(request):
    """Elimina todas las tareas completadas del usuario"""
    deleted, _ = Task.objects.filter(user=request.user, completed=True).delete()
    messages.success(request, f'Se eliminaron {deleted} tareas completadas.')
    return redirect('task_list')


@login_required
def reorder_task(request):
    """Vista para reordenar tareas mediante AJAX"""
    return _reorder(request, Task, 'task_ids')


# ---------------------------------------------------------------------------
# Informes
# ---------------------------------------------------------------------------

@login_required
def progress_report(request):
    """Vista para el informe de progreso"""
    today = timezone.localdate()
    end_date = today
    start_date = end_date - timedelta(days=29)

    if request.GET:
        form = DateRangeForm(request.GET)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
    else:
        form = DateRangeForm(initial={'start_date': start_date, 'end_date': end_date})

    date_range = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    chart_labels = [d.isoformat() for d in date_range]

    habits = list(Habit.objects.filter(user=request.user, archived=False))
    records = _records_by_habit(habits, start_date, end_date)
    all_completed = _completed_dates_by_habit(habits)

    habit_data = []
    daily_totals = [0] * len(date_range)
    for habit in habits:
        habit_records = records.get(habit.id, {})
        cumulative_progress = []
        chart_data = []
        completed_count = 0
        for i, day in enumerate(date_range):
            done = 1 if habit_records.get(day) else 0
            completed_count += done
            daily_totals[i] += done
            percentage = round((completed_count / (i + 1)) * 100, 1)
            cumulative_progress.append({'date': day.isoformat(), 'percentage': percentage})
            chart_data.append(percentage)

        current_streak, best_streak = compute_streaks(all_completed.get(habit.id, set()), today)
        habit_data.append({
            'habit': habit,
            'daily_completion': {day: 1 if habit_records.get(day) else 0 for day in date_range},
            'cumulative_progress': cumulative_progress,
            'chart_data': chart_data,
            'completed_days': completed_count,
            'total_days': len(date_range),
            'rate': chart_data[-1] if chart_data else 0,
            'current_streak': current_streak,
            'best_streak': best_streak,
        })

    habit_count = len(habits)
    daily_rate = [round((total / habit_count) * 100, 1) if habit_count else 0 for total in daily_totals]

    # Tareas: creadas en el período y cuántas de ellas están completadas
    period_tasks = Task.objects.filter(user=request.user, created_at__date__range=(start_date, end_date))
    total_tasks = period_tasks.count()
    completed_tasks = period_tasks.filter(completed=True).count()
    task_completion_rate = int((completed_tasks / total_tasks) * 100) if total_tasks else 0
    completed_in_period = Task.objects.filter(
        user=request.user, completed=True, completed_at__date__range=(start_date, end_date)
    ).count()

    context = {
        'form': form,
        'start_date': start_date,
        'end_date': end_date,
        'habit_data': habit_data,
        'chart_labels': chart_labels,
        'chart_payload': {
            'labels': chart_labels,
            'datasets': [
                {'label': d['habit'].name, 'priority': d['habit'].priority, 'data': d['chart_data']}
                for d in habit_data
            ],
            'daily': daily_rate,
        },
        'completed_tasks': completed_tasks,
        'total_tasks': total_tasks,
        'task_completion_rate': task_completion_rate,
        'completed_in_period': completed_in_period,
    }
    return render(request, 'tracker/progress_report.html', context)


@login_required
def weekly_view(request):
    """Vista semanal tipo agenda, con navegación entre semanas (?week=YYYY-MM-DD)"""
    today = timezone.localdate()
    reference = _parse_date(request.GET.get('week')) or today
    start_of_week, end_of_week = _week_bounds(reference)

    week_days = [
        {'date_obj': start_of_week + timedelta(days=i), 'date_str': (start_of_week + timedelta(days=i)).isoformat()}
        for i in range(7)
    ]

    tasks_by_day = {day['date_obj']: [] for day in week_days}
    week_tasks = Task.objects.filter(
        user=request.user, due_date__range=(start_of_week, end_of_week)
    ).order_by('completed', PRIORITY_ORDER, 'order')
    for task in week_tasks:
        tasks_by_day[task.due_date].append(task)

    habits = list(Habit.objects.filter(user=request.user, archived=False))
    records = _records_by_habit(habits, start_of_week, end_of_week)
    habit_records = {
        habit.id: {
            day['date_str']: {'completed': records.get(habit.id, {}).get(day['date_obj'], False)}
            for day in week_days
        }
        for habit in habits
    }

    context = {
        'week_days': week_days,
        'tasks_by_day': tasks_by_day,
        'habits': habits,
        'habit_records': habit_records,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'prev_week': (start_of_week - timedelta(days=7)).isoformat(),
        'next_week': (start_of_week + timedelta(days=7)).isoformat(),
        'is_current_week': start_of_week <= today <= end_of_week,
        'ref_date': today if start_of_week <= today <= end_of_week else start_of_week,
    }
    return render(request, 'tracker/weekly_view.html', context)


@login_required
def export_data(request, kind):
    """Exporta los hábitos o las tareas del usuario a CSV"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response.write('﻿')  # BOM para que Excel detecte UTF-8
    writer = csv.writer(response)
    stamp = timezone.localdate().isoformat()

    if kind == 'habits':
        response['Content-Disposition'] = f'attachment; filename="habitos_{stamp}.csv"'
        writer.writerow(['Hábito', 'Prioridad', 'Fecha', 'Completado'])
        rows = HabitRecord.objects.filter(habit__user=request.user).select_related('habit').order_by('habit__name', 'date')
        for record in rows:
            writer.writerow([record.habit.name, record.habit.get_priority_display(),
                             record.date.isoformat(), 'Sí' if record.completed else 'No'])
    elif kind == 'tasks':
        response['Content-Disposition'] = f'attachment; filename="tareas_{stamp}.csv"'
        writer.writerow(['Título', 'Descripción', 'Prioridad', 'Fecha límite', 'Completada', 'Completada el', 'Creada el'])
        for task in Task.objects.filter(user=request.user).order_by('created_at'):
            writer.writerow([
                task.title,
                task.description,
                task.get_priority_display(),
                task.due_date.isoformat() if task.due_date else '',
                'Sí' if task.completed else 'No',
                timezone.localtime(task.completed_at).strftime('%Y-%m-%d %H:%M') if task.completed_at else '',
                timezone.localtime(task.created_at).strftime('%Y-%m-%d %H:%M'),
            ])
    else:
        raise Http404
    return response


@login_required
def daily_view(request):
    """Vista de un día (?date=YYYY-MM-DD): hábitos para marcar y tareas del día"""
    today = timezone.localdate()
    day = _parse_date(request.GET.get('date')) or today

    habits = list(Habit.objects.filter(user=request.user, archived=False))
    records = _records_by_habit(habits, day, day)
    completed_dates = _completed_dates_by_habit(habits)
    habit_items = []
    for habit in habits:
        current_streak, best_streak = compute_streaks(completed_dates.get(habit.id, set()), today)
        habit_items.append({
            'habit': habit,
            'completed': records.get(habit.id, {}).get(day, False),
            'current_streak': current_streak,
            'best_streak': best_streak,
        })
    habits_done = sum(1 for item in habit_items if item['completed'])

    tasks_due = Task.objects.filter(user=request.user, due_date=day).order_by('completed', PRIORITY_ORDER, 'order')
    overdue_tasks = _pending_tasks(request.user).filter(due_date__lt=today) if day == today else Task.objects.none()
    completed_other = Task.objects.filter(
        user=request.user, completed=True, completed_at__date=day
    ).exclude(due_date=day).order_by('-completed_at')

    context = {
        'day': day,
        'today': today,
        'is_today': day == today,
        'is_future': day > today,
        'prev_day': (day - timedelta(days=1)).isoformat(),
        'next_day': (day + timedelta(days=1)).isoformat(),
        'habit_items': habit_items,
        'habits_done': habits_done,
        'habits_total': len(habit_items),
        'habit_rate': int(habits_done / len(habit_items) * 100) if habit_items else 0,
        'tasks_due': tasks_due,
        'overdue_tasks': overdue_tasks,
        'completed_other': completed_other,
        'ref_date': day,
    }
    return render(request, 'tracker/daily_view.html', context)


@login_required
def monthly_view(request):
    """Calendario mensual (?month=YYYY-MM) con cumplimiento de hábitos y tareas por día"""
    today = timezone.localdate()
    first = _parse_date(f"{request.GET.get('month', '')}-01") or today.replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])

    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
    grid_start, grid_end = weeks[0][0], weeks[-1][-1]

    habits = list(Habit.objects.filter(user=request.user, archived=False))
    stats, records, starts = _daily_completion(habits, grid_start, grid_end, today)

    tasks_by_day = defaultdict(list)
    grid_tasks = Task.objects.filter(
        user=request.user, due_date__range=(grid_start, grid_end)
    ).order_by('completed', PRIORITY_ORDER, 'order')
    for task in grid_tasks:
        tasks_by_day[task.due_date].append(task)

    calendar_weeks = []
    for week in weeks:
        row = []
        for d in week:
            done, eligible = stats[d]
            day_tasks = tasks_by_day.get(d, [])
            row.append({
                'date': d,
                'in_month': d.month == first.month,
                'is_today': d == today,
                'future': d > today,
                'done': done,
                'eligible': eligible,
                'level': _heat_level(done, eligible),
                'tasks': day_tasks[:3],
                'more_tasks': max(len(day_tasks) - 3, 0),
            })
        calendar_weeks.append(row)

    # Resumen por hábito dentro del mes (solo días transcurridos desde el inicio del hábito)
    elapsed_end = min(last, today)
    habit_summary = []
    for habit in habits:
        start = max(first, starts[habit.id])
        eligible_days = (elapsed_end - start).days + 1 if elapsed_end >= start else 0
        done = sum(1 for d, completed in records.get(habit.id, {}).items() if completed and first <= d <= last)
        habit_summary.append({
            'habit': habit,
            'done': done,
            'eligible': eligible_days,
            'rate': int(done / eligible_days * 100) if eligible_days else 0,
        })

    month_days = [d for week in weeks for d in week if d.month == first.month]
    month_done = sum(stats[d][0] for d in month_days)
    month_eligible = sum(stats[d][1] for d in month_days)

    context = {
        'month_start': first,
        'month_end': last,
        'today': today,
        'weekday_labels': ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'],
        'calendar_weeks': calendar_weeks,
        'habit_summary': habit_summary,
        'month_rate': int(month_done / month_eligible * 100) if month_eligible else 0,
        'month_done': month_done,
        'perfect_days': sum(1 for d in month_days if stats[d][1] and stats[d][0] == stats[d][1]),
        'tasks_due_count': Task.objects.filter(user=request.user, due_date__range=(first, last)).count(),
        'tasks_completed_count': Task.objects.filter(
            user=request.user, completed=True, completed_at__date__range=(first, last)
        ).count(),
        'prev_month': (first - timedelta(days=1)).strftime('%Y-%m'),
        'next_month': (last + timedelta(days=1)).strftime('%Y-%m'),
        'is_current_month': first <= today <= last,
        'ref_date': today if first <= today <= last else first,
    }
    return render(request, 'tracker/monthly_view.html', context)


@login_required
def yearly_view(request):
    """Resumen anual (?year=YYYY, opcional ?habit=<id>) con un mapa de calor por mes"""
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
    except (TypeError, ValueError):
        year = today.year
    year = min(max(year, 1900), 2100)

    all_habits = list(Habit.objects.filter(user=request.user, archived=False))
    selected_habit = next((h for h in all_habits if str(h.id) == request.GET.get('habit')), None)
    habits = [selected_habit] if selected_habit else all_habits

    first, last = date(year, 1, 1), date(year, 12, 31)
    stats, records, starts = _daily_completion(habits, first, last, today)

    completed_by_month = defaultdict(int)
    completed_stamps = Task.objects.filter(
        user=request.user, completed=True, completed_at__date__range=(first, last)
    ).values_list('completed_at', flat=True)
    for stamp in completed_stamps:
        completed_by_month[timezone.localtime(stamp).month] += 1

    cal = calendar.Calendar(firstweekday=0)
    months = []
    for month in range(1, 13):
        weeks = []
        done_month = eligible_month = 0
        for week in cal.monthdatescalendar(year, month):
            row = []
            for d in week:
                if d.month != month:
                    row.append(None)
                    continue
                done, eligible = stats[d]
                done_month += done
                eligible_month += eligible
                row.append({
                    'date': d,
                    'done': done,
                    'eligible': eligible,
                    'level': _heat_level(done, eligible),
                    'is_today': d == today,
                    'future': d > today,
                })
            weeks.append(row)
        months.append({
            'date': date(year, month, 1),
            'weeks': weeks,
            'done': done_month,
            'eligible': eligible_month,
            'rate': int(done_month / eligible_month * 100) if eligible_month else None,
            'tasks_completed': completed_by_month.get(month, 0),
        })

    total_done = sum(m['done'] for m in months)
    total_eligible = sum(m['eligible'] for m in months)
    rated_months = [m for m in months if m['rate'] is not None]

    habit_summary = []
    for habit in habits:
        habit_records = records.get(habit.id, {})
        start = max(first, starts[habit.id])
        end = min(last, today)
        eligible_days = (end - start).days + 1 if end >= start else 0
        done = sum(1 for completed in habit_records.values() if completed)
        _, best_in_year = compute_streaks({d for d, c in habit_records.items() if c}, end if end >= first else first)
        habit_summary.append({
            'habit': habit,
            'done': done,
            'eligible': eligible_days,
            'rate': int(done / eligible_days * 100) if eligible_days else 0,
            'best_streak': best_in_year,
        })

    context = {
        'year': year,
        'today': today,
        'months': months,
        'weekday_initials': ['L', 'M', 'X', 'J', 'V', 'S', 'D'],
        'all_habits': all_habits,
        'selected_habit': selected_habit,
        'habit_summary': habit_summary,
        'year_rate': int(total_done / total_eligible * 100) if total_eligible else 0,
        'total_done': total_done,
        'active_days': sum(1 for done, _ in stats.values() if done),
        'tasks_completed_year': sum(completed_by_month.values()),
        'best_month': max(rated_months, key=lambda m: m['rate']) if rated_months else None,
        'prev_year': year - 1,
        'next_year': year + 1,
        'is_current_year': year == today.year,
        'ref_date': today if year == today.year else first,
    }
    return render(request, 'tracker/yearly_view.html', context)
