from django import template
register = template.Library()
@register.filter
def money(value): return f'₦{value:,.2f}'
@register.filter
def tone(value): return {'Paid': 'green', 'Part paid': 'amber', 'Overpaid': 'red'}.get(value, 'neutral')
