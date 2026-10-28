# Wanted Board follow-up work

Items marked ON HOLD remain deferred at the user's request. Do not implement
them until the user asks to resume them. Completed work is recorded below.

## Server-side pagination — IMPLEMENTED

- Replaced See More/See Less with numbered pages of 12 cards (four columns, three rows on desktop) and AJAX navigation.
- Real posts are ordered by newest creation time and UUID, followed by samples.
  Only the database rows needed for the requested page are loaded.
- Search and category remain in page links; changing either starts at page one.

## Status filtering and transaction completion — ON HOLD

- Current board/search continues to include open, fulfilled, and closed posts.
- Future board/search should show only open posts while keeping other posts
  stored and accessible to their owner.
- Mark the linked WantedPost fulfilled only after its transaction completes,
  not merely when an offer is accepted or payment is pending.
- A cancelled transaction before completion must not mark the request fulfilled.
- A closed post means the requester stopped looking without necessarily getting
  the item. Both fulfilled and closed requests should reject new offers.

## Offer modal backend — STILL A PROTOTYPE

- Photo, price, and description are currently frontend-only. Board buttons open
  the shared modal; details show the same form inline. Send is disabled until
  required fields and photo validation pass. Submission retains the draft and
  explicitly says delivery is not connected yet; backend wiring remains deferred.

## Implemented in this iteration

- WantedPost.id is a required, immutable UUID primary key. Existing numeric IDs
  and their two offer relations are migrated to the previously assigned UUIDs.
- Wanted Board and Item Matching URLs now use UUIDs; older numeric detail URLs
  are no longer supported.
- Signed, user-bound creation tokens and database-backed idempotent Create.
- AJAX Create/Edit validation without replacing the form or losing entered details.
- WantedPost no longer has an image field (migration 0015); create, edit, samples,
  and detail pages no longer accept or display reference images. Image-cleanup
  signals were removed. Historical migration validators remain for old upgrades.
- Offer photo input and browser image validation remain in the prototype modal.
- New-post locations default to the city/province of the user's main saved address,
  remain editable, and do not expose the private street address.

## UUID migration notes

- Run the full `python manage.py migrate` command so the intermediate
  Item Matching migration is included before Wanted Board's final table swap.
- Migrations 0013/0014 copy post data into a UUID-keyed table and preserve
  requester, content, image paths, timestamps, and both Offer/ItemOffer relations.
- Pause app writes during this upgrade and back up the database first. These
  data conversion migrations intentionally do not provide a reverse conversion
  to the old integer keys; restore the backup if rollback is required.
- Status filtering and Offer backend wiring remain on hold; pagination is implemented.
