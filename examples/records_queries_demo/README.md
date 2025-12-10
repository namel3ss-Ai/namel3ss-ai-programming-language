# Records & Queries Demo

This example shows the English query surface for records:

- Record definitions over a frame with defaults and required fields.
- `find <alias> where:` filtering with English operators.
- Ordering and pagination with `order ... by`, `limit ... to`, and `offset ... by`.

Flows:
- `seed_sample_data` inserts four users.
- `list_active_users` filters active users, sorts by `created_at` then `name`, and limits to the first page.
- `be_or_nl_users` filters with `is one of`, orders by `created_at`, and paginates with `offset`.

Run it:
```
n3 example run records_queries_demo
```
or open in Studio:
```
http://localhost:8000/studio?example=records_queries_demo
```

See the Records & Queries chapter in `docs/book/records_and_queries.md` for a full walkthrough.
