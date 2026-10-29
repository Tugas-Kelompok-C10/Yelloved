# Wanted sample data

Only dummy posts use this integration. User-created wanted posts remain in the
database; API products are not inserted into the database.

`get_sample_wanted_posts()` is used by the board, sample detail, search and
landing preview. It fetches `https://dummyjson.com/products?limit=30` on the
server and validates all 30 products before accepting the response.

- Fresh results: cached for 10 minutes.
- Last successful results: kept for 24 hours as an outage fallback.
- No successful cached response: use `dummyjson_products.json` from the repo.
- API timeout, HTTP error or invalid data: cache the fallback for 1 minute,
  then allow a new API attempt. Never overwrite the last-good cache with bad data.
- Requests use a 2-second connection timeout and 3-second read timeout.

The `wanted_samples` Django cache uses `.cache/wanted-samples/`, shared by
workers using the same filesystem. This directory must be writable by Django.
It is disposable, ignored by Git and separate from uploaded media. Multiple
servers with separate filesystems each have their own cache. Cache disk failures
are logged and do not stop the sample-data fallback.

No network request occurs during module import. The exported
`SAMPLE_WANTED_POSTS` constant is the stable local fixture for existing tests;
application views call the getter so results can refresh.

Run the isolated tests (all API requests are mocked):

```powershell
python manage.py test wanted_board.test_sample_api
```

Configuration lives in `home/settings.py`; cache durations and request timeouts
live in `wanted_board/sample_data.py`. No migration is required. Restart Django
after deploying this change so it loads the cache configuration.
