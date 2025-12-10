# Data & Collections Demo

This example showcases the modern data model:

- Collection pipelines over lists (filter, group, sort, take).
- Aggregates (`sum/mean/minimum/maximum/count`) inside `group by`.
- Record destructuring and safe access (`get ... otherwise ...`).
- List helpers (`append`, `remove`, `insert`) that return new lists.

How it works:

- `summarize_sales` filters paid BE sales, groups by `customer_id`, and logs top customers.
- Safe record lookups demonstrate defaults for missing fields.
- List helpers show pure list transformations.

Run it:
```
n3 example run data_collections_demo
```
or open in Studio:
```
http://localhost:8000/studio?example=data_collections_demo
```

See the walkthrough in `docs/book/data_and_collections.md` and the cheat sheet in `docs/language/data_collections.md`.
