from contextlib import contextmanager

from django.db import transaction
from django.db.models import F
from django.http import Http404

from .models import WantedPost


@contextmanager
def locked_wanted_post(pk, requester=None):
    """Read current status only after acquiring the post's database write lock."""
    with transaction.atomic():
        posts = WantedPost.objects.filter(pk=pk)
        if requester is not None:
            posts = posts.filter(requester=requester)
        # This deliberately writes the same value. PostgreSQL locks this row;
        # SQLite obtains its write lock too (SELECT FOR UPDATE is a no-op there).
        # Keep updated_at untouched so merely submitting an offer is not an edit.
        if not posts.update(status=F("status")):
            raise Http404("Wanted post not found")
        yield posts.get()
