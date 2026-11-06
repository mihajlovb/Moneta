from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Account, Budget, Category, Goal, Transaction, UserPreference

User = get_user_model()


# ── Helpers ────────────────────────────────────────────────────────────────

def colored_amount(amount, positive=True):
    color = '#059669' if positive else '#DC2626'
    amt = f"{float(amount):,.2f}"
    return format_html('<strong style="color:{}">{}</strong>', color, amt)


# ── Inlines ────────────────────────────────────────────────────────────────

class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    fields = ('date', 'merchant', 'type', 'amount', 'category')
    readonly_fields = ('date', 'merchant', 'type', 'amount', 'category')
    ordering = ('-date',)
    max_num = 10
    can_delete = False
    show_change_link = True
    verbose_name = _('Recent transaction')
    verbose_name_plural = _('Recent transactions (last 10)')


class BudgetInline(admin.TabularInline):
    model = Budget
    extra = 1
    fields = ('category', 'amount', 'month')


# ── Account Admin ──────────────────────────────────────────────────────────

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display   = ('colored_name', 'user_link', 'type_badge', 'currency',
                      'initial_balance', 'balance_display', 'is_active', 'created_at')
    list_filter    = ('type', 'currency', 'is_active', 'include_in_net_worth')
    search_fields  = ('name', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'balance_display')
    ordering       = ('user', 'name')
    date_hierarchy = 'created_at'
    inlines        = [TransactionInline]

    fieldsets = (
        (_('Basic Info'), {
            'fields': ('user', 'name', 'type', 'color')
        }),
        (_('Financial'), {
            'fields': ('initial_balance', 'currency', 'balance_display')
        }),
        (_('Settings'), {
            'fields': ('is_active', 'include_in_net_worth', 'created_at')
        }),
    )

    def colored_name(self, obj):
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:6px;">'
            '<span style="width:12px;height:12px;border-radius:50%;background:{};display:inline-block"></span>'
            '<strong>{}</strong></span>',
            obj.color, obj.name
        )
    colored_name.short_description = _('Account')
    colored_name.admin_order_field = 'name'

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__username'

    def type_badge(self, obj):
        colors = {
            'checking':    '#6366F1',
            'debit':       '#8B5CF6',
            'savings':     '#10B981',
            'cash':        '#F59E0B',
            'credit_card': '#EF4444',
            'investment':  '#3B82F6',
        }
        color = colors.get(obj.type, '#94A3B8')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600">{}</span>',
            color, obj.get_type_display()
        )
    type_badge.short_description = _('Type')
    type_badge.admin_order_field = 'type'

    def balance_display(self, obj):
        bal = obj.current_balance
        return colored_amount(bal, bal >= 0)
    balance_display.short_description = _('Current balance')


# ── Category Admin ─────────────────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ('icon_name', 'type_badge', 'user_display', 'transaction_count')
    list_filter   = ('type',)
    search_fields = ('name',)
    ordering      = ('type', 'name')

    def icon_name(self, obj):
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:8px;">'
            '<span style="width:28px;height:28px;border-radius:8px;background:{};display:inline-flex;align-items:center;justify-content:center;font-size:14px">{}</span>'
            '<strong>{}</strong></span>',
            obj.color + '22', obj.icon, obj.name
        )
    icon_name.short_description = _('Category')
    icon_name.admin_order_field = 'name'

    def type_badge(self, obj):
        color = '#10B981' if obj.type == 'income' else '#EF4444'
        label = _('Income') if obj.type == 'income' else _('Expense')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600">{}</span>',
            color, label
        )
    type_badge.short_description = _('Type')
    type_badge.admin_order_field = 'type'

    def user_display(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return format_html('<span style="color:#94A3B8;font-style:italic">{}</span>', _('Default'))
    user_display.short_description = _('User')

    def transaction_count(self, obj):
        count = obj.transactions.count()
        return format_html('<span style="font-weight:600">{}</span>', count)
    transaction_count.short_description = _('Transactions')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(tx_count=Count('transactions'))


# ── Transaction Admin ──────────────────────────────────────────────────────

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display   = ('date', 'merchant', 'user_link', 'type_amount',
                      'category_display', 'account_display', 'is_recurring')
    list_filter    = ('type', 'is_recurring', 'category', 'account')
    search_fields  = ('merchant', 'notes', 'user__username')
    ordering       = ('-date', '-created_at')
    date_hierarchy = 'date'
    readonly_fields = ('created_at', 'signed_amount_display')

    fieldsets = (
        (_('Transaction Details'), {
            'fields': ('user', 'date', 'merchant', 'type', 'amount', 'signed_amount_display')
        }),
        (_('Classification'), {
            'fields': ('account', 'category', 'notes', 'is_recurring')
        }),
        (_('Meta'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = _('User')
    user_link.admin_order_field = 'user__username'

    def type_amount(self, obj):
        positive = obj.type == 'income'
        sign = '+' if positive else '−'
        color = '#059669' if positive else '#DC2626'
        amt = f"{float(obj.amount):,.2f}"
        return format_html(
            '<strong style="color:{};font-size:13px">{}{}</strong>',
            color, sign, amt
        )
    type_amount.short_description = _('Amount')
    type_amount.admin_order_field = 'amount'

    def category_display(self, obj):
        if not obj.category:
            return format_html('<span style="color:#94A3B8">—</span>')
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:4px;">'
            '<span style="width:8px;height:8px;border-radius:50%;background:{};display:inline-block"></span>{} {}</span>',
            obj.category.color, obj.category.icon, obj.category.name
        )
    category_display.short_description = _('Category')
    category_display.admin_order_field = 'category__name'

    def account_display(self, obj):
        return format_html(
            '<span style="display:inline-flex;align-items:center;gap:4px;">'
            '<span style="width:8px;height:8px;border-radius:50%;background:{};display:inline-block"></span>{}</span>',
            obj.account.color, obj.account.name
        )
    account_display.short_description = _('Account')
    account_display.admin_order_field = 'account__name'

    def signed_amount_display(self, obj):
        return colored_amount(obj.amount, obj.type == 'income')
    signed_amount_display.short_description = _('Amount')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'category', 'account')


# ── Budget Admin ────────────────────────────────────────────────────────────

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display  = ('category_display', 'user_link', 'month', 'limit_display',
                     'spent_display', 'progress_bar', 'status_badge')
    list_filter   = ('month', 'category')
    search_fields = ('user__username', 'category__name')
    ordering      = ('-month', 'category__name')
    date_hierarchy = 'month'

    def category_display(self, obj):
        return format_html('{} {}', obj.category.icon, obj.category.name)
    category_display.short_description = _('Category')
    category_display.admin_order_field = 'category__name'

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = _('User')

    def limit_display(self, obj):
        return format_html('<strong>{}</strong>', f"{float(obj.amount):,.2f}")
    limit_display.short_description = _('Limit')
    limit_display.admin_order_field = 'amount'

    def spent_display(self, obj):
        spent = obj.spent
        color = '#EF4444' if spent > obj.amount else '#64748B'
        return format_html('<span style="color:{};font-weight:600">{}</span>', color, f"{float(spent):,.2f}")
    spent_display.short_description = _('Spent')

    def progress_bar(self, obj):
        pct = min(obj.percent_used, 100)
        if obj.status == 'over':
            color = '#EF4444'
        elif obj.status == 'warning':
            color = '#F59E0B'
        else:
            color = '#10B981'
        return format_html(
            '<div style="width:120px;height:8px;background:#E2E8F0;border-radius:99px;overflow:hidden">'
            '<div style="width:{}%;height:100%;background:{};border-radius:99px"></div>'
            '</div> <small style="color:#64748B">{}%</small>',
            pct, color, obj.percent_used
        )
    progress_bar.short_description = _('Progress')

    def status_badge(self, obj):
        labels = {'ok': ('•', '#10B981', _('OK')),
                  'warning': ('•', '#F59E0B', _('Warning')),
                  'over': ('•', '#EF4444', _('Over budget'))}
        icon, color, label = labels.get(obj.status, ('', '#64748B', '?'))
        return format_html(
            '<span style="color:{};font-weight:600;font-size:12px">{} {}</span>',
            color, icon, label
        )
    status_badge.short_description = _('Status')


# ── Goal Admin ──────────────────────────────────────────────────────────────

@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display  = ('goal_name', 'user_link', 'target_display', 'saved_display',
                     'progress_bar', 'deadline', 'days_left_display')
    list_filter   = ('deadline',)
    search_fields = ('name', 'user__username')
    ordering      = ('deadline', 'name')
    readonly_fields = ('created_at', 'percent')

    def goal_name(self, obj):
        return format_html('<strong>{}</strong>', obj.name)
    goal_name.short_description = _('Goal')
    goal_name.admin_order_field = 'name'

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = _('User')

    def target_display(self, obj):
        return format_html('<strong>{}</strong>', f"{float(obj.target_amount):,.2f}")
    target_display.short_description = _('Target')
    target_display.admin_order_field = 'target_amount'

    def saved_display(self, obj):
        return colored_amount(obj.saved_amount, True)
    saved_display.short_description = _('Saved')

    def progress_bar(self, obj):
        pct = obj.percent
        return format_html(
            '<div style="width:120px;height:8px;background:#E2E8F0;border-radius:99px;overflow:hidden">'
            '<div style="width:{}%;height:100%;background:#6366F1;border-radius:99px"></div>'
            '</div> <small style="color:#6366F1;font-weight:600">{}%</small>',
            pct, pct
        )
    progress_bar.short_description = _('Progress')

    def days_left_display(self, obj):
        dl = obj.days_left
        if dl is None:
            return '—'
        if dl < 0:
            return format_html('<span style="color:#EF4444;font-weight:600">• {} {}</span>', abs(dl), _('overdue'))
        if dl < 30:
            return format_html('<span style="color:#F59E0B;font-weight:600">{} {}</span>', dl, _('days'))
        return format_html('<span style="color:#64748B">{} {}</span>', dl, _('days'))
    days_left_display.short_description = _('Days left')


# ── Admin site customisation ────────────────────────────────────────────────

class MonetaAdminSite(admin.AdminSite):
    site_header  = 'Moneta Admin'
    site_title   = 'Moneta'
    index_title  = _('Finance Management Dashboard')

admin.site.site_header  = 'Moneta Admin'
admin.site.site_title   = 'Moneta'
admin.site.index_title  = _('Finance Management Dashboard')


# ── Admin index stats context ───────────────────────────────────────────────

from django.contrib.admin import AdminSite
from django.template.response import TemplateResponse

_original_index = AdminSite.index

def custom_index(self, request, extra_context=None):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    extra_context = extra_context or {}
    total_tx = Transaction.objects.count()
    total_users = User.objects.count()
    total_budgets = Budget.objects.count()
    total_goals = Goal.objects.count()
    from .services import to_mkd
    from decimal import Decimal
    all_transactions = Transaction.objects.select_related('account').all()
    total_income = sum((to_mkd(t.amount, t.account.currency) for t in all_transactions if t.type == 'income'), Decimal('0.00'))
    total_expense = sum((to_mkd(t.amount, t.account.currency) for t in all_transactions if t.type == 'expense'), Decimal('0.00'))
    extra_context['admin_stats'] = [
        {'icon': 'U', 'label': _('Users'),        'value': total_users,   'color': '#6366F1'},
        {'icon': 'T', 'label': _('Transactions'), 'value': total_tx,      'color': '#0EA5E9'},
        {'icon': 'I', 'label': _('Total Income'),  'value': f'{total_income:,.0f}', 'color': '#10B981'},
        {'icon': 'E', 'label': _('Total Expenses'),'value': f'{total_expense:,.0f}','color': '#EF4444'},
        {'icon': 'B', 'label': _('Budgets'),       'value': total_budgets, 'color': '#F59E0B'},
        {'icon': 'G', 'label': _('Goals'),         'value': total_goals,   'color': '#8B5CF6'},
    ]
    return _original_index(self, request, extra_context)

AdminSite.index = custom_index


# ── User preferences ─────────────────────────────────────────────────────────

@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'preferred_currency', 'theme', 'budget_alerts', 'transaction_alerts', 'weekly_summary', 'updated_at')
    list_filter = ('preferred_currency', 'theme', 'budget_alerts', 'transaction_alerts', 'weekly_summary')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('updated_at',)
