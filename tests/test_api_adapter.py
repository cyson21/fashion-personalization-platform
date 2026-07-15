import importlib.util
from typing import Any

import pytest

if importlib.util.find_spec("fastapi") is None or importlib.util.find_spec("httpx") is None:
    _HAS_TESTCLIENT = False
    _TESTCLIENT_SKIP_REASON = "FastAPI API test dependencies are not installed"
else:
    from fastapi.testclient import TestClient

    _HAS_TESTCLIENT = True
    _TESTCLIENT_SKIP_REASON = None


@pytest.fixture
def api_client() -> Any:
    if not _HAS_TESTCLIENT:
        pytest.skip(_TESTCLIENT_SKIP_REASON)

    from fashion_personalization.api import create_app

    with TestClient(create_app()) as client:
        yield client


def test_fastapi_adapter_is_import_safe_without_dependency() -> None:
    import fashion_personalization.api as api

    assert callable(api.create_app)


@pytest.mark.skipif(importlib.util.find_spec("fastapi") is None, reason="FastAPI optional dependency is not installed")
def test_fastapi_adapter_registers_expected_routes() -> None:
    from fashion_personalization.api import create_app

    app = create_app()
    route_paths = {route.path for route in app.routes}

    assert "/products" in route_paths
    assert "/events" in route_paths
    assert "/admin/report" in route_paths


def test_get_products_returns_seeded_data_and_filtering(api_client: Any) -> None:
    all_products_response = api_client.get("/products")
    assert all_products_response.status_code == 200
    all_products = all_products_response.json()

    assert len(all_products) == 5
    assert all(product["stock"] > 0 for product in all_products)
    assert "sku-shoes-006" not in {product["product_id"] for product in all_products}

    denim_response = api_client.get("/products", params={"category": "denim"})
    assert denim_response.status_code == 200
    denim_products = denim_response.json()

    assert len(denim_products) == 1
    assert denim_products[0]["product_id"] == "sku-denim-001"


def test_post_events_success(api_client: Any) -> None:
    payload = {
        "user_id": "u-api-success",
        "product_id": "sku-denim-001",
        "event_type": "view",
        "idempotency_key": "post-evt-success-001",
        "size": "M",
    }
    response = api_client.post("/events", json=payload)

    assert response.status_code == 200
    body = response.json()

    assert isinstance(body.get("event_id"), str)
    assert body["event_id"].startswith("evt-")
    assert body["status"] == "pending"
    assert body["attempts"] == 0


def test_post_events_validation_error(api_client: Any) -> None:
    payload = {
        "user_id": "u-api-validation",
        "product_id": "sku-denim-001",
        "idempotency_key": "post-evt-validation-bad",
        "size": "M",
    }
    response = api_client.post("/events", json=payload)

    assert response.status_code == 422


def test_post_events_unknown_product_returns_404(api_client: Any) -> None:
    payload = {
        "user_id": "u-api-unknown",
        "product_id": "sku-missing-000",
        "event_type": "view",
        "idempotency_key": "post-evt-unknown-001",
        "size": "M",
    }
    response = api_client.post("/events", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "unknown product"


def test_post_events_idempotency_conflict_returns_409(api_client: Any) -> None:
    first_payload = {
        "user_id": "u-api-conflict",
        "product_id": "sku-denim-001",
        "event_type": "view",
        "idempotency_key": "post-evt-conflict-001",
        "size": "M",
    }
    second_payload = {
        "user_id": "u-api-conflict",
        "product_id": "sku-denim-001",
        "event_type": "purchase",
        "idempotency_key": "post-evt-conflict-001",
        "size": "M",
    }

    assert api_client.post("/events", json=first_payload).status_code == 200

    conflict_response = api_client.post("/events", json=second_payload)
    assert conflict_response.status_code == 409
    assert "idempotency_key is already used for a different event fingerprint" in conflict_response.json()["detail"]


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Admin-Token": "not-demo-admin"}],
)
def test_admin_report_requires_valid_token(api_client: Any, headers: dict[str, str]) -> None:
    response = api_client.get("/admin/report", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "admin token required"


def test_admin_report_returns_snapshot(api_client: Any) -> None:
    response = api_client.get("/admin/report", headers={"X-Admin-Token": "demo-admin"})

    assert response.status_code == 200
    report = response.json()

    assert report["products"] == 6
    assert report["users"] == 2
    assert report["latest_batch_id"] == "demo-batch-001"
    assert report["processed_events"] >= 1
    assert isinstance(report["pending_events"], int)
