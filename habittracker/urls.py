"""
URL configuration for habittracker project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from tracker import views as tracker_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Autenticación
    path('register/', tracker_views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='tracker/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='tracker/logout.html'), name='logout'),
    
    # Dashboard
    path('', tracker_views.dashboard, name='dashboard'),
    
    # Hábitos
    path('habits/', tracker_views.habit_list, name='habit_list'),
    path('habits/new/', tracker_views.habit_list, name='new_habit'),
    path('habits/<int:habit_id>/edit/', tracker_views.edit_habit, name='edit_habit'),
    path('habits/<int:habit_id>/delete/', tracker_views.delete_habit, name='delete_habit'),
    path('habit-record/<int:record_id>/toggle/', tracker_views.toggle_habit_record, name='toggle_habit_record'),
    path('habits/reorder/', tracker_views.reorder_habit, name='reorder_habit'),
    
    # Tareas
    path('tasks/', tracker_views.task_list, name='task_list'),
    path('tasks/new/', tracker_views.task_list, name='new_task'),
    path('tasks/<int:task_id>/edit/', tracker_views.edit_task, name='edit_task'),
    path('tasks/<int:task_id>/delete/', tracker_views.delete_task, name='delete_task'),
    path('tasks/<int:task_id>/complete/', tracker_views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/uncomplete/', tracker_views.uncomplete_task, name='uncomplete_task'),
    path('tasks/reorder/', tracker_views.reorder_task, name='reorder_task'),
    
    # Vistas adicionales
    path('progress/', tracker_views.progress_report, name='progress_report'),
    path('weekly/', tracker_views.weekly_view, name='weekly_view'),
    
]