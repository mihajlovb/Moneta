from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Account, Budget, Category, Goal, Transaction


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'account', 'category', 'amount', 'date', 'merchant', 'notes', 'is_recurring']
        widgets = {
            'type': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'account': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'step': '0.01', 'min': '0.01'}),
            'date': forms.DateInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'type': 'date'}),
            'merchant': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'placeholder': 'e.g. Grocery store'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'rows': 3}),
            'is_recurring': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded accent-indigo-600 cursor-pointer'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['account'].queryset = Account.objects.filter(user=user, is_active=True)
            self.fields['category'].queryset = Category.objects.filter(user=user)


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['name', 'type', 'has_debit_card', 'initial_balance', 'currency', 'color', 'include_in_net_worth']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'type': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'has_debit_card': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded accent-emerald-600 cursor-pointer'}),
            'initial_balance': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'step': '0.01'}),
            'currency': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'include_in_net_worth': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded accent-indigo-600 cursor-pointer'}),
        }


class BudgetForm(forms.ModelForm):
    # Native month picker submits YYYY-MM; parse it as the first day of that month.
    month = forms.DateField(input_formats=['%Y-%m'], widget=forms.DateInput(format='%Y-%m', attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'type': 'month'}))

    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month']
        widgets = {
            'category': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'step': '0.01'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.month:
            self.initial['month'] = self.instance.month.strftime('%Y-%m')
        elif not self.is_bound and not self.initial.get('month'):
            from django.utils import timezone
            self.initial['month'] = timezone.localdate().strftime('%Y-%m')
        self.user = user
        if user:
            self.fields['category'].queryset = Category.objects.filter(
                user=user, type=Category.Type.EXPENSE
            )

    def clean_month(self):
        value = self.cleaned_data['month']
        return value.replace(day=1)

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')
        month = cleaned.get('month')
        if category and month and hasattr(self, 'user') and self.user:
            duplicates = Budget.objects.filter(user=self.user, category=category, month=month)
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error('category', forms.ValidationError(
                    _('A budget already exists for this category and month. Edit the existing budget instead.')
                ))
        return cleaned


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ['name', 'target_amount', 'saved_amount', 'deadline']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500'}),
            'target_amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'step': '0.01'}),
            'saved_amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'step': '0.01'}),
            'deadline': forms.DateInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-slate-800 dark:text-slate-100 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500', 'type': 'date'}),
        }


class UserSettingsForm(forms.Form):
    """Validated profile and preference form for the Settings page."""

    first_name = forms.CharField(required=False, max_length=150, label='First name')
    last_name = forms.CharField(required=False, max_length=150, label='Last name')
    email = forms.EmailField(required=False, label='Email address')
    preferred_currency = forms.ChoiceField(choices=[
        ('MKD', 'MKD — Macedonian Denar'),
        ('EUR', 'EUR — Euro'),
        ('USD', 'USD — US Dollar'),
        ('GBP', 'GBP — British Pound'),
        ('CHF', 'CHF — Swiss Franc'),
    ], label='Display currency')
    theme = forms.ChoiceField(choices=[('light', 'Light'), ('dark', 'Dark')], label='Appearance')
    budget_alerts = forms.BooleanField(required=False, initial=True)
    transaction_alerts = forms.BooleanField(required=False, initial=True)
    weekly_summary = forms.BooleanField(required=False, initial=False)

    field_classes = (
        'w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-800 '
        'outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200 '
        'dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 dark:focus:ring-slate-600'
    )

    def __init__(self, *args, user=None, preferences=None, **kwargs):
        super().__init__(*args, **kwargs)
        initial = kwargs.get('initial', {})
        if user and not self.is_bound:
            initial.update({
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
            })
        if preferences and not self.is_bound:
            initial.update({
                'preferred_currency': preferences.preferred_currency,
                'theme': preferences.theme,
                'budget_alerts': preferences.budget_alerts,
                'transaction_alerts': preferences.transaction_alerts,
                'weekly_summary': preferences.weekly_summary,
            })
        self.initial.update(initial)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'sr-only peer'})
            else:
                field.widget.attrs.update({'class': self.field_classes})
