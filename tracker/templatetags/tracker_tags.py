from django import template
from django.template.defaultfilters import stringfilter

from ..models import priority_color as _priority_color

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Obtiene un elemento de un diccionario por clave (None si no aplica)"""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None


@register.filter
@stringfilter
def priority_color(priority):
    """Convierte prioridad a color de Bootstrap"""
    return _priority_color(priority)


@register.filter
def multiply(value, arg):
    """Multiplica el valor por el argumento"""
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0
