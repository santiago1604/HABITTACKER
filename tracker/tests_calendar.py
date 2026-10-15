from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Habit, HabitRecord, Task


def today():
    return timezone.localdate()


class CalendarViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cal', password='12345')
        self.other = User.objects.create_user(username='other', password='12345')
        self.client.login(username='cal', password='12345')
        self.habit = Habit.objects.create(user=self.user, name='Meditar', priority='alta')

    # --- Día ---
    def test_daily_view_defaults_to_today(self):
        HabitRecord.objects.create(habit=self.habit, date=today(), completed=True)
        response = self.client.get(reverse('daily_view'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_today'])
        self.assertEqual((response.context['habits_done'], response.context['habits_total']), (1, 1))
        self.assertContains(response, 'Meditar')

    def test_daily_view_specific_date_and_tasks(self):
        Task.objects.create(user=self.user, title='Due', due_date=date(2024, 3, 5))
        Task.objects.create(user=self.other, title='Ajena', due_date=date(2024, 3, 5))
        response = self.client.get(reverse('daily_view'), {'date': '2024-03-05'})
        self.assertEqual(response.context['day'], date(2024, 3, 5))
        self.assertEqual([t.title for t in response.context['tasks_due']], ['Due'])
        self.assertEqual(response.context['prev_day'], '2024-03-04')
        self.assertEqual(response.context['next_day'], '2024-03-06')

    def test_daily_view_overdue_only_today(self):
        Task.objects.create(user=self.user, title='Vencida', due_date=today() - timedelta(days=2))
        response = self.client.get(reverse('daily_view'))
        self.assertEqual([t.title for t in response.context['overdue_tasks']], ['Vencida'])
        response = self.client.get(reverse('daily_view'), {'date': (today() - timedelta(days=1)).isoformat()})
        self.assertEqual(list(response.context['overdue_tasks']), [])

    def test_daily_view_completed_other_tasks(self):
        Task.objects.create(user=self.user, title='Sin fecha').mark_completed(True)
        response = self.client.get(reverse('daily_view'))
        self.assertEqual([t.title for t in response.context['completed_other']], ['Sin fecha'])

    def test_daily_view_invalid_date_falls_back(self):
        response = self.client.get(reverse('daily_view'), {'date': 'xx'})
        self.assertEqual(response.context['day'], today())

    def test_daily_view_future_disables_checkboxes(self):
        response = self.client.get(reverse('daily_view'), {'date': (today() + timedelta(days=3)).isoformat()})
        self.assertTrue(response.context['is_future'])
        self.assertContains(response, 'disabled')

    # --- Mes ---
    def test_monthly_view_grid_and_summary(self):
        HabitRecord.objects.create(habit=self.habit, date=date(2024, 2, 10), completed=True)
        response = self.client.get(reverse('monthly_view'), {'month': '2024-02'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['month_start'], date(2024, 2, 1))
        self.assertEqual(response.context['month_end'], date(2024, 2, 29))
        weeks = response.context['calendar_weeks']
        self.assertTrue(all(len(week) == 7 for week in weeks))
        cells = {c['date']: c for week in weeks for c in week}
        self.assertEqual(cells[date(2024, 2, 10)]['level'], 4)
        self.assertIsNone(cells[date(2024, 2, 9)]['level'])  # el hábito aún no existía
        self.assertEqual(cells[date(2024, 2, 11)]['level'], 0)
        summary = response.context['habit_summary'][0]
        self.assertEqual((summary['done'], summary['eligible'], summary['rate']), (1, 20, 5))
        self.assertEqual(response.context['perfect_days'], 1)
        self.assertEqual(response.context['prev_month'], '2024-01')
        self.assertEqual(response.context['next_month'], '2024-03')

    def test_monthly_view_tasks_in_cells(self):
        for i in range(5):
            Task.objects.create(user=self.user, title=f'T{i}', due_date=date(2024, 2, 15))
        response = self.client.get(reverse('monthly_view'), {'month': '2024-02'})
        cell = next(c for week in response.context['calendar_weeks'] for c in week if c['date'] == date(2024, 2, 15))
        self.assertEqual((len(cell['tasks']), cell['more_tasks']), (3, 2))
        self.assertEqual(response.context['tasks_due_count'], 5)

    def test_monthly_view_invalid_month_falls_back(self):
        response = self.client.get(reverse('monthly_view'), {'month': '2024-13'})
        self.assertEqual(response.context['month_start'], today().replace(day=1))
        self.assertTrue(response.context['is_current_month'])

    def test_monthly_view_december_navigation(self):
        response = self.client.get(reverse('monthly_view'), {'month': '2024-12'})
        self.assertEqual(response.context['next_month'], '2025-01')

    # --- Año ---
    def test_yearly_view(self):
        HabitRecord.objects.create(habit=self.habit, date=date(2024, 2, 10), completed=True)
        HabitRecord.objects.create(habit=self.habit, date=date(2024, 2, 11), completed=True)
        task = Task.objects.create(user=self.user, title='Hecha', completed=True)
        Task.objects.filter(pk=task.pk).update(completed_at=timezone.make_aware(datetime(2024, 5, 3, 12)))
        response = self.client.get(reverse('yearly_view'), {'year': '2024'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['months']), 12)
        self.assertEqual(response.context['total_done'], 2)
        self.assertEqual(response.context['active_days'], 2)
        self.assertEqual(response.context['best_month']['date'], date(2024, 2, 1))
        self.assertIsNone(response.context['months'][0]['rate'])  # enero: el hábito no existía
        self.assertEqual(response.context['months'][4]['tasks_completed'], 1)
        self.assertEqual(response.context['tasks_completed_year'], 1)
        self.assertEqual(response.context['habit_summary'][0]['best_streak'], 2)

    def test_yearly_view_habit_filter_ignores_foreign_habit(self):
        foreign = Habit.objects.create(user=self.other, name='Ajeno')
        response = self.client.get(reverse('yearly_view'), {'habit': foreign.id})
        self.assertIsNone(response.context['selected_habit'])
        response = self.client.get(reverse('yearly_view'), {'habit': self.habit.id})
        self.assertEqual(response.context['selected_habit'], self.habit)

    def test_yearly_view_invalid_year(self):
        response = self.client.get(reverse('yearly_view'), {'year': 'abc'})
        self.assertEqual(response.context['year'], today().year)

    def test_calendar_views_exclude_archived(self):
        Habit.objects.create(user=self.user, name='Archivado', archived=True)
        for name in ('daily_view', 'monthly_view', 'yearly_view'):
            self.assertNotContains(self.client.get(reverse(name)), 'Archivado')

    def test_calendar_views_require_login(self):
        self.client.logout()
        for name in ('daily_view', 'monthly_view', 'yearly_view'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
