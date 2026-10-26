import itertools

_ids = itertools.count(1)


def promo(**overrides):
    body = {
        "category": "Winter Jackets",
        "base_price": 1200,
        "proposed_discount_pct": 25,
        "is_festival_season": False,
        "forecast_date": "2026-12-10",
    }
    return {**body, **overrides}


def tx(
    store="KANPUR_01",
    category="Mens Casual",
    quantity=2,
    ts="2026-10-26T10:00:00Z",
    tid=None,
):
    return {
        "transaction_id": tid or f"T{next(_ids)}",
        "timestamp": ts,
        "store_id": store,
        "item_category": category,
        "quantity": quantity,
    }


# ---- health ----------------------------------------------------------------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["components"]["database"]["status"] == "connected"
    assert body["components"]["forecast_model"] == "loaded"
    assert body["components"]["anomaly_model"] == "loaded"


# ---- forecast ----------------------------------------------------------------
def test_forecast_shape_and_revenue(client):
    r = client.post("/api/v1/forecast", json=promo())
    assert r.status_code == 200
    b = r.json()
    assert b["predicted_units_sold"] > 0
    assert (
        b["confidence_interval_lower"]
        <= b["predicted_units_sold"]
        <= b["confidence_interval_upper"] + 1
    )
    assert b["projected_revenue"] == round(b["predicted_units_sold"] * 1200 * 0.75, 2)


def test_forecast_is_seasonal_and_discount_sensitive(client):
    winter = client.post(
        "/api/v1/forecast", json=promo(forecast_date="2026-12-10")
    ).json()
    summer = client.post(
        "/api/v1/forecast", json=promo(forecast_date="2026-06-10")
    ).json()
    assert winter["predicted_units_sold"] > summer["predicted_units_sold"] * 3

    low = client.post("/api/v1/forecast", json=promo(proposed_discount_pct=0)).json()
    high = client.post("/api/v1/forecast", json=promo(proposed_discount_pct=50)).json()
    assert high["predicted_units_sold"] > low["predicted_units_sold"]


def test_forecast_unknown_category(client):
    assert (
        client.post("/api/v1/forecast", json=promo(category="Socks")).status_code == 422
    )


def test_forecast_validation(client):
    assert client.post("/api/v1/forecast", json=promo(base_price=0)).status_code == 422
    assert (
        client.post(
            "/api/v1/forecast", json=promo(proposed_discount_pct=101)
        ).status_code
        == 422
    )


# ---- live monitoring -------------------------------------------------------------
def test_normal_transaction(client):
    r = client.post(
        "/api/v1/transactions/monitor", json=tx(store="NORMAL_01", quantity=2)
    )
    assert r.status_code == 200
    assert r.json() == {
        "status": "processed",
        "is_anomaly": False,
        "risk_level": "NORMAL",
        "manager_action_required": False,
    }


def test_panic_buy_single_transaction(client):
    r = client.post(
        "/api/v1/transactions/monitor", json=tx(store="PANIC_01", quantity=60)
    )
    assert r.json()["risk_level"] == "CRITICAL_PANIC_BUY"
    assert r.json()["manager_action_required"] is True


def test_velocity_builds_up_across_transactions(client):
    """Each basket is small, but the burst of sales in 60s at one store is not."""
    levels = []
    for i in range(12):
        ts = f"2026-10-26T11:00:{i:02d}Z"
        r = client.post(
            "/api/v1/transactions/monitor",
            json=tx(store="BURST_01", category="Winter Jackets", quantity=3, ts=ts),
        )
        levels.append(r.json()["risk_level"])
    assert levels[0] == "NORMAL"
    assert levels[-1] == "CRITICAL_PANIC_BUY"

    # Same burst at another store is unaffected.
    other = client.post(
        "/api/v1/transactions/monitor",
        json=tx(
            store="CALM_01",
            category="Winter Jackets",
            quantity=2,
            ts="2026-10-26T11:00:12Z",
        ),
    )
    assert other.json()["risk_level"] == "NORMAL"


def test_duplicate_transaction_is_idempotent(client):
    body = tx(store="DUP_01", quantity=60, tid="DUP-1")
    first = client.post("/api/v1/transactions/monitor", json=body).json()
    second = client.post("/api/v1/transactions/monitor", json=body).json()
    assert first["status"] == "processed"
    assert second["status"] == "duplicate"
    assert second["risk_level"] == first["risk_level"]


def test_monitor_validation(client):
    assert (
        client.post("/api/v1/transactions/monitor", json=tx(quantity=0)).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/transactions/monitor", json=tx(ts="not-a-date")
        ).status_code
        == 422
    )
