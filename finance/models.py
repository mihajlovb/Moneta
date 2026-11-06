from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Account(models.Model):
    """Сметка / извор на пари (банка, кеш, картичка, штедна...)."""

    class Type(models.TextChoices):
        CHECKING = 'checking', _('Checking account')
        SAVINGS = 'savings', _('Savings account')
        CASH = 'cash', _('Cash')
        CREDIT_CARD = 'credit_card', _('Credit card')
        INVESTMENT = 'investment', _('Investments')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts'
    )
    name = models.CharField('Име', max_length=100)
    type = models.CharField('Тип', max_length=20, choices=Type.choices, default=Type.CHECKING)
    has_debit_card = models.BooleanField(
        'Има поврзана дебитна картичка', default=False,
        help_text='Картичката е платежен инструмент поврзан со оваа сметка и не претставува посебно салдо.'
    )
    initial_balance = models.DecimalField(
        'Почетно салдо', max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    CURRENCY_CHOICES = [
        ('MKD', 'MKD — Macedonian Denar'),
        ('EUR', 'EUR — Euro'),
        ('USD', 'USD — US Dollar'),
        ('GBP', 'GBP — British Pound'),
        ('CHF', 'CHF — Swiss Franc'),
    ]
    currency = models.CharField('Валута', max_length=3, default='MKD', choices=CURRENCY_CHOICES)
    color = models.CharField('Боја', max_length=7, default='#6366F1')
    is_active = models.BooleanField('Активна', default=True)
    include_in_net_worth = models.BooleanField('Вклучи во вкупен имот', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [('user', 'name')]
        verbose_name = 'Сметка'
        verbose_name_plural = 'Сметки'

    def __str__(self):
        return f'{self.name} ({self.currency})'

    @property
    def is_liability(self):
        return self.type == self.Type.CREDIT_CARD

    @property
    def current_balance(self):
        agg = self.transactions.aggregate(
            income=Sum('amount', filter=Q(type=Transaction.Type.INCOME)),
            expense=Sum('amount', filter=Q(type=Transaction.Type.EXPENSE)),
        )
        income = agg['income'] or Decimal('0.00')
        expense = agg['expense'] or Decimal('0.00')
        # Credit-card balance represents the amount owed, not an asset balance.
        if self.is_liability:
            return self.initial_balance + expense - income
        return self.initial_balance + income - expense


class Category(models.Model):
    """Категорија на трансакција (default категории се креираат автоматски за секој нов корисник)."""

    class Type(models.TextChoices):
        INCOME = 'income', _('Income')
        EXPENSE = 'expense', _('Expense')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='categories',
        null=True,
        blank=True,
    )
    name = models.CharField('Име', max_length=60)
    type = models.CharField('Тип', max_length=10, choices=Type.choices, default=Type.EXPENSE)
    color = models.CharField('Боја', max_length=7, default='#94A3B8')
    icon = models.CharField('Икона (emoji)', max_length=8, default='🏷️')

    class Meta:
        ordering = ['type', 'name']
        unique_together = [('user', 'name', 'type')]
        verbose_name = 'Категорија'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return f'{self.icon} {self.name}'


class Transaction(models.Model):
    """Единечна трансакција. Износот е секогаш позитивен; насоката ја одредува type."""

    class Type(models.TextChoices):
        INCOME = 'income', _('Income')
        EXPENSE = 'expense', _('Expense')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions'
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name='transactions', verbose_name='Сметка'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='Категорија',
    )
    type = models.CharField('Тип', max_length=10, choices=Type.choices, default=Type.EXPENSE)
    amount = models.DecimalField(
        'Износ',
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    date = models.DateField('Датум', default=timezone.localdate)
    merchant = models.CharField('Трговец / опис', max_length=150)
    notes = models.TextField('Забелешки', blank=True)
    is_recurring = models.BooleanField('Повторувачка', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', '-date']),
            models.Index(fields=['user', 'type', 'date']),
        ]
        verbose_name = 'Трансакција'
        verbose_name_plural = 'Трансакции'

    def __str__(self):
        sign = '+' if self.type == self.Type.INCOME else '-'
        return f'{self.date} {self.merchant} {sign}{self.amount}'

    @property
    def signed_amount(self):
        return self.amount if self.type == self.Type.INCOME else -self.amount


class Budget(models.Model):
    """Месечен буџет по категорија на расходи."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='budgets'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='budgets',
        limit_choices_to={'type': Category.Type.EXPENSE},
        verbose_name='Категорија',
    )
    amount = models.DecimalField(
        'Месечен лимит',
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    month = models.DateField('Месец (прв ден)')

    class Meta:
        ordering = ['-month', 'category__name']
        unique_together = [('user', 'category', 'month')]
        verbose_name = 'Буџет'
        verbose_name_plural = 'Буџети'

    def __str__(self):
        return f'{self.category.name} {self.month:%m/%Y}: {self.amount}'

    def save(self, *args, **kwargs):
        self.month = self.month.replace(day=1)
        super().save(*args, **kwargs)

    @property
    def spent(self):
        # Budget limits are expressed in MKD. Convert each transaction from its
        # account currency before comparing it with the limit.
        from .services import to_mkd
        transactions = Transaction.objects.filter(
            user=self.user, category=self.category, type=Transaction.Type.EXPENSE,
            date__year=self.month.year, date__month=self.month.month,
        ).select_related('account')
        total = sum((to_mkd(tx.amount, tx.account.currency) for tx in transactions), Decimal('0.00'))
        return total.quantize(Decimal('0.01'))

    @property
    def remaining(self):
        return self.amount - self.spent

    @property
    def percent_used(self):
        if not self.amount:
            return 0
        return min(int(self.spent / self.amount * 100), 999)

    @property
    def status(self):
        """ok / warning / over - за боење на progress bar."""
        p = self.percent_used
        if p >= 100:
            return 'over'
        if p >= 80:
            return 'warning'
        return 'ok'


class Goal(models.Model):
    """Цел за штедење."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals'
    )
    name = models.CharField('Име на цел', max_length=100)
    target_amount = models.DecimalField(
        'Целен износ', max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))]
    )
    saved_amount = models.DecimalField(
        'Заштедено', max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    deadline = models.DateField('Рок', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['deadline', 'name']
        verbose_name = 'Цел'
        verbose_name_plural = 'Цели'

    def __str__(self):
        return self.name

    @property
    def percent(self):
        if not self.target_amount:
            return 0
        return min(int(self.saved_amount / self.target_amount * 100), 100)

    @property
    def remaining(self):
        return max(self.target_amount - self.saved_amount, Decimal('0.00'))

    @property
    def days_left(self):
        if not self.deadline:
            return None
        return (self.deadline - date.today()).days


class UserPreference(models.Model):
    """Per-user display and notification preferences for Moneta."""

    CURRENCY_CHOICES = [
        ('MKD', 'MKD — Macedonian Denar'),
        ('EUR', 'EUR — Euro'),
        ('USD', 'USD — US Dollar'),
        ('GBP', 'GBP — British Pound'),
        ('CHF', 'CHF — Swiss Franc'),
    ]
    THEME_CHOICES = [('light', 'Light'), ('dark', 'Dark')]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    preferred_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='MKD')
    theme = models.CharField(max_length=8, choices=THEME_CHOICES, default='light')
    budget_alerts = models.BooleanField(default=True)
    transaction_alerts = models.BooleanField(default=True)
    weekly_summary = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Корисничка поставка'
        verbose_name_plural = 'Кориснички поставки'

    def __str__(self):
        return f'Preferences for {self.user}'
