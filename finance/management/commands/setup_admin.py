"""Create an administrator or reset a known admin account password safely.

Usage: python manage.py setup_admin
The command prompts for username and password and does not hard-code credentials.
"""
from getpass import getpass
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create or repair a Django superuser account.'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Admin username (prompted if omitted)')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options.get('username') or input('Admin username: ').strip()
        if not username:
            raise CommandError('Username cannot be empty.')
        user, created = User.objects.get_or_create(username=username)
        password = getpass('New admin password (input hidden): ')
        confirm = getpass('Confirm password: ')
        if not password or password != confirm:
            if created:
                user.delete()
            raise CommandError('Passwords are empty or do not match. No password was changed.')
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f'Administrator {username!r} is ready. Sign in at /admin/.'
        ))
