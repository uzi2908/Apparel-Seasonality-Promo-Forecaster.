Start the server from `project/`:

```bash
uv run uvicorn app.main:app --reload
```

Interactive docs are at http://127.0.0.1:8000/docs. The curl examples below also work.

## Health

```bash
curl http://127.0.0.1:8000/health
```

## Forecast

Winter Jackets in December, 25% off (expect about 130 units):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/forecast \
  -H "Content-Type: application/json" \
  -d '{"category":"Winter Jackets","base_price":1200,"proposed_discount_pct":25,"is_festival_season":false,"forecast_date":"2026-12-10"}'
```

The same product in June should give only about 5 units:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/forecast \
  -H "Content-Type: application/json" \
  -d '{"category":"Winter Jackets","base_price":1200,"proposed_discount_pct":25,"is_festival_season":false,"forecast_date":"2026-06-10"}'
```

Festival effect. Run it with `true`, then `false`; I got about 118 versus about 73:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/forecast \
  -H "Content-Type: application/json" \
  -d '{"category":"Womens Ethnic","base_price":1200,"proposed_discount_pct":25,"is_festival_season":true,"forecast_date":"2026-11-01"}'
```

Error cases (both return 422):

```bash
# unknown category
curl -X POST http://127.0.0.1:8000/api/v1/forecast -H "Content-Type: application/json" \
  -d '{"category":"Socks","base_price":500,"proposed_discount_pct":10,"is_festival_season":false}'
# discount over 100
curl -X POST http://127.0.0.1:8000/api/v1/forecast -H "Content-Type: application/json" \
  -d '{"category":"Kidswear","base_price":500,"proposed_discount_pct":150,"is_festival_season":false}'
```

## Live monitoring

Use a fresh `transaction_id` each time. Re-sending the same one returns `"status":"duplicate"`.

Normal sale (`NORMAL`):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transactions/monitor \
  -H "Content-Type: application/json" \
  -d '{"transaction_id":"T1001","timestamp":"2026-10-26T10:00:00Z","store_id":"KANPUR_01","item_category":"Mens Casual","quantity":2}'
```

Panic buy, a single huge basket (`CRITICAL_PANIC_BUY`, `manager_action_required: true`):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transactions/monitor \
  -H "Content-Type: application/json" \
  -d '{"transaction_id":"T1002","timestamp":"2026-10-26T10:00:05Z","store_id":"KANPUR_01","item_category":"Kidswear","quantity":60}'
```

Velocity burst. Each basket is only 3 jackets, but the volume at one store builds up. The first calls return `NORMAL` and it turns critical around the 9th–12th:

```bash
for i in 01 02 03 04 05 06 07 08 09 10 11 12; do
  curl -s -X POST http://127.0.0.1:8000/api/v1/transactions/monitor \
    -H "Content-Type: application/json" \
    -d "{\"transaction_id\":\"BURST-$i\",\"timestamp\":\"2026-10-26T11:00:$i\"Z,\"store_id\":\"LKO_02\",\"item_category\":\"Winter Jackets\",\"quantity\":3}"
  echo
done
```

The `timestamp` inside `-d` above is mangled by my shell quoting. Use this version instead, which builds the JSON correctly:

```bash
for i in $(seq -w 1 12); do
  curl -s -X POST http://127.0.0.1:8000/api/v1/transactions/monitor \
    -H "Content-Type: application/json" \
    -d '{"transaction_id":"BURST-'$i'","timestamp":"2026-10-26T11:00:'$i'Z","store_id":"LKO_02","item_category":"Winter Jackets","quantity":3}'
  echo
done
```

Check what was stored:

```bash
sqlite3 ../retail_sales.db "select transaction_id, store_id, quantity, velocity_units, risk_level from live_transactions order by id desc limit 15;"
```

Live transactions are written to `retail_sales.db`. To clear your test rows, run `sqlite3 ../retail_sales.db "delete from live_transactions;"`.

To run the automated checks, use `.venv/bin/python -m pytest -q`. They use a temporary DB copy, so they leave your real data alone.