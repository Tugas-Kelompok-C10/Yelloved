"""Import Wanted Board examples explicitly, never from an HTTP page request."""
from uuid import NAMESPACE_URL, uuid5

import requests
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from wanted_board.models import WantedPost
from wanted_board.sample_data import DUMMYJSON_PRODUCTS_URL, _fetch_posts


class Command(BaseCommand):
    help = 'Import 30 DummyJSON examples as stored Wanted Board posts.'

    def handle(self, *args, **options):
        try:
            posts = _fetch_posts()
        except (requests.RequestException, ValueError, ArithmeticError, TypeError) as exc:
            raise CommandError(f'DummyJSON import failed; existing posts were not changed: {exc}') from exc
        with transaction.atomic():
            User = get_user_model()
            username = 'yelloved_wanted_demo'
            owner = User.objects.filter(username=username).first()
            if owner and (owner.has_usable_password() or owner.is_staff or owner.is_superuser
                          or owner.get_full_name() != 'Yelloved Community'):
                raise CommandError('Demo username belongs to another account; database unchanged.')
            if owner is None:
                owner = User.objects.create_user(username=username, password=None,
                                                first_name='Yelloved', last_name='Community')
            created = 0
            for post in posts:
                identifier = uuid5(NAMESPACE_URL, f'{DUMMYJSON_PRODUCTS_URL}#product-{post["source_id"]}')
                existing = WantedPost.objects.filter(pk=identifier).first()
                if existing and existing.requester_id != owner.pk:
                    raise CommandError('Imported post ID conflicts with a user post; database unchanged.')
                defaults = dict(requester=owner, title=post['title'][:50],
                                description=post['description'][:500], category=post['category'],
                                budget=post['budget'], location=post['location'])
                try:
                    WantedPost(id=identifier, **defaults).full_clean(validate_unique=False)
                except ValidationError as exc:
                    raise CommandError(f'Invalid imported post; database unchanged: {exc}') from exc
                # Stable IDs prevent duplicates; keep existing edits/status on repeat imports.
                _, new = WantedPost.objects.get_or_create(pk=identifier, defaults=defaults)
                created += int(new)
        self.stdout.write(self.style.SUCCESS(f'Imported {created} new posts; {len(posts) - created} already existed.'))
