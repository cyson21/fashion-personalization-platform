from typing import Any

from fashion_personalization.models import EventType, SearchQuery
from fashion_personalization.service import build_demo_service
from fashion_personalization.store import IdempotencyConflict


def create_app() -> Any:
    try:
        from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query
        from pydantic import BaseModel, ConfigDict, Field
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("FastAPI adapter requires `pip install -e .[api]`.") from exc

    service = build_demo_service()
    app = FastAPI(title="Fashion Personalization Platform", version="0.1.0")

    class EventRequest(BaseModel):
        model_config = ConfigDict(extra="forbid")

        user_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
        product_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
        event_type: EventType
        idempotency_key: str = Field(min_length=8, max_length=120)
        size: str | None = Field(default=None, max_length=16)

    def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
        if x_admin_token != "demo-admin":
            raise HTTPException(status_code=403, detail="admin token required")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/products")
    def products(
        keyword: str | None = Query(default=None, max_length=80),
        category: str | None = Query(default=None, max_length=40),
        size: str | None = Query(default=None, max_length=16),
        max_price: int | None = Query(default=None, ge=0),
        in_stock_only: bool = True,
    ) -> list[dict[str, Any]]:
        results = service.search(
            SearchQuery(
                keyword=keyword,
                category=category,
                size=size,
                max_price=max_price,
                in_stock_only=in_stock_only,
            )
        )
        return [
            {
                "product_id": product.product_id,
                "name": product.name,
                "brand": product.brand,
                "category": product.category,
                "price": product.price,
                "tags": product.tags,
                "sizes": product.sizes,
                "stock": product.stock,
                "updated_at": product.updated_at,
            }
            for product in results
        ]

    @app.post("/events")
    def record_event(payload: EventRequest = Body()) -> dict[str, Any]:
        if service.store.get_product(payload.product_id) is None:
            raise HTTPException(status_code=404, detail="unknown product")
        try:
            event = service.record_event(
                user_id=payload.user_id,
                product_id=payload.product_id,
                event_type=payload.event_type,
                idempotency_key=payload.idempotency_key,
                payload={"size": payload.size} if payload.size else None,
                process_now=False,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"event_id": event.event_id, "status": event.status.value, "attempts": event.attempts}

    @app.get("/users/{user_id}/recommendations")
    def recommendations(
        user_id: str,
        limit: int = Query(default=5, ge=1, le=20),
    ) -> list[dict[str, Any]]:
        return [
            {
                "product_id": recommendation.product_id,
                "score": recommendation.score,
                "reasons": [
                    reason
                    for reason in recommendation.reasons
                    if reason not in {"healthy-margin", "low-stock"}
                ],
            }
            for recommendation in service.recommend_now(user_id, limit=limit, create_profile=False)
        ]

    @app.post("/admin/batches/{batch_id}")
    def run_batch(batch_id: str, _: None = Depends(require_admin)) -> dict[str, Any]:
        return service.run_batch(batch_id).__dict__

    @app.get("/admin/report")
    def admin_report(_: None = Depends(require_admin)) -> dict[str, Any]:
        return service.admin_report().__dict__

    return app
