from fashion_personalization.models import EventType, Product, SearchQuery
from fashion_personalization.service import PersonalizationService, build_demo_service


def test_personal_ranking_prioritizes_user_preferences() -> None:
    service = build_demo_service()

    recommendations = service.recommend_now("u-100", limit=3)

    assert recommendations
    assert recommendations[0].product_id in {"sku-denim-001", "sku-knit-002"}
    assert any("brand:Danble Studio" in item.reasons for item in recommendations)


def test_search_filters_catalog_for_user_api_surface() -> None:
    service = build_demo_service()

    products = service.search(SearchQuery(keyword="daily", max_price=90000, size="M"))

    assert [product.product_id for product in products] == ["sku-knit-002", "sku-denim-001"]


def test_dislike_removes_product_from_recommendations() -> None:
    service = build_demo_service()
    service.record_event(
        user_id="u-100",
        product_id="sku-denim-001",
        event_type=EventType.DISLIKE,
        idempotency_key="dislike-denim",
    )

    recommendations = service.recommend_now("u-100", limit=5)

    assert "sku-denim-001" not in [item.product_id for item in recommendations]


def test_size_preference_contributes_to_ranking() -> None:
    service = PersonalizationService()
    service.load_catalog(
        [
            Product(
                product_id="p-small",
                name="Small Fit Tee",
                brand="FitLab",
                category="tee",
                price=50000,
                tags=("daily",),
                sizes=("S",),
                stock=10,
                margin_rate=0.4,
            ),
            Product(
                product_id="p-medium",
                name="Medium Fit Tee",
                brand="FitLab",
                category="tee",
                price=50000,
                tags=("daily",),
                sizes=("M",),
                stock=10,
                margin_rate=0.4,
            ),
        ]
    )
    service.record_event(
        user_id="u-size",
        product_id="p-medium",
        event_type=EventType.ADD_TO_CART,
        idempotency_key="size-pref-1",
        payload={"size": "M"},
    )

    recommendations = service.recommend_now("u-size", limit=2)

    assert recommendations[0].product_id == "p-medium"
    assert "sizes:M" in recommendations[0].reasons


def test_target_price_is_weighted_and_order_independent() -> None:
    products = [
        Product(
            product_id="cheap",
            name="Cheap Tee",
            brand="Budget",
            category="tee",
            price=10000,
            tags=("daily",),
            sizes=("M",),
            stock=10,
            margin_rate=0.4,
        ),
        Product(
            product_id="premium",
            name="Premium Jacket",
            brand="Premium",
            category="outer",
            price=200000,
            tags=("outer",),
            sizes=("M",),
            stock=10,
            margin_rate=0.4,
        ),
    ]
    first = PersonalizationService()
    second = PersonalizationService()
    first.load_catalog(products)
    second.load_catalog(products)

    first.record_event(user_id="u-price", product_id="cheap", event_type=EventType.VIEW, idempotency_key="p1")
    first.record_event(user_id="u-price", product_id="premium", event_type=EventType.PURCHASE, idempotency_key="p2")
    second.record_event(user_id="u-price", product_id="premium", event_type=EventType.PURCHASE, idempotency_key="p3")
    second.record_event(user_id="u-price", product_id="cheap", event_type=EventType.VIEW, idempotency_key="p4")

    first_price = first.store.get_profile("u-price").target_price
    second_price = second.store.get_profile("u-price").target_price

    assert round(first_price, 6) == round(second_price, 6)
    assert first_price > 100000


def test_stock_availability_and_low_stock_are_reflected() -> None:
    service = build_demo_service()

    recommendations = service.recommend_now("u-100", limit=10)
    product_ids = [item.product_id for item in recommendations]
    low_stock = next(item for item in recommendations if item.product_id == "sku-jacket-003")

    assert "sku-shoes-006" not in product_ids
    assert "low-stock" in low_stock.reasons
