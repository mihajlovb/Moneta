import django_filters
from django import forms

from .models import Category, Transaction


class TransactionFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(
        field_name='date', lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='From date',
    )
    date_to = django_filters.DateFilter(
        field_name='date', lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='To date',
    )
    type = django_filters.ChoiceFilter(
        choices=[('', 'All types'), ('income', 'Income'), ('expense', 'Expense')],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Type',
        empty_label=None,
    )
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.none(),
        empty_label='All categories',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Category',
    )
    merchant = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Search merchant…'}),
        label='Merchant',
    )

    class Meta:
        model = Transaction
        fields = ['type', 'category', 'merchant', 'date_from', 'date_to']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.filters['category'].queryset = Category.objects.filter(user=user)
