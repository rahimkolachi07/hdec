import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_item(d, key):
    """Dict lookup: {{ my_dict|get_item:key }}"""
    if isinstance(d, dict):
        return d.get(key, {})
    return {}

@register.filter
def safe_json(value):
    """Serialize any Python object to safe JSON for use in <script> tags."""
    return mark_safe(json.dumps(value, default=str))
