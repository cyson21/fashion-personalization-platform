import importlib.util

import pytest


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
