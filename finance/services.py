"""Currency-safe financial calculations. All cross-account totals are normalized to MKD."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models.functions import TruncMonth

from .models import Account, Transaction

# Indicative fixed rates for this academic demo, expressed as MKD for 1 unit.
# These are deliberately centralized; update them from a trusted FX source before
# using real financial data. They are not live market rates.
FX_TO_MKD = {
    'MKD': Decimal('1.0000'),
    'EUR': Decimal('61.5000'),
    'USD': Decimal('53.0000'),
    'GBP': Decimal('71.0000'),
    'CHF': Decimal('65.5000'),
}
MONEY = Decimal('0.01')


def to_mkd(amount, currency):
    """Convert an amount to the app's reporting currency (MKD).

    Unknown currencies raise an error instead of silently using a 1:1 rate.
    """
    try:
        rate = FX_TO_MKD[currency]
    except KeyError as exc:
        raise ValueError(f'Unsupported currency: {currency}') from exc
    return (Decimal(amount) * rate).quantize(MONEY, rounding=ROUND_HALF_UP)



def from_mkd(amount, currency):
    """Convert an MKD reporting amount into the selected display currency."""
    try:
        rate = FX_TO_MKD[currency]
    except KeyError as exc:
        raise ValueError(f'Unsupported currency: {currency}') from exc
    return (Decimal(amount) / rate).quantize(MONEY, rounding=ROUND_HALF_UP)


def month_start(d: date) -> date:
    return d.replace(day=1)


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _transactions(user, start=None, end=None):
    qs = Transaction.objects.filter(user=user).select_related('account', 'category')
    if start is not None:
        qs = qs.filter(date__gte=start)
    if end is not None:
        qs = qs.filter(date__lt=end)
    return qs


def net_worth(user):
    """Assets minus credit-card liabilities, all converted to MKD."""
    total = Decimal('0.00')
    accounts = Account.objects.filter(user=user, is_active=True, include_in_net_worth=True)
    for acc in accounts:
        balance = to_mkd(acc.current_balance, acc.currency)
        total += -balance if acc.is_liability else balance
    return total.quantize(MONEY, rounding=ROUND_HALF_UP)


def month_summary(user, month: date):
    start = month_start(month)
    end = add_months(start, 1)
    income = Decimal('0.00')
    expense = Decimal('0.00')
    for tx in _transactions(user, start, end):
        converted = to_mkd(tx.amount, tx.account.currency)
        if tx.type == Transaction.Type.INCOME:
            income += converted
        else:
            expense += converted
    income = income.quantize(MONEY, rounding=ROUND_HALF_UP)
    expense = expense.quantize(MONEY, rounding=ROUND_HALF_UP)
    net = income - expense
    return {
        'income': income,
        'expense': expense,
        'net': net,
        'savings_rate': int((net / income) * 100) if income else 0,
        'currency': 'MKD',
    }


def spending_by_category(user, month: date):
    start = month_start(month)
    end = add_months(start, 1)
    totals = {}
    for tx in _transactions(user, start, end).filter(type=Transaction.Type.EXPENSE):
        key = (tx.category_id, tx.category.name if tx.category else 'Other',
               tx.category.color if tx.category else '#94A3B8',
               tx.category.icon if tx.category else '🏷️')
        totals[key] = totals.get(key, Decimal('0.00')) + to_mkd(tx.amount, tx.account.currency)
    rows = [
        {'category__name': key[1], 'category__color': key[2], 'category__icon': key[3],
         'total': value.quantize(MONEY, rounding=ROUND_HALF_UP)}
        for key, value in totals.items()
    ]
    return sorted(rows, key=lambda row: row['total'], reverse=True)


def monthly_trend(user, months: int = 6):
    """Monthly income/expense trend converted to MKD, without mixing currencies."""
    start = add_months(month_start(date.today()), -(months - 1))
    data = {add_months(start, i): {'income': Decimal('0.00'), 'expense': Decimal('0.00')}
            for i in range(months)}
    for tx in _transactions(user, start):
        key = month_start(tx.date)
        if key not in data:
            continue
        data[key][tx.type] += to_mkd(tx.amount, tx.account.currency)
    return [
        {'month': key,
         'income': values['income'].quantize(MONEY, rounding=ROUND_HALF_UP),
         'expense': values['expense'].quantize(MONEY, rounding=ROUND_HALF_UP)}
        for key, values in sorted(data.items())
    ]
