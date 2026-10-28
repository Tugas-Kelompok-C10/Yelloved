"""Dedicated, non-login seller identity for imported community listings."""
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

DEMO_USERNAME = 'yelloved_community'


def get_demo_seller():
    User = get_user_model()
    seller = User.objects.filter(username=DEMO_USERNAME).first()
    if seller is not None:
        if (seller.has_usable_password() or seller.is_staff or seller.is_superuser
                or seller.get_full_name() != 'Yelloved Community'):
            raise CommandError('Username demo sudah dipakai akun lain; akun dan item pengguna tidak diubah.')
        return seller
    return User.objects.create_user(username=DEMO_USERNAME, password=None,
                                   first_name='Yelloved', last_name='Community')
