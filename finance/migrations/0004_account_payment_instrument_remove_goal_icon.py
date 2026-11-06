from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def convert_debit_accounts(apps, schema_editor):
    Account = apps.get_model('finance', 'Account')
    Account.objects.filter(type='debit').update(type='checking', has_debit_card=True)


def reverse_convert_debit_accounts(apps, schema_editor):
    # Reversal is intentionally a no-op: converted checking accounts may now
    # represent genuine bank accounts, so reverting them automatically is unsafe.
    pass


class Migration(migrations.Migration):
    dependencies = [('finance', '0003_userpreference')]

    operations = [
        migrations.AddField(
            model_name='account',
            name='has_debit_card',
            field=models.BooleanField(default=False, help_text='Картичката е платежен инструмент поврзан со оваа сметка и не претставува посебно салдо.', verbose_name='Има поврзана дебитна картичка'),
        ),
        migrations.RunPython(convert_debit_accounts, reverse_convert_debit_accounts),
        migrations.AlterField(
            model_name='account',
            name='type',
            field=models.CharField(choices=[('checking', _('Checking account')), ('savings', _('Savings account')), ('cash', _('Cash')), ('credit_card', _('Credit card')), ('investment', _('Investments'))], default='checking', max_length=20, verbose_name='Тип'),
        ),
        migrations.RemoveField(model_name='goal', name='icon'),
    ]
