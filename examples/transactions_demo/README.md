# Transactions Demo

This example highlights the `transaction:` block that was introduced for the C6 milestone.
It defines `User`, `Order`, and `AuditLog` records plus a few flows that show how a transaction groups multiple record operations:

- `signup_new_customer` creates a user and a welcome order in the same transaction.
- `signup_invalid_order` inserts the user, then tries to create an order that references a missing user ID, which forces a rollback.
- `signup_duplicate_email` demonstrates how an earlier insert is undone when a later step collides with a uniqueness rule.
- Each transaction has an `on error` block that inserts into `AuditLog`, so you can inspect the rollback reason.

Run these flows with the CLI or Studio to compare the committed data (`users`, `orders`) and the audit log entries generated when constraints fail. Use `seed_existing_user` once if you want an existing email to collide with `signup_duplicate_email`.
