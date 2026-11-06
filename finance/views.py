from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from . import services
from .filters import TransactionFilter
from .forms import AccountForm, BudgetForm, GoalForm, TransactionForm, UserSettingsForm
from .models import Account, Budget, Category, Goal, Transaction
from .preferences import get_user_preferences


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    user = request.user
    today = date.today()
    this_month = services.month_start(today)
    preferences = get_user_preferences(request)
    preferred_currency = preferences.preferred_currency
    net_worth_mkd = services.net_worth(user)
    summary_mkd = services.month_summary(user, this_month)
    previous_month = services.add_months(this_month, -1)
    previous_summary_mkd = services.month_summary(user, previous_month)

    # Keep all comparisons in the same reporting currency before formatting.
    def change_percent(current, previous):
        if not previous:
            return 100 if current > 0 else 0
        return round(float((current - previous) / abs(previous) * 100))

    comparison = {
        'income_pct': change_percent(summary_mkd['income'], previous_summary_mkd['income']),
        'expense_pct': change_percent(summary_mkd['expense'], previous_summary_mkd['expense']),
        'income_has_previous': previous_summary_mkd['income'] > 0,
        'expense_has_previous': previous_summary_mkd['expense'] > 0,
        'previous_month': previous_month,
    }
    summary = dict(summary_mkd)
    previous_summary = dict(previous_summary_mkd)
    for item in (summary, previous_summary):
        for key in ('income', 'expense', 'net'):
            item[key] = services.from_mkd(item[key], preferred_currency)

    by_category = services.spending_by_category(user, this_month)
    for row in by_category:
        row['total'] = services.from_mkd(row['total'], preferred_currency)
    trend = services.monthly_trend(user, 6)
    for row in trend:
        row['income'] = services.from_mkd(row['income'], preferred_currency)
        row['expense'] = services.from_mkd(row['expense'], preferred_currency)

    budgets = list(Budget.objects.filter(user=user, month=this_month).select_related('category'))
    for budget in budgets:
        budget.display_amount = services.from_mkd(budget.amount, preferred_currency)
        budget.display_spent = services.from_mkd(budget.spent, preferred_currency)
        budget.display_remaining = services.from_mkd(budget.remaining, preferred_currency)
        budget.display_percent = min(budget.percent_used, 100)

    # A compact, real account snapshot gives users a quick route to their money.
    accounts = list(Account.objects.filter(user=user, is_active=True, include_in_net_worth=True))
    for account in accounts:
        account.display_balance = services.from_mkd(
            services.to_mkd(account.current_balance, account.currency), preferred_currency
        )
    accounts = accounts[:4]

    # Actionable alerts are derived from the user's real budget and transaction data.
    alerts = []
    over_budgets = [b for b in budgets if b.status == 'over']
    warning_budgets = [b for b in budgets if b.status == 'warning']
    if over_budgets:
        alerts.append({'level': 'danger', 'title': 'Budget limit exceeded', 'detail': over_budgets[0].category.name, 'count': len(over_budgets), 'url': 'finance:budgets'})
    elif warning_budgets:
        alerts.append({'level': 'warning', 'title': 'Budget getting close', 'detail': warning_budgets[0].category.name, 'count': len(warning_budgets), 'url': 'finance:budgets'})
    if summary_mkd['income'] > 0 and summary_mkd['expense'] > summary_mkd['income']:
        alerts.append({'level': 'info', 'title': 'Expenses are higher than income', 'detail': 'Review this month’s cash flow', 'count': 0, 'url': 'finance:reports'})

    goals = list(Goal.objects.filter(user=user))
    for goal in goals:
        goal.display_saved_amount = services.from_mkd(goal.saved_amount, preferred_currency)
        goal.display_target_amount = services.from_mkd(goal.target_amount, preferred_currency)

    context = {
        'net_worth': services.from_mkd(net_worth_mkd, preferred_currency),
        'display_currency': preferred_currency,
        'summary': summary,
        'previous_summary': previous_summary,
        'comparison': comparison,
        'by_category': by_category,
        'trend': trend,
        'has_trend_data': any(row['income'] or row['expense'] for row in trend),
        'accounts': accounts,
        'account_count': Account.objects.filter(user=user, is_active=True, include_in_net_worth=True).count(),
        'recent': Transaction.objects.filter(user=user).select_related('category', 'account')[:6],
        'budgets': budgets,
        'budget_count': len(budgets),
        'alerts': alerts,
        'goals': goals,
        'today': today,
    }
    return render(request, 'finance/dashboard.html', context)


# ── Transactions ───────────────────────────────────────────────────────────────

@login_required
def transaction_list(request):
    if request.GET.get('export') == 'csv':
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="moneta-transactions.csv"'
        response.write('\ufeff')  # Excel-friendly UTF-8 BOM
        writer = csv.writer(response)
        writer.writerow(['Date', 'Type', 'Amount', 'Currency', 'Account', 'Category', 'Merchant', 'Notes', 'Recurring'])
        rows = Transaction.objects.filter(user=request.user).select_related(
            'account', 'category'
        ).order_by('-date', '-created_at')
        for tx in rows:
            writer.writerow([
                tx.date.isoformat(), tx.get_type_display(), str(tx.amount),
                tx.account.currency, tx.account.name,
                tx.category.name if tx.category else '', tx.merchant,
                tx.notes, 'Yes' if tx.is_recurring else 'No',
            ])
        return response

    from django.db.models import Avg, Max, Min, Q
    qs = Transaction.objects.filter(user=request.user).select_related('category', 'account')
    f = TransactionFilter(request.GET, queryset=qs, user=request.user)
    # Date/count metadata can be aggregated in SQL, but money values must be
    # converted row-by-row because transactions may belong to different currencies.
    from decimal import Decimal
    from .services import to_mkd
    filtered_transactions = list(f.qs.select_related('account'))
    income = sum((to_mkd(t.amount, t.account.currency) for t in filtered_transactions if t.type == 'income'), Decimal('0.00'))
    expense = sum((to_mkd(t.amount, t.account.currency) for t in filtered_transactions if t.type == 'expense'), Decimal('0.00'))
    expense_values = [to_mkd(t.amount, t.account.currency) for t in filtered_transactions if t.type == 'expense']
    all_values = [to_mkd(t.amount, t.account.currency) for t in filtered_transactions]
    preferences = get_user_preferences(request)
    display_currency = preferences.preferred_currency
    agg = {
        'income': services.from_mkd(income, display_currency),
        'expense': services.from_mkd(expense, display_currency),
        'largest_expense': services.from_mkd(max(expense_values), display_currency) if expense_values else None,
        'avg': services.from_mkd((sum(all_values, Decimal('0.00')) / len(all_values)), display_currency) if all_values else None,
        'first_date': min((t.date for t in filtered_transactions), default=None),
        'last_date': max((t.date for t in filtered_transactions), default=None),
    }
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get('page'))
    from datetime import date as _date
    this_month = _date.today().replace(day=1).isoformat()
    from django.utils.translation import gettext as _
    qs_str = '&'.join(f'{k}={v}' for k,v in request.GET.items() if k not in ('type','page'))
    qs_pfx = f'?{qs_str}&' if qs_str else '?'
    type_pills = [
        (f'{qs_pfx}', _('All'), not request.GET.get('type')),
        (f'{qs_pfx}type=income', _('Income'), request.GET.get('type')=='income'),
        (f'{qs_pfx}type=expense', _('Expenses'), request.GET.get('type')=='expense'),
        (f'{qs_pfx}date_from={this_month}', _('This month'), request.GET.get('date_from')==this_month),
    ]
    return render(request, 'finance/transactions.html', {
        'filter': f, 'page': page, 'totals': agg,
        'total_count': f.qs.count(),
        'this_month': this_month,
        'type_pills': type_pills, 'display_currency': display_currency,
    })


@login_required
def transaction_add(request):
    form = TransactionForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        t = form.save(commit=False)
        t.user = request.user
        t.save()
        messages.success(request, _('Transaction added.'))
        return redirect('finance:transactions')
    return render(request, 'finance/transaction_form.html', {'form': form, 'title': _('Add transaction')})


@login_required
def transaction_edit(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    form = TransactionForm(request.POST or None, instance=tx, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Transaction updated.'))
        return redirect('finance:transactions')
    return render(request, 'finance/transaction_form.html', {'form': form, 'title': _('Edit transaction'), 'obj': tx})


@login_required
def transaction_delete(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        tx.delete()
        messages.success(request, _('Transaction deleted.'))
        return redirect('finance:transactions')
    return render(request, 'finance/confirm_delete.html', {'obj': tx, 'back': 'finance:transactions'})


# ── Accounts ──────────────────────────────────────────────────────────────────

@login_required
def account_list(request):
    import json
    from decimal import Decimal
    user = request.user
    accounts = Account.objects.filter(user=user, is_active=True)
    preferences = get_user_preferences(request)
    preferred_currency = preferences.preferred_currency
    net = services.net_worth(user)
    net_display = services.from_mkd(net, preferred_currency)

    GROUP_DEFS = [
        ('checking',    _('Checking accounts'), ['checking'],             '#0F766E', 'wallet', False),
        ('cash',        _('Cash'),              ['cash'],                  '#64748B', 'banknote', False),
        ('savings',     _('Savings'),           ['savings'],               '#10B981', 'piggy-bank', False),
        ('investments', _('Investments'),       ['investment'],            '#6366F1', 'chart-no-axes-combined', False),
        ('credit',      _('Credit Cards'),      ['credit_card'],           '#F59E0B', 'credit-card', True),
    ]
    total_assets = Decimal('0')
    total_liab   = Decimal('0')
    groups = []
    for key, label, types, color, icon, is_liab in GROUP_DEFS:
        accs = [a for a in accounts if a.type in types]
        total = sum((services.to_mkd(a.current_balance, a.currency) for a in accs), Decimal('0.00'))
        if is_liab:
            total_liab += abs(total)
        else:
            total_assets += total
        groups.append({
            'key': key, 'label': label, 'color': color, 'icon': icon,
            'accounts': accs, 'total': abs(total) if is_liab else total,
            'is_liability': is_liab, 'change_pct': None,
            'pct': 0,
        })
    all_abs = sum(g["total"] for g in groups) or Decimal('1')
    for g in groups:
        g['pct'] = round(float(g['total'] / all_abs * 100), 1)
        g['display_total'] = services.from_mkd(g['total'], preferred_currency)

    # Do not fabricate historical balance charts. Until a balance-history model exists,
    # expose only the current balance rather than inventing a trend.
    sparklines = {str(a.pk): [float(a.current_balance)] for a in accounts}

    return render(request, 'finance/accounts.html', {
        'account_groups': groups,
        'account_count': len(accounts),
        'net_worth': net_display,
        'display_currency': preferred_currency,
        'assets': services.from_mkd(total_assets, preferred_currency),
        'liabilities': services.from_mkd(total_liab, preferred_currency),
        'sparklines': json.dumps(sparklines),
    })


@login_required
def account_add(request):
    form = AccountForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        a = form.save(commit=False)
        a.user = request.user
        a.save()
        messages.success(request, _('Account added.'))
        return redirect('finance:accounts')
    return render(request, 'finance/account_form.html', {'form': form, 'title': _('Add account')})


@login_required
def account_edit(request, pk):
    acc = get_object_or_404(Account, pk=pk, user=request.user)
    form = AccountForm(request.POST or None, instance=acc)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Account updated.'))
        return redirect('finance:accounts')
    return render(request, 'finance/account_form.html', {'form': form, 'title': _('Edit account'), 'obj': acc})


# ── Budgets ───────────────────────────────────────────────────────────────────

@login_required
def budget_list(request):
    from decimal import Decimal
    today = date.today()
    this_month = services.month_start(today)
    preferences = get_user_preferences(request)
    currency = preferences.preferred_currency
    budgets = list(Budget.objects.filter(user=request.user, month=this_month).select_related('category'))
    total_limit = sum(b.amount for b in budgets) or Decimal('0')
    total_spent = sum(b.spent for b in budgets) or Decimal('0')
    gauge_pct = min(int(total_spent / total_limit * 100), 100) if total_limit else 0
    for budget in budgets:
        budget.display_amount = services.from_mkd(budget.amount, currency)
        budget.display_spent = services.from_mkd(budget.spent, currency)
        budget.display_remaining = services.from_mkd(budget.remaining, currency)
    return render(request, 'finance/budgets.html', {
        'budgets': budgets, 'month': this_month,
        'total_limit': services.from_mkd(total_limit, currency),
        'total_spent': services.from_mkd(total_spent, currency),
        'display_currency': currency, 'gauge_pct': gauge_pct,
    })


@login_required
def budget_add(request):
    form = BudgetForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        b = form.save(commit=False)
        b.user = request.user
        b.save()
        messages.success(request, _('Budget created.'))
        return redirect('finance:budgets')
    return render(request, 'finance/budget_form.html', {'form': form, 'title': _('Add budget')})


@login_required
def budget_edit(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    form = BudgetForm(request.POST or None, instance=budget, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Budget updated.'))
        return redirect('finance:budgets')
    return render(request, 'finance/budget_form.html', {'form': form, 'title': _('Edit budget'), 'obj': budget})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        budget.delete()
        messages.success(request, _('Budget deleted.'))
        return redirect('finance:budgets')
    return render(request, 'finance/confirm_delete.html', {'obj': budget, 'back': 'finance:budgets'})


# ── Goals ─────────────────────────────────────────────────────────────────────

@login_required
def goal_list(request):
    preferences = get_user_preferences(request)
    currency = preferences.preferred_currency
    goals = list(Goal.objects.filter(user=request.user))
    total_target_mkd = sum((goal.target_amount for goal in goals), Decimal('0.00'))
    total_target = services.from_mkd(total_target_mkd, currency)
    for goal in goals:
        goal.display_saved_amount = services.from_mkd(goal.saved_amount, currency)
        goal.display_target_amount = services.from_mkd(goal.target_amount, currency)
        goal.display_remaining = services.from_mkd(goal.remaining, currency)
    return render(request, 'finance/goals.html', {
        'goals': goals, 'display_currency': currency, 'total_target': total_target,
    })


@login_required
def goal_add(request):
    form = GoalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        g = form.save(commit=False)
        g.user = request.user
        g.save()
        messages.success(request, _('Goal created.'))
        return redirect('finance:goals')
    return render(request, 'finance/goal_form.html', {'form': form, 'title': _('Add goal')})


@login_required
def goal_edit(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    form = GoalForm(request.POST or None, instance=goal)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, _('Goal updated.'))
        return redirect('finance:goals')
    return render(request, 'finance/goal_form.html', {'form': form, 'title': _('Edit goal'), 'obj': goal})


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == 'POST':
        goal.delete()
        messages.success(request, _('Goal deleted.'))
        return redirect('finance:goals')
    return render(request, 'finance/confirm_delete.html', {'obj': goal, 'back': 'finance:goals'})


@login_required
@require_GET
def market_data(request):
    """Fetch Yahoo chart data server-side so browser CORS does not block it."""
    from urllib.error import HTTPError, URLError
    from urllib.parse import quote
    from urllib.request import Request, urlopen
    import json

    allowed_symbols = {'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'BTC-USD', 'ETH-USD', '^GSPC', '^DJI', '^IXIC', 'ORCL', 'JPM', 'WMT', 'NFLX', 'AMD', 'DIS', 'COST', 'AVGO'}
    allowed_ranges = {'1d', '5d', '1mo', '6mo', '1y'}
    allowed_intervals = {'5m', '15m', '1d', '1wk'}
    symbol = request.GET.get('symbol', 'AAPL')
    range_ = request.GET.get('range', '5d')
    interval = request.GET.get('interval', '1d')
    if symbol not in allowed_symbols or range_ not in allowed_ranges or interval not in allowed_intervals:
        return JsonResponse({'error': 'Invalid market symbol or chart range.'}, status=400)

    cache_key = f'market-data:{symbol}:{interval}:{range_}'
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe="^-")}?interval={interval}&range={range_}'
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 FinTrack/1.0', 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode('utf-8'))
        chart = payload.get('chart', {})
        if chart.get('error') or not chart.get('result'):
            return JsonResponse({'error': 'Market data provider returned no data.'}, status=502)
        cache.set(cache_key, payload, 60)
        return JsonResponse(payload)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return JsonResponse({'error': 'Market data is temporarily unavailable. Please try again later.'}, status=502)


@login_required
def markets(request):
    # Prices are fetched through the same-origin Django endpoint to avoid browser CORS failures.
    watchlist = [
        {'symbol': 'AAPL', 'name': 'Apple', 'domain': 'apple.com'},
        {'symbol': 'MSFT', 'name': 'Microsoft', 'domain': 'microsoft.com'},
        {'symbol': 'NVDA', 'name': 'NVIDIA', 'domain': 'nvidia.com'},
        {'symbol': 'GOOGL', 'name': 'Alphabet', 'domain': 'google.com'},
        {'symbol': 'AMZN', 'name': 'Amazon', 'domain': 'amazon.com'},
        {'symbol': 'META', 'name': 'Meta Platforms', 'domain': 'meta.com'},
        {'symbol': 'TSLA', 'name': 'Tesla', 'domain': 'tesla.com'},
        {'symbol': 'ORCL', 'name': 'Oracle', 'domain': 'oracle.com'},
        {'symbol': 'JPM', 'name': 'JPMorgan Chase', 'domain': 'jpmorganchase.com'},
        {'symbol': 'WMT', 'name': 'Walmart', 'domain': 'walmart.com'},
        {'symbol': 'NFLX', 'name': 'Netflix', 'domain': 'netflix.com'},
        {'symbol': 'AMD', 'name': 'AMD', 'domain': 'amd.com'},
        {'symbol': 'DIS', 'name': 'Disney', 'domain': 'thewaltdisneycompany.com'},
        {'symbol': 'COST', 'name': 'Costco', 'domain': 'costco.com'},
        {'symbol': 'AVGO', 'name': 'Broadcom', 'domain': 'broadcom.com'},
        {'symbol': 'BTC-USD', 'name': 'Bitcoin', 'domain': 'bitcoin.org'},
        {'symbol': 'ETH-USD', 'name': 'Ethereum', 'domain': 'ethereum.org'},
        {'symbol': '^GSPC', 'name': 'S&P 500', 'domain': 'spglobal.com'},
        {'symbol': '^DJI', 'name': 'Dow Jones', 'domain': 'dowjones.com'},
        {'symbol': '^IXIC', 'name': 'NASDAQ Composite', 'domain': 'nasdaq.com'},
    ]
    return render(request, 'finance/markets.html', {'watchlist': watchlist, 'ranges': ['1D','5D','1M','6M','1Y']})


@login_required
def recurring(request):
    from datetime import date
    txs = Transaction.objects.filter(
        user=request.user, is_recurring=True
    ).select_related('category', 'account').order_by('merchant')
    return render(request, 'finance/recurring.html', {
        'recurring': txs,
        'today': date.today(),
        'weekdays': ['M','T','W','T','F','S','S'],
    })


@login_required
def reports(request):
    from django.db.models import Sum, Q
    from datetime import date
    from .services import month_start, add_months, spending_by_category, monthly_trend
    today = date.today()
    this_month = month_start(today)
    preferences = get_user_preferences(request)
    display_currency = preferences.preferred_currency
    by_cat = spending_by_category(request.user, this_month)
    for row in by_cat:
        row['total'] = services.from_mkd(row['total'], display_currency)
    trend = monthly_trend(request.user, 12)
    for row in trend:
        row['income'] = services.from_mkd(row['income'], display_currency)
        row['expense'] = services.from_mkd(row['expense'], display_currency)
    # cumulative net spending per day this month
    from decimal import Decimal
    from .services import to_mkd
    daily = Transaction.objects.filter(
        user=request.user, date__year=today.year, date__month=today.month
    ).select_related('account').order_by('date')
    running = Decimal('0')
    seen_dates = {}
    for tx in daily:
        d = str(tx.date)
        seen_dates.setdefault(d, Decimal('0'))
        converted = to_mkd(tx.amount, tx.account.currency)
        seen_dates[d] += converted if tx.type == 'income' else -converted
    cumulative = []
    for d in sorted(seen_dates):
        running += seen_dates[d]
        cumulative.append({'date': d, 'net': float(services.from_mkd(running, display_currency))})
    return render(request, 'finance/reports.html', {
        'by_cat': by_cat,
        'trend': trend,
        'cumulative': cumulative,
        'month': this_month,
        'display_currency': display_currency,
    })


@login_required
def user_settings(request):
    """Manage persisted profile, display, and notification preferences."""
    preferences = get_user_preferences(request)

    if request.method == 'POST':
        form = UserSettingsForm(
            request.POST, user=request.user, preferences=preferences
        )
        if form.is_valid():
            user = request.user
            user.first_name = form.cleaned_data['first_name'].strip()
            user.last_name = form.cleaned_data['last_name'].strip()
            user.email = form.cleaned_data['email'].strip()
            user.save(update_fields=['first_name', 'last_name', 'email'])

            preferences.preferred_currency = form.cleaned_data['preferred_currency']
            preferences.theme = form.cleaned_data['theme']
            preferences.budget_alerts = form.cleaned_data['budget_alerts']
            preferences.transaction_alerts = form.cleaned_data['transaction_alerts']
            preferences.weekly_summary = form.cleaned_data['weekly_summary']
            preferences.save()

            request.session['preferred_currency'] = preferences.preferred_currency
            request.session['preferred_theme'] = preferences.theme
            messages.success(request, _('Your settings have been saved.'))
            return redirect('finance:settings')
        messages.error(request, _('Please correct the highlighted fields.'))
    else:
        form = UserSettingsForm(user=request.user, preferences=preferences)

    return render(request, 'finance/settings.html', {
        'settings_form': form,
        'preferences': preferences,
        'preferred_currency': preferences.preferred_currency,
        'preferred_theme': preferences.theme,
    })
