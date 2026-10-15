"""URL configuration for habittracker project."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from tracker import views as tracker_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Autenticación
    path('register/', tracker_views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='tracker/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Dashboard
    path('', tracker_views.dashboard, name='dashboard'),

    # Hábitos
    path('habits/', tracker_views.habit_list, name='habit_list'),
    path('habits/new/', tracker_views.habit_list, name='new_habit'),
    path('habits/reorder/', tracker_views.reorder_habit, name='reorder_habit'),
    path('habits/<int:habit_id>/', tracker_views.habit_detail, name='habit_detail'),
    path('habits/<int:habit_id>/edit/', tracker_views.edit_habit, name='edit_habit'),
    path('habits/<int:habit_id>/delete/', tracker_views.delete_habit, name='delete_habit'),
    path('habits/<int:habit_id>/archive/', tracker_views.archive_habit, name='archive_habit'),
    path('habits/<int:habit_id>/toggle/', tracker_views.toggle_habit, name='toggle_habit'),
    path('habit-record/<int:record_id>/toggle/', tracker_views.toggle_habit_record, name='toggle_habit_record'),

    # Tareas
    path('tasks/', tracker_views.task_list, name='task_list'),
    path('tasks/new/', tracker_views.task_list, name='new_task'),
    path('tasks/reorder/', tracker_views.reorder_task, name='reorder_task'),
    path('tasks/clear-completed/', tracker_views.clear_completed_tasks, name='clear_completed_tasks'),
    path('tasks/<int:task_id>/edit/', tracker_views.edit_task, name='edit_task'),
    path('tasks/<int:task_id>/delete/', tracker_views.delete_task, name='delete_task'),
    path('tasks/<int:task_id>/complete/', tracker_views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/uncomplete/', tracker_views.uncomplete_task, name='uncomplete_task'),

    # Vistas adicionales
    path('progress/', tracker_views.progress_report, name='progress_report'),
    path('day/', tracker_views.daily_view, name='daily_view'),
    path('weekly/', tracker_views.weekly_view, name='weekly_view'),
    path('month/', tracker_views.monthly_view, name='monthly_view'),
    path('year/', tracker_views.yearly_view, name='yearly_view'),
    path('export/<str:kind>.csv', tracker_views.export_data, name='export_data'),
]
