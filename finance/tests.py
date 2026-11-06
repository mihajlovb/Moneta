from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Account, Budget, Category, Transaction, UserPreference
from .services import month_summary, net_worth, to_mkd


class CurrencyCalculationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='currency-test', password='test-password-123')
        self.income_category = Category.objects.create(user=self.user, name='Salary', type='income')
        self.expense_category = Category.objects.create(user=self.user, name='Food', type='expense')

    def test_to_mkd_converts_and_rounds(self):
        self.assertEqual(to_mkd(Decimal('10.00'), 'EUR'), Decimal('615.00'))
        self.assertEqual(to_mkd(Decimal('10.00'), 'USD'), Decimal('530.00'))

    def test_unknown_currency_does_not_fall_back_to_one_to_one(self):
        with self.assertRaises(ValueError):
            to_mkd(Decimal('10.00'), 'XYZ')

    def test_month_summary_does_not_add_different_currency_amounts_directly(self):
        mkd = Account.objects.create(user=self.user, name='MKD', currency='MKD', initial_balance=0)
        eur = Account.objects.create(user=self.user, name='EUR', currency='EUR', initial_balance=0)
        Transaction.objects.create(user=self.user, account=mkd, category=self.income_category,
                                   type='income', amount=Decimal('1000'), date=date(2026, 10, 5), merchant='Salary')
        Transaction.objects.create(user=self.user, account=eur, category=self.expense_category,
                                   type='expense', amount=Decimal('10'), date=date(2026, 10, 6), merchant='Lunch')
        result = month_summary(self.user, date(2026, 10, 1))
        self.assertEqual(result['income'], Decimal('1000.00'))
        self.assertEqual(result['expense'], Decimal('615.00'))
        self.assertEqual(result['net'], Decimal('385.00'))

    def test_credit_card_debt_is_subtracted_from_net_worth(self):
        cash = Account.objects.create(user=self.user, name='Cash', currency='MKD', initial_balance=Decimal('10000'))
        card = Account.objects.create(user=self.user, name='Card', currency='EUR', type='credit_card', initial_balance=0)
        Transaction.objects.create(user=self.user, account=card, category=self.expense_category,
                                   type='expense', amount=Decimal('20'), date=date(2026, 10, 6), merchant='Purchase')
        self.assertEqual(card.current_balance, Decimal('20.00'))
        self.assertEqual(net_worth(self.user), Decimal('8770.00'))

    def test_budget_spending_is_converted_to_mkd(self):
        eur = Account.objects.create(user=self.user, name='EUR', currency='EUR', initial_balance=0)
        Transaction.objects.create(user=self.user, account=eur, category=self.expense_category,
                                   type='expense', amount=Decimal('10'), date=date(2026, 10, 6), merchant='Lunch')
        budget = Budget.objects.create(user=self.user, category=self.expense_category,
                                       amount=Decimal('1000'), month=date(2026, 10, 1))
        self.assertEqual(budget.spent, Decimal('615.00'))


class UserSettingsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='settings-test', password='test-password-123', email='old@example.com'
        )
        self.client.login(username='settings-test', password='test-password-123')

    def test_preferences_and_profile_are_saved(self):
        response = self.client.post(reverse('finance:settings'), {
            'first_name': 'Test', 'last_name': 'User', 'email': 'test@example.com',
            'preferred_currency': 'EUR', 'theme': 'dark',
            'budget_alerts': 'on', 'transaction_alerts': '', 'weekly_summary': 'on',
        })
        self.assertRedirects(response, reverse('finance:settings'))
        self.user.refresh_from_db()
        preference = UserPreference.objects.get(user=self.user)
        self.assertEqual(self.user.first_name, 'Test')
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertEqual(preference.preferred_currency, 'EUR')
        self.assertEqual(preference.theme, 'dark')
        self.assertTrue(preference.budget_alerts)
        self.assertFalse(preference.transaction_alerts)
        self.assertTrue(preference.weekly_summary)

    def test_csv_export_is_scoped_to_current_user(self):
        category = Category.objects.create(user=self.user, name='Food', type='expense')
        account = Account.objects.create(user=self.user, name='Cash', currency='MKD')
        Transaction.objects.create(user=self.user, account=account, category=category,
                                   type='expense', amount=Decimal('125.00'),
                                   date=date(2026, 10, 5), merchant='Coffee shop')
        other_user = get_user_model().objects.create_user(
            username='other-settings-test', password='test-password-123'
        )
        other_account = Account.objects.create(user=other_user, name='Other cash', currency='MKD')
        Transaction.objects.create(user=other_user, account=other_account, type='expense',
                                   amount=Decimal('1.00'), date=date(2026, 10, 6), merchant='Private row')
        response = self.client.get(reverse('finance:transactions') + '?export=csv')
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8-sig')
        self.assertIn('Coffee shop', body)
        self.assertNotIn('Private row', body)


class DashboardExperienceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='dashboard-test', password='test-password-123', first_name='Moneta'
        )
        self.client.login(username='dashboard-test', password='test-password-123')

    def test_dashboard_renders_financial_overview_and_empty_states(self):
        response = self.client.get(reverse('finance:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your financial overview')
        self.assertContains(response, 'Net worth')
        self.assertContains(response, 'Your cash flow will appear here')
        self.assertContains(response, 'Bring your accounts together')

    def test_dashboard_only_shows_current_users_accounts(self):
        own = Account.objects.create(user=self.user, name='My account', currency='MKD')
        other_user = get_user_model().objects.create_user(
            username='dashboard-other', password='test-password-123'
        )
        Account.objects.create(user=other_user, name='Private account', currency='MKD')
        response = self.client.get(reverse('finance:dashboard'))
        self.assertContains(response, own.name)
        self.assertNotContains(response, 'Private account')
