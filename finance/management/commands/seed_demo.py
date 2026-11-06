"""Креира demo корисник со реални податоци за тестирање на UI.

Употреба:  python manage.py seed_demo
Логин:     demo / demo1234
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from finance.models import Account, Budget, Category, Goal, Transaction
from finance.services import month_start

User = get_user_model()

EXPENSES = {
    'Храна и пазарење': (['Рамстор', 'Тинекс', 'Веро', 'Пекара'], 300, 2500),
    'Ресторани и кафе': (['Кафе Скопје', 'Пицерија', 'Бургер', 'Starbucks'], 150, 1200),
    'Транспорт': (['Бензин', 'Автобус', 'Такси'], 100, 2000),
    'Сметки и режии': (['ЕВН', 'Водовод', 'Македонски Телеком'], 500, 3500),
    'Забава': (['Кино', 'Концерт', 'Игри'], 200, 1500),
    'Здравје': (['Аптека', 'Лекар'], 150, 2000),
    'Претплати': (['Netflix', 'Spotify'], 300, 600),
}


class Command(BaseCommand):
    help = 'Креира demo податоци'

    def handle(self, *args, **opts):
        random.seed(42)
        user, created = User.objects.get_or_create(username='demo', defaults={'first_name': 'Демо'})
        user.set_password('demo1234')
        user.save()
        if not created:
            Transaction.objects.filter(user=user).delete()
            Account.objects.filter(user=user).delete()
            Budget.objects.filter(user=user).delete()
            Goal.objects.filter(user=user).delete()

        cats = {c.name: c for c in Category.objects.filter(user=user)}

        main = Account.objects.create(user=user, name='Стопанска банка', type='checking',
                                      initial_balance=Decimal('25000'), color='#6366F1')
        savings = Account.objects.create(user=user, name='Штедна книшка', type='savings',
                                         initial_balance=Decimal('80000'), color='#10B981')
        cash = Account.objects.create(user=user, name='Кеш', type='cash',
                                      initial_balance=Decimal('8000'), color='#F59E0B')
        card = Account.objects.create(user=user, name='Visa картичка', type='credit_card',
                                      initial_balance=Decimal('0'), color='#EF4444')

        today = date.today()
        txs = []
        # Keep demo balances realistic: cash never goes negative and the card stays under its limit.
        cash_left = Decimal('8000')
        card_room = Decimal('15000')
        for months_back in range(6):
            m = month_start(today)
            for _ in range(months_back):
                m = month_start(m - timedelta(days=1))
            # плата на 5-ти
            txs.append(Transaction(user=user, account=main, category=cats['Плата'], type='income',
                                   amount=Decimal('48000'), date=m.replace(day=5), merchant='Плата'))
            if random.random() > 0.5:
                txs.append(Transaction(user=user, account=main, category=cats['Фриленс'], type='income',
                                       amount=Decimal(random.randint(3000, 9000)),
                                       date=m.replace(day=random.randint(10, 25)), merchant='Фриленс проект'))
            txs.append(Transaction(user=user, account=main, category=cats['Станарина'], type='expense',
                                   amount=Decimal('12000'), date=m.replace(day=1), merchant='Станарина',
                                   is_recurring=True))
            for cat_name, (merchants, lo, hi) in EXPENSES.items():
                for _ in range(random.randint(2, 6)):
                    day = random.randint(1, 28)
                    d = m.replace(day=day)
                    if d > today:
                        continue
                    amount = Decimal(random.randint(lo, hi))
                    account = random.choice([main, main, cash, card])
                    if account is cash and (amount > 1000 or amount > cash_left):
                        account = main
                    if account is card and amount > card_room:
                        account = main
                    if account is cash:
                        cash_left -= amount
                    elif account is card:
                        card_room -= amount
                    txs.append(Transaction(
                        user=user,
                        account=account,
                        category=cats[cat_name],
                        type='expense',
                        amount=amount,
                        date=d,
                        merchant=random.choice(merchants),
                    ))
        Transaction.objects.bulk_create([t for t in txs if t.date <= today])

        this_month = month_start(today)
        for cat_name, limit in [('Храна и пазарење', 9000), ('Ресторани и кафе', 4000),
                                ('Транспорт', 4000), ('Забава', 3000)]:
            Budget.objects.create(user=user, category=cats[cat_name], amount=Decimal(limit), month=this_month)

        Goal.objects.create(user=user, name='Одмор на море', target_amount=Decimal('60000'),
                            saved_amount=Decimal('22000'), deadline=today + timedelta(days=150))
        Goal.objects.create(user=user, name='Нов лаптоп', target_amount=Decimal('90000'),
                            saved_amount=Decimal('35000'), deadline=today + timedelta(days=300))

        self.stdout.write(self.style.SUCCESS(f'Готово. Креирани {Transaction.objects.filter(user=user).count()} трансакции. Логин: demo / demo1234'))
