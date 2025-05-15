from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Obtiene un elemento de un diccionario por clave"""
    return dictionary.get(key)

@register.filter
@stringfilter
def priority_color(priority):
    """Convierte prioridad a color de Bootstrap"""
    priority_colors = {
        'alta': 'danger',
        'media': 'warning',
        'baja': 'info',
    }
    return priority_colors.get(priority, 'secondary')