"""Helpers for loading and keeping a user's preferences consistent across pages."""


def get_user_preferences(request):
    from .models import UserPreference

    preferences, _ = UserPreference.objects.get_or_create(
        user=request.user,
        defaults={
            'preferred_currency': request.session.get('preferred_currency', 'MKD'),
            'theme': request.session.get('preferred_theme', 'light'),
        },
    )
    request.session['preferred_currency'] = preferences.preferred_currency
    request.session['preferred_theme'] = preferences.theme
    return preferences
