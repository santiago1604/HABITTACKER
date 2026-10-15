import json
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import DateRangeForm, HabitForm, TaskForm, UserRegisterForm
from .models import Habit, HabitRecord, Task, compute_streaks


def today():
    return timezone.localdate()


class HabitModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.habit = Habit.objects.create(user=self.user, name='Test Habit', priority='media')

    def test_habit_str(self):
        self.assertEqual(str(self.habit), 'Test Habit')

    def test_completion_rate_no_records(self):
        self.assertEqual(self.habit.completion_rate(), 0)

    def test_completion_rate_with_records(self):
        HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        HabitRecord.objects.create(habit=self.habit, date=today() - timedelta(days=1), completed=False)
        self.assertEqual(self.habit.completion_rate(), 50)

    def test_completion_rate_counts_days_without_records(self):
        # Registro completado hace 3 días y hoy: 2 de 4 días
        HabitRecord.objects.create(habit=self.habit, date=today() - timedelta(days=3), completed=True)
        HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        self.assertEqual(self.habit.completion_rate(), 50)

    def test_streaks(self):
        for offset in (0, 1, 2, 5, 6, 7, 8):
            HabitRecord.objects.create(habit=self.habit, date=today() - timedelta(days=offset), completed=True)
        self.assertEqual(self.habit.streaks(), (3, 4))

    def test_priority_color(self):
        self.assertEqual(self.habit.get_priority_color(), 'warning')


class StreakTests(TestCase):
    def test_empty(self):
        self.assertEqual(compute_streaks(set(), date(2025, 1, 10)), (0, 0))

    def test_streak_alive_if_yesterday_done(self):
        ref = date(2025, 1, 10)
        dates = {ref - timedelta(days=1), ref - timedelta(days=2)}
        self.assertEqual(compute_streaks(dates, ref), (2, 2))

    def test_streak_broken(self):
        ref = date(2025, 1, 10)
        dates = {ref - timedelta(days=2), ref - timedelta(days=3)}
        self.assertEqual(compute_streaks(dates, ref), (0, 2))

    def test_future_dates_ignored(self):
        ref = date(2025, 1, 10)
        self.assertEqual(compute_streaks({ref + timedelta(days=1)}, ref), (0, 0))


class HabitRecordModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.habit = Habit.objects.create(user=self.user, name='Test Habit', priority='media')

    def test_habit_record_str(self):
        record = HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        self.assertEqual(str(record), f"{self.habit.name} - {today().strftime('%d/%m/%Y')}")

    def test_unique_together_constraint(self):
        HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        with self.assertRaises(IntegrityError):
            HabitRecord.objects.create(habit=self.habit, date=today(), completed=False)

    def test_default_date_is_local_date(self):
        record = HabitRecord.objects.create(habit=self.habit)
        self.assertEqual(record.date, today())


class TaskModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.task = Task.objects.create(user=self.user, title='Test Task', priority='media')

    def test_task_str(self):
        self.assertEqual(str(self.task), 'Test Task')

    def test_get_priority_color(self):
        self.assertEqual(self.task.get_priority_color(), 'warning')
        self.task.priority = 'alta'
        self.assertEqual(self.task.get_priority_color(), 'danger')
        self.task.priority = 'baja'
        self.assertEqual(self.task.get_priority_color(), 'info')
        self.task.priority = 'unknown'
        self.assertEqual(self.task.get_priority_color(), 'secondary')

    def test_overdue_and_due_today(self):
        self.task.due_date = today() - timedelta(days=1)
        self.assertTrue(self.task.is_overdue)
        self.task.due_date = today()
        self.assertFalse(self.task.is_overdue)
        self.assertTrue(self.task.is_due_today)
        self.task.completed = True
        self.assertFalse(self.task.is_due_today)

    def test_mark_completed_sets_timestamp(self):
        self.task.mark_completed(True)
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)
        self.assertIsNotNone(self.task.completed_at)
        self.task.mark_completed(False)
        self.task.refresh_from_db()
        self.assertFalse(self.task.completed)
        self.assertIsNone(self.task.completed_at)


class FormTests(TestCase):
    def test_user_register_form_valid(self):
        form = UserRegisterForm(data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
        })
        self.assertTrue(form.is_valid())

    def test_user_register_form_invalid_email(self):
        form = UserRegisterForm(data={
            'username': 'newuser',
            'email': 'not-an-email',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_user_register_form_duplicate_email(self):
        User.objects.create_user(username='other', email='dup@example.com', password='x')
        form = UserRegisterForm(data={
            'username': 'newuser',
            'email': 'DUP@example.com',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_habit_form_valid(self):
        form = HabitForm(data={'name': 'Exercise', 'description': 'Daily exercise', 'priority': 'alta'})
        self.assertTrue(form.is_valid())

    def test_habit_form_missing_name(self):
        form = HabitForm(data={'description': 'Daily exercise', 'priority': 'alta'})
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_task_form_valid(self):
        form = TaskForm(data={
            'title': 'Complete project',
            'description': 'Finish by end of month',
            'priority': 'media',
            'due_date': (today() + timedelta(days=10)).isoformat(),
        })
        self.assertTrue(form.is_valid())

    def test_task_form_past_due_date(self):
        form = TaskForm(data={'title': 'Old', 'priority': 'media', 'due_date': '2020-01-01'})
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)

    def test_task_form_keeps_existing_past_due_date(self):
        user = User.objects.create_user(username='u', password='x')
        task = Task.objects.create(user=user, title='Old', due_date=date(2020, 1, 1))
        form = TaskForm(data={'title': 'Old renamed', 'priority': 'media', 'due_date': '2020-01-01'}, instance=task)
        self.assertTrue(form.is_valid())

    def test_task_form_invalid_due_date(self):
        form = TaskForm(data={'title': 'Complete project', 'priority': 'media', 'due_date': 'invalid-date'})
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)

    def test_date_range_form_valid(self):
        form = DateRangeForm(data={'start_date': '2024-01-01', 'end_date': '2024-01-31'})
        self.assertTrue(form.is_valid())

    def test_date_range_form_start_after_end(self):
        form = DateRangeForm(data={'start_date': '2024-01-31', 'end_date': '2024-01-01'})
        self.assertFalse(form.is_valid())

    def test_date_range_form_too_long(self):
        form = DateRangeForm(data={'start_date': '2020-01-01', 'end_date': '2024-01-01'})
        self.assertFalse(form.is_valid())


class AuthViewTests(TestCase):
    def test_register_logs_in_and_redirects(self):
        response = self.client.post(reverse('register'), {
            'username': 'nuevo',
            'email': 'nuevo@example.com',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
        })
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='nuevo').pk)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_logout_via_post(self):
        User.objects.create_user(username='u', password='12345')
        self.client.login(username='u', password='12345')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))


class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.other = User.objects.create_user(username='other', password='12345')
        self.client.login(username='testuser', password='12345')
        self.habit = Habit.objects.create(user=self.user, name='Test Habit', priority='media')
        self.task = Task.objects.create(user=self.user, title='Test Task', priority='media')

    # --- Dashboard ---
    def test_dashboard_shows_habits_and_tasks(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Habit')
        self.assertContains(response, 'Test Task')
        self.assertEqual(len(response.context['habits_with_data']), 1)

    def test_dashboard_does_not_create_empty_records(self):
        self.client.get(reverse('dashboard'))
        self.client.get(reverse('weekly_view'))
        self.assertEqual(HabitRecord.objects.count(), 0)

    def test_dashboard_hides_archived_habits(self):
        self.habit.archived = True
        self.habit.save()
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['habits_total'], 0)

    # --- Hábitos ---
    def test_habit_create(self):
        response = self.client.post(reverse('habit_list'), {'name': 'Leer', 'priority': 'alta'})
        self.assertRedirects(response, reverse('habit_list'))
        self.assertTrue(Habit.objects.filter(user=self.user, name='Leer').exists())

    def test_habit_list_post_invalid(self):
        response = self.client.post(reverse('habit_list'), {'priority': 'alta'})
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_edit_habit_post_invalid(self):
        response = self.client.post(reverse('edit_habit', args=[self.habit.id]), {'name': '', 'priority': 'baja'})
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_cannot_edit_other_users_habit(self):
        foreign = Habit.objects.create(user=self.other, name='Ajeno')
        response = self.client.get(reverse('edit_habit', args=[foreign.id]))
        self.assertEqual(response.status_code, 404)

    def test_delete_habit_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('delete_habit', args=[self.habit.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Habit.objects.filter(id=self.habit.id).exists())

    def test_archive_and_restore_habit(self):
        self.client.post(reverse('archive_habit', args=[self.habit.id]))
        self.habit.refresh_from_db()
        self.assertTrue(self.habit.archived)
        self.client.post(reverse('archive_habit', args=[self.habit.id]))
        self.habit.refresh_from_db()
        self.assertFalse(self.habit.archived)

    def test_habit_detail(self):
        HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        response = self.client.get(reverse('habit_detail', args=[self.habit.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_streak'], 1)
        self.assertEqual(len(response.context['grid']), 7)

    # --- Toggle de hábitos ---
    def _toggle(self, habit, payload):
        return self.client.post(
            reverse('toggle_habit', args=[habit.id]),
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_toggle_habit_creates_and_updates_record(self):
        response = self._toggle(self.habit, {'date': today().isoformat(), 'completed': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['current_streak'], 1)
        self.assertTrue(HabitRecord.objects.get(habit=self.habit, date=today()).completed)

        self._toggle(self.habit, {'date': today().isoformat(), 'completed': False})
        self.assertFalse(HabitRecord.objects.get(habit=self.habit, date=today()).completed)
        self.assertEqual(HabitRecord.objects.count(), 1)

    def test_toggle_habit_rejects_future_date(self):
        response = self._toggle(self.habit, {'date': (today() + timedelta(days=1)).isoformat(), 'completed': True})
        self.assertEqual(response.status_code, 400)

    def test_toggle_habit_rejects_bad_date(self):
        response = self._toggle(self.habit, {'date': 'not-a-date', 'completed': True})
        self.assertEqual(response.status_code, 400)

    def test_toggle_habit_other_user_404(self):
        foreign = Habit.objects.create(user=self.other, name='Ajeno')
        response = self._toggle(foreign, {'completed': True})
        self.assertEqual(response.status_code, 404)

    def test_toggle_habit_requires_post(self):
        response = self.client.get(reverse('toggle_habit', args=[self.habit.id]))
        self.assertEqual(response.status_code, 405)

    def test_toggle_habit_record_ajax_invalid_json(self):
        record = HabitRecord.objects.create(habit=self.habit, date=today(), completed=False)
        response = self.client.post(
            reverse('toggle_habit_record', args=[record.id]),
            data='invalid-json',
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'status': 'error', 'message': 'Invalid JSON'})

    def test_toggle_habit_record_ajax_invalid_request(self):
        record = HabitRecord.objects.create(habit=self.habit, date=today(), completed=False)
        response = self.client.get(reverse('toggle_habit_record', args=[record.id]))
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'status': 'error', 'message': 'Invalid request'})

    def test_toggle_habit_record_other_user_returns_404(self):
        foreign = Habit.objects.create(user=self.other, name='Ajeno')
        record = HabitRecord.objects.create(habit=foreign, date=today())
        response = self.client.post(
            reverse('toggle_habit_record', args=[record.id]),
            data=json.dumps({'completed': True}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 404)

    def test_toggle_habit_record_accepts_form_data(self):
        record = HabitRecord.objects.create(habit=self.habit, date=today(), completed=False)
        response = self.client.post(
            reverse('toggle_habit_record', args=[record.id]),
            {'completed': 'true'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        record.refresh_from_db()
        self.assertTrue(record.completed)

    # --- Reordenar ---
    def test_reorder_habit_ajax_invalid_method(self):
        response = self.client.get(reverse('reorder_habit'))
        self.assertEqual(response.status_code, 400)

    def test_reorder_task_ajax_invalid_method(self):
        response = self.client.get(reverse('reorder_task'))
        self.assertEqual(response.status_code, 400)

    def test_reorder_tasks_json(self):
        second = Task.objects.create(user=self.user, title='Second')
        response = self.client.post(
            reverse('reorder_task'),
            data=json.dumps({'task_ids': [second.id, self.task.id]}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        second.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual((second.order, self.task.order), (0, 1))

    def test_reorder_habits_form_data(self):
        second = Habit.objects.create(user=self.user, name='Second')
        response = self.client.post(
            reverse('reorder_habit'),
            {'habit_ids[]': [second.id, self.habit.id]},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        second.refresh_from_db()
        self.assertEqual(second.order, 0)

    def test_reorder_rejects_foreign_ids(self):
        foreign = Task.objects.create(user=self.other, title='Ajena', order=5)
        response = self.client.post(
            reverse('reorder_task'),
            data=json.dumps({'task_ids': [foreign.id, self.task.id]}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.order, 5)

    # --- Tareas ---
    def test_task_list_post_invalid(self):
        response = self.client.post(reverse('task_list'), {'priority': 'alta'})
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_edit_task_post_invalid(self):
        response = self.client.post(reverse('edit_task', args=[self.task.id]), {'title': '', 'priority': 'baja'})
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_task_list_filters(self):
        Task.objects.create(user=self.user, title='Comprar pan', priority='alta', due_date=today() - timedelta(days=1))
        response = self.client.get(reverse('task_list'), {'q': 'pan'})
        self.assertEqual([t.title for t in response.context['tasks']], ['Comprar pan'])
        response = self.client.get(reverse('task_list'), {'status': 'overdue'})
        self.assertEqual([t.title for t in response.context['tasks']], ['Comprar pan'])
        response = self.client.get(reverse('task_list'), {'status': 'no_date'})
        self.assertEqual([t.title for t in response.context['tasks']], ['Test Task'])

    def test_complete_and_uncomplete_task(self):
        self.client.post(reverse('complete_task', args=[self.task.id]))
        self.task.refresh_from_db()
        self.assertTrue(self.task.completed)
        self.assertIsNotNone(self.task.completed_at)
        self.client.post(reverse('uncomplete_task', args=[self.task.id]))
        self.task.refresh_from_db()
        self.assertFalse(self.task.completed)

    def test_complete_task_redirects_to_safe_next(self):
        response = self.client.post(reverse('complete_task', args=[self.task.id]), {'next': reverse('dashboard')})
        self.assertRedirects(response, reverse('dashboard'))

    def test_complete_task_ignores_external_next(self):
        response = self.client.post(reverse('complete_task', args=[self.task.id]), {'next': 'https://evil.example.com/'})
        self.assertRedirects(response, reverse('task_list'))

    def test_complete_task_get_does_not_modify(self):
        self.client.get(reverse('complete_task', args=[self.task.id]))
        self.task.refresh_from_db()
        self.assertFalse(self.task.completed)

    def test_clear_completed_tasks(self):
        Task.objects.create(user=self.user, title='Hecha', completed=True)
        Task.objects.create(user=self.other, title='Hecha ajena', completed=True)
        self.client.post(reverse('clear_completed_tasks'))
        self.assertFalse(Task.objects.filter(user=self.user, completed=True).exists())
        self.assertTrue(Task.objects.filter(user=self.other, completed=True).exists())

    def test_delete_task_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('delete_task', args=[self.task.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(id=self.task.id).exists())

    def test_complete_task_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('complete_task', args=[self.task.id]))
        self.assertEqual(response.status_code, 302)

    def test_uncomplete_task_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('uncomplete_task', args=[self.task.id]))
        self.assertEqual(response.status_code, 302)

    # --- Informes ---
    def test_progress_report_view_with_date_range(self):
        response = self.client.get(reverse('progress_report'), {'start_date': '2024-01-01', 'end_date': '2024-01-31'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('habit_data', response.context)
        self.assertEqual(len(response.context['chart_labels']), 31)

    def test_progress_report_invalid_range_falls_back(self):
        response = self.client.get(reverse('progress_report'), {'start_date': '2024-01-31', 'end_date': '2024-01-01'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['chart_labels']), 30)

    def test_progress_report_rates(self):
        HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        start = today() - timedelta(days=1)
        response = self.client.get(reverse('progress_report'), {'start_date': start.isoformat(), 'end_date': today().isoformat()})
        data = response.context['habit_data'][0]
        self.assertEqual(data['chart_data'], [0.0, 50.0])
        self.assertEqual(response.context['chart_payload']['daily'], [0, 100.0])

    def test_weekly_view_context(self):
        response = self.client.get(reverse('weekly_view'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('week_days', response.context)
        self.assertIn('tasks_by_day', response.context)
        self.assertIn('habit_records', response.context)
        self.assertTrue(response.context['is_current_week'])

    def test_weekly_view_navigation(self):
        response = self.client.get(reverse('weekly_view'), {'week': '2024-01-03'})
        self.assertEqual(response.context['start_of_week'], date(2024, 1, 1))
        self.assertFalse(response.context['is_current_week'])

    def test_weekly_view_shows_tasks_on_due_date(self):
        Task.objects.create(user=self.user, title='Semana', due_date=date(2024, 1, 3))
        response = self.client.get(reverse('weekly_view'), {'week': '2024-01-03'})
        self.assertEqual([t.title for t in response.context['tasks_by_day'][date(2024, 1, 3)]], ['Semana'])

    # --- Exportación ---
    def test_export_habits_csv(self):
        HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        response = self.client.get(reverse('export_data', args=['habits']))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('Test Habit', response.content.decode('utf-8'))

    def test_export_tasks_csv_only_own(self):
        Task.objects.create(user=self.other, title='Secreta')
        content = self.client.get(reverse('export_data', args=['tasks'])).content.decode('utf-8')
        self.assertIn('Test Task', content)
        self.assertNotIn('Secreta', content)

    def test_export_unknown_kind_404(self):
        response = self.client.get(reverse('export_data', args=['otra']))
        self.assertEqual(response.status_code, 404)
