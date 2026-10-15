from django.contrib import admin

from .models import Habit, HabitRecord, Task


class HabitRecordInline(admin.TabularInline):
    model = HabitRecord
    extra = 0
    ordering = ('-date',)


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'priority', 'archived', 'created_at')
    list_filter = ('priority', 'archived', 'user')
    search_fields = ('name', 'description')
    inlines = [HabitRecordInline]


@admin.register(HabitRecord)
class HabitRecordAdmin(admin.ModelAdmin):
    list_display = ('habit', 'date', 'completed')
    list_filter = ('completed', 'date')
    list_select_related = ('habit',)
    date_hierarchy = 'date'


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'priority', 'due_date', 'completed', 'completed_at')
    list_filter = ('priority', 'completed', 'user')
    search_fields = ('title', 'description')
    date_hierarchy = 'due_date'
