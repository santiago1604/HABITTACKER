from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """Multiplica el valor por el argumento"""
    return float(value) * float(arg)