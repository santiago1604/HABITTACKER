from django.contrib import admin
from .models import Habit, HabitRecord, Task

@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'priority', 'created_at')
    list_filter = ('priority', 'user')
    search_fields = ('name', 'description')
    
@admin.register(HabitRecord)
class HabitRecordAdmin(admin.ModelAdmin):
    list_display = ('habit', 'date', 'completed')
    list_filter = ('completed', 'date')
    date_hierarchy = 'date'

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'priority', 'due_date', 'completed')
    list_filter = ('priority', 'completed', 'user')
    search_fields = ('title', 'description')