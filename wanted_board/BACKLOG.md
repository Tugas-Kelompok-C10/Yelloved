# Wanted Board follow-up work

The following items are on hold at the user's request. Do not implement them
until the user asks to resume them.

## Server-side pagination — ON HOLD

- Current See More/See Less only hides cards in the browser; all matching posts
  and sample cards are still returned by the backend.
- Add bounded server queries and incremental AJAX loading with stable ordering.
- Preserve search/category selection and define how sample posts participate.

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

- Photo, price, and description are currently frontend-only. Submission does not
  persist an offer, despite its success toast. Backend wiring remains deferred.

## Implemented in this iteration

- WantedPost.id is a required, immutable UUID primary key. Existing numeric IDs
  and their two offer relations are migrated to the previously assigned UUIDs.
- Wanted Board and Item Matching URLs now use UUIDs; older numeric detail URLs
  are no longer supported.
- Signed, user-bound creation tokens and database-backed idempotent Create.
- AJAX Create/Edit validation without replacing the form or losing selected files.
- Removal of replaced/deleted reference images after database commit, provided
  no other WantedPost references the same file.
- File cleanup covers future model save/delete operations; it does not scan or
  delete pre-existing orphan files. Direct SQL and QuerySet image updates bypass
  model signals and should not be used for replacing reference images.

## UUID migration notes

- Run the full `python manage.py migrate` command so the intermediate
  Item Matching migration is included before Wanted Board's final table swap.
- Migrations 0013/0014 copy post data into a UUID-keyed table and preserve
  requester, content, image paths, timestamps, and both Offer/ItemOffer relations.
- Pause app writes during this upgrade and back up the database first. These
  data conversion migrations intentionally do not provide a reverse conversion
  to the old integer keys; restore the backup if rollback is required.
- Pagination, status filtering, and Offer backend wiring remain on hold.
