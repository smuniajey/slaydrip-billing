# Return & Exchange module

## Tables
- `returns`: one row per returned item (return or exchange). Group transactions by `return_ref`/`exchange_ref`.
- `exchange_details`: one row per new item issued during an exchange, tied to `exchange_ref`.

Run `returns_schema.sql` once on your Neon database before using the feature.

## API endpoints
- `GET /return-exchange` – UI for staff (login required).
- `GET /api/invoice/<invoice_no>` – returns invoice summary plus sold items with available returnable qty.
- `POST /api/returns` – payload: `invoice_no`, `payment_mode` (Cash/UPI/Card), `items` [{design_id, size, quantity}]. Increases stock, logs to `returns`, calculates refund.
- `POST /api/exchanges` – payload: `invoice_no`, `payment_mode`, `return_items` (same shape as returns), `new_items` [{design_id, size, quantity}]. Returned items increase stock + log to `returns` with return_type=EXCHANGE. New items reduce stock and log to `exchange_details`. Settlement: refund/collect/zero based on returned vs new totals.

## Rules enforced
- Invoice must exist; original sales rows are never touched.
- Cannot return more than sold minus previous returns/exchanges.
- Stock never goes negative; exchange new items require available stock.
- Payment modes limited to Cash/UPI/Card for audit clarity.
- All transactions timestamped; reference numbers generated per return/exchange.

## Edge cases covered
- Partial returns and multiple transactions per invoice.
- Exchange after prior returns (uses running returnable quantity).
- Rejects missing stock rows or over-return attempts.
