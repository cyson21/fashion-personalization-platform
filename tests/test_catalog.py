import json

from fashion_personalization.catalog import load_products_from_json, search_products
from fashion_personalization.models import SearchQuery


def test_load_products_from_json_converts_numeric_and_iterable_fields() -> None:
    raw_text = json.dumps(
        [
            {
                "product_id": "sku-100",
                "name": "light jacket",
                "brand": "brand-a",
                "category": "outer",
                "price": "14900",
                "tags": ["winter", "windproof"],
                "sizes": ["S", "M"],
                "stock": "3",
                "margin_rate": "0.15",
            },
            {
                "product_id": "sku-200",
                "name": "summer top",
                "brand": "brand-b",
                "category": "top",
                "price": 7800,
                "tags": ["cotton", "summer"],
                "sizes": ["M"],
                "stock": 0,
                "margin_rate": 0.2,
            },
        ]
    )

    products = load_products_from_json(raw_text)

    assert len(products) == 2
    first = products[0]
    assert first.price == 14900
    assert isinstance(first.price, int)
    assert first.stock == 3
    assert isinstance(first.stock, int)
    assert isinstance(first.tags, tuple)
    assert first.tags == ("winter", "windproof")
    assert isinstance(first.sizes, tuple)
    assert first.sizes == ("S", "M")


def test_search_products_applies_combined_filters() -> None:
    query = SearchQuery(
        keyword="cotton",
        category="top",
        size="M",
        max_price=10000,
        in_stock_only=True,
    )
    products = [
        {
            "product_id": "sku-a",
            "name": "cotton polo",
            "brand": "brand-a",
            "category": "top",
            "price": 8600,
            "tags": ["cotton", "summer"],
            "sizes": ["S", "M"],
            "stock": 10,
            "margin_rate": 0.15,
        },
        {
            "product_id": "sku-b",
            "name": "cotton hoodie",
            "brand": "brand-b",
            "category": "top",
            "price": 12000,
            "tags": ["cotton", "winter"],
            "sizes": ["M"],
            "stock": 20,
            "margin_rate": 0.2,
        },
        {
            "product_id": "sku-c",
            "name": "cotton knit",
            "brand": "brand-c",
            "category": "top",
            "price": 9000,
            "tags": ["cotton", "basic"],
            "sizes": ["L", "XL"],
            "stock": 0,
            "margin_rate": 0.18,
        },
        {
            "product_id": "sku-d",
            "name": "linen shirt",
            "brand": "brand-d",
            "category": "top",
            "price": 8600,
            "tags": ["linen"],
            "sizes": ["M"],
            "stock": 15,
            "margin_rate": 0.12,
        },
    ]

    candidates = load_products_from_json(json.dumps(products))
    results = search_products(candidates, query)

    assert len(results) == 1
    assert results[0].product_id == "sku-a"


def test_search_products_combination_with_in_stock_only_false() -> None:
    products = load_products_from_json(
        json.dumps(
            [
                {
                    "product_id": "sku-1",
                    "name": "denim coat",
                    "brand": "brand-a",
                    "category": "coat",
                    "price": 30000,
                    "tags": ["winter"],
                    "sizes": ["M", "L"],
                    "stock": 0,
                    "margin_rate": 0.16,
                },
                {
                    "product_id": "sku-2",
                    "name": "denim vest",
                    "brand": "brand-b",
                    "category": "coat",
                    "price": 35000,
                    "tags": ["denim"],
                    "sizes": ["M"],
                    "stock": 1,
                    "margin_rate": 0.22,
                },
            ]
        )
    )

    query = SearchQuery(category="coat", size="M", in_stock_only=False)
    results = search_products(products, query)

    assert {product.product_id for product in results} == {"sku-1", "sku-2"}


def test_search_products_orders_by_availability_price_then_name() -> None:
    products = load_products_from_json(
        json.dumps(
            [
                {
                    "product_id": "sku-out-1",
                    "name": "zebra jacket",
                    "brand": "b1",
                    "category": "outer",
                    "price": 5500,
                    "tags": [],
                    "sizes": ["M"],
                    "stock": 0,
                    "margin_rate": 0.1,
                },
                {
                    "product_id": "sku-in-1",
                    "name": "basic tee",
                    "brand": "b2",
                    "category": "top",
                    "price": 5500,
                    "tags": ["cotton"],
                    "sizes": ["M"],
                    "stock": 3,
                    "margin_rate": 0.1,
                },
                {
                    "product_id": "sku-in-2",
                    "name": "alpha shirt",
                    "brand": "b3",
                    "category": "top",
                    "price": 4500,
                    "tags": ["cotton"],
                    "sizes": ["L"],
                    "stock": 2,
                    "margin_rate": 0.1,
                },
                {
                    "product_id": "sku-in-3",
                    "name": "charlie shirt",
                    "brand": "b4",
                    "category": "top",
                    "price": 5500,
                    "tags": ["linen"],
                    "sizes": ["M"],
                    "stock": 1,
                    "margin_rate": 0.1,
                },
            ]
        )
    )

    results = search_products(products, SearchQuery(in_stock_only=False))

    assert [product.name for product in results] == [
        "alpha shirt",
        "basic tee",
        "charlie shirt",
        "zebra jacket",
    ]
