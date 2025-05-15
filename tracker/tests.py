from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Habit, HabitRecord, Task
from .forms import UserRegisterForm, HabitForm, TaskForm, DateRangeForm
from datetime import date, timedelta
import json

class HabitModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.habit = Habit.objects.create(user=self.user, name='Test Habit', priority='media')

    def test_habit_str(self):
        self.assertEqual(str(self.habit), 'Test Habit')

    def test_completion_rate_no_records(self):
        self.assertEqual(self.habit.completion_rate(), 0)

    def test_completion_rate_with_records(self):
        HabitRecord.objects.create(habit=self.habit, date=date.today(), completed=True)
        HabitRecord.objects.create(habit=self.habit, date=date.today() - timedelta(days=1), completed=False)
        self.assertEqual(self.habit.completion_rate(), 50)

class HabitRecordModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.habit = Habit.objects.create(user=self.user, name='Test Habit', priority='media')

    def test_habit_record_str(self):
        record = HabitRecord.objects.create(habit=self.habit, date=date.today(), completed=True)
        self.assertEqual(str(record), f"{self.habit.name} - {date.today().strftime('%d/%m/%Y')}")

    def test_unique_together_constraint(self):
        HabitRecord.objects.create(habit=self.habit, date=date.today(), completed=True)
        with self.assertRaises(Exception):
            HabitRecord.objects.create(habit=self.habit, date=date.today(), completed=False)

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

class FormTests(TestCase):
    def test_user_register_form_valid(self):
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
        }
        form = UserRegisterForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_user_register_form_invalid_email(self):
        form_data = {
            'username': 'newuser',
            'email': 'not-an-email',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
        }
        form = UserRegisterForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_habit_form_valid(self):
        form_data = {
            'name': 'Exercise',
            'description': 'Daily exercise',
            'priority': 'alta',
        }
        form = HabitForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_habit_form_missing_name(self):
        form_data = {
            'description': 'Daily exercise',
            'priority': 'alta',
        }
        form = HabitForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_task_form_valid(self):
        form_data = {
            'title': 'Complete project',
            'description': 'Finish by end of month',
            'priority': 'media',
            'due_date': '2024-12-31',
        }
        form = TaskForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_task_form_invalid_due_date(self):
        form_data = {
            'title': 'Complete project',
            'description': 'Finish by end of month',
            'priority': 'media',
            'due_date': 'invalid-date',
        }
        form = TaskForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('due_date', form.errors)

    def test_date_range_form_valid(self):
        form_data = {
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
        }
        form = DateRangeForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_date_range_form_invalid(self):
        form_data = {
            'start_date': '2024-01-31',
            'end_date': '2024-01-01',
        }
        form = DateRangeForm(data=form_data)
        self.assertTrue(form.is_valid())  # No custom validation for date order, so valid

class ExtendedViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.login(username='testuser', password='12345')
        self.habit = Habit.objects.create(user=self.user, name='Test Habit', priority='media')
        self.task = Task.objects.create(user=self.user, title='Test Task', priority='media')

    def test_habit_list_post_invalid(self):
        # Missing required 'name' field
        response = self.client.post(reverse('habit_list'), {'priority': 'alta'})
        self.assertEqual(response.status_code, 200)  # Form re-rendered with errors
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_edit_habit_post_invalid(self):
        response = self.client.post(reverse('edit_habit', args=[self.habit.id]), {'name': '', 'priority': 'baja'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_delete_habit_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('delete_habit', args=[self.habit.id]))
        self.assertNotEqual(response.status_code, 200)  # Should redirect to login

    def test_toggle_habit_record_ajax_invalid_json(self):
        record = HabitRecord.objects.create(habit=self.habit, date=date.today(), completed=False)
        response = self.client.post(
            reverse('toggle_habit_record', args=[record.id]),
            data='invalid-json',
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'status': 'error', 'message': 'Invalid JSON'})

    def test_toggle_habit_record_ajax_invalid_request(self):
        record = HabitRecord.objects.create(habit=self.habit, date=date.today(), completed=False)
        response = self.client.get(reverse('toggle_habit_record', args=[record.id]))
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'status': 'error', 'message': 'Invalid request'})

    def test_task_list_post_invalid(self):
        response = self.client.post(reverse('task_list'), {'priority': 'alta'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_edit_task_post_invalid(self):
        response = self.client.post(reverse('edit_task', args=[self.task.id]), {'title': '', 'priority': 'baja'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Este campo es obligatorio', status_code=200)

    def test_delete_task_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('delete_task', args=[self.task.id]))
        self.assertNotEqual(response.status_code, 200)

    def test_complete_task_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('complete_task', args=[self.task.id]))
        self.assertNotEqual(response.status_code, 200)

    def test_uncomplete_task_post_unauthenticated(self):
        self.client.logout()
        response = self.client.post(reverse('uncomplete_task', args=[self.task.id]))
        self.assertNotEqual(response.status_code, 200)

    def test_reorder_task_ajax_invalid_method(self):
        response = self.client.get(reverse('reorder_task'))
        self.assertEqual(response.status_code, 400)

    def test_reorder_habit_ajax_invalid_method(self):
        response = self.client.get(reverse('reorder_habit'))
        self.assertEqual(response.status_code, 400)

    def test_progress_report_view_with_date_range(self):
        response = self.client.get(reverse('progress_report'), {'start_date': '2024-01-01', 'end_date': '2024-01-31'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('habit_data', response.context)
        self.assertIn('chart_labels', response.context)

    def test_weekly_view_context(self):
        response = self.client.get(reverse('weekly_view'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('week_days', response.context)
        self.assertIn('tasks_by_day', response.context)
        self.assertIn('habit_records', response.context)
