from __future__ import annotations

import json
from pathlib import Path

from fashion_personalization.models import Product, SearchQuery


def load_products(path: Path) -> list[Product]:
    return load_products_from_json(path.read_text(encoding="utf-8"))


def load_products_from_json(raw_text: str) -> list[Product]:
    raw_products = json.loads(raw_text)
    return [
        Product(
            product_id=item["product_id"],
            name=item["name"],
            brand=item["brand"],
            category=item["category"],
            price=int(item["price"]),
            tags=tuple(item["tags"]),
            sizes=tuple(item["sizes"]),
            stock=int(item["stock"]),
            margin_rate=float(item["margin_rate"]),
        )
        for item in raw_products
    ]


def search_products(products: list[Product], query: SearchQuery) -> list[Product]:
    keyword = query.keyword.lower() if query.keyword else None
    results: list[Product] = []
    for product in products:
        if query.in_stock_only and not product.available:
            continue
        if query.category and product.category != query.category:
            continue
        if query.size and query.size not in product.sizes:
            continue
        if query.max_price is not None and product.price > query.max_price:
            continue
        if keyword:
            haystack = " ".join((product.name, product.brand, product.category, *product.tags)).lower()
            if keyword not in haystack:
                continue
        results.append(product)
    return sorted(results, key=lambda item: (not item.available, item.price, item.name))
