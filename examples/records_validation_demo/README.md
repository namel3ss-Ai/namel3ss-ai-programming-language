# Records Validation Demo

This example highlights the C7 field-validation work:

- `Product` record defines numeric bounds, enum membership, a slug pattern, array length, and JSON metadata.
- `seed_valid_product` inserts a row that satisfies every rule.
- `create_bad_price` fails because `price` violates `must be at least 0`.
- `bulk_seed_products` shows that `create many ...` rolls back when any item fails validation.
- `transaction_invalid_slug` demonstrates that a `transaction:` block rolls back when a later step violates the slug pattern.

Run the flows with `n3 example run records_validation_demo --flow <flow_name>` or load the source in Studio to experiment with different values.
