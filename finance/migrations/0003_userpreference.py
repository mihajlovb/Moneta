from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('finance', '0002_alter_account_currency_alter_account_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('preferred_currency', models.CharField(choices=[('MKD', 'MKD — Macedonian Denar'), ('EUR', 'EUR — Euro'), ('USD', 'USD — US Dollar'), ('GBP', 'GBP — British Pound'), ('CHF', 'CHF — Swiss Franc')], default='MKD', max_length=3)),
                ('theme', models.CharField(choices=[('light', 'Light'), ('dark', 'Dark')], default='light', max_length=8)),
                ('budget_alerts', models.BooleanField(default=True)),
                ('transaction_alerts', models.BooleanField(default=True)),
                ('weekly_summary', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Корисничка поставка', 'verbose_name_plural': 'Кориснички поставки'},
        ),
    ]
