from django.utils.translation import gettext_lazy as _

from .preferences import get_user_preferences


def nav_items(request):
    from django.urls import reverse
    items = [
        (reverse('finance:dashboard'),    '◫', _('Home')),
        (reverse('finance:transactions'), '↔', _('Transactions')),
        (reverse('finance:accounts'),     '▤', _('Accounts')),
        (reverse('finance:budgets'),      '▦', _('Budgets')),
        (reverse('finance:goals'),        '◎', _('Goals')),
        (reverse('finance:recurring'),    '↻', _('Recurring')),
        (reverse('finance:reports'),      '▥', _('Reports')),
        (reverse('finance:markets'),      '⌁', _('Markets')),
        (reverse('finance:settings'),     '⚙', _('Settings')),
    ]
    # Mobile bottom bar keeps the primary destinations only; Recurring and Reports stay in the sidebar.
    mobile_items = [item for item in items if item[0] not in (reverse('finance:recurring'), reverse('finance:reports'))]
    result = {'nav_items': items, 'mobile_nav_items': mobile_items}
    if request.user.is_authenticated:
        preferences = get_user_preferences(request)
        result.update({
            'user_preferences': preferences,
            'preferred_currency': preferences.preferred_currency,
            'preferred_theme': preferences.theme,
        })
    else:
        result.update({'preferred_currency': 'MKD', 'preferred_theme': 'light'})
    return result
