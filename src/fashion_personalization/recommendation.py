from __future__ import annotations

from fashion_personalization.models import EventType, Product, Recommendation, UserEvent, UserProfile

EVENT_WEIGHTS = {
    EventType.VIEW: 0.4,
    EventType.CLICK: 0.8,
    EventType.ADD_TO_CART: 1.4,
    EventType.PURCHASE: 2.2,
    EventType.DISLIKE: -2.4,
}


def apply_event_to_profile(profile: UserProfile, product: Product, event: UserEvent) -> None:
    weight = EVENT_WEIGHTS[event.event_type]
    if event.event_type == EventType.DISLIKE:
        profile.negative_product_ids.add(product.product_id)
    else:
        _add_weight(profile.preferred_brands, product.brand, weight)
        _add_weight(profile.preferred_categories, product.category, weight)
        for tag in product.tags:
            _add_weight(profile.preferred_tags, tag, weight / max(len(product.tags), 1))
        selected_size = event.payload.get("size")
        if isinstance(selected_size, str) and selected_size in product.sizes:
            _add_weight(profile.size_preferences, selected_size, max(weight, 0.1))
        if profile.target_price is None:
            profile.target_price = float(product.price)
            profile.target_price_weight = max(weight, 0.1)
        else:
            next_weight = max(weight, 0.1)
            total_weight = profile.target_price_weight + next_weight
            profile.target_price = (
                (profile.target_price * profile.target_price_weight)
                + (float(product.price) * next_weight)
            ) / total_weight
            profile.target_price_weight = total_weight
    profile.touch()


def rank_products(profile: UserProfile, products: list[Product], limit: int = 5) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for product in products:
        if product.product_id in profile.negative_product_ids:
            continue
        if not product.available:
            continue
        score, reasons = _score_product(profile, product)
        recommendations.append(Recommendation(product_id=product.product_id, score=round(score, 4), reasons=tuple(reasons)))
    return sorted(recommendations, key=lambda item: (-item.score, item.product_id))[:limit]


def _score_product(profile: UserProfile, product: Product) -> tuple[float, list[str]]:
    score = 0.25
    reasons: list[str] = ["available"]
    if profile.event_count == 0:
        reasons.append("cold-start")

    brand_score = profile.preferred_brands.get(product.brand, 0.0)
    if brand_score:
        score += brand_score * 1.3
        reasons.append(f"brand:{product.brand}")

    category_score = profile.preferred_categories.get(product.category, 0.0)
    if category_score:
        score += category_score * 1.1
        reasons.append(f"category:{product.category}")

    matched_tags = [tag for tag in product.tags if tag in profile.preferred_tags]
    if matched_tags:
        score += sum(profile.preferred_tags[tag] for tag in matched_tags) * 0.9
        reasons.append("tags:" + ",".join(sorted(matched_tags)))

    matched_sizes = [size for size in product.sizes if size in profile.size_preferences]
    if matched_sizes:
        score += sum(profile.size_preferences[size] for size in matched_sizes) * 0.35
        reasons.append("sizes:" + ",".join(sorted(matched_sizes)))

    if profile.target_price:
        distance = abs(product.price - profile.target_price) / max(profile.target_price, 1)
        price_score = max(0.0, 1.0 - distance)
        score += price_score * 0.8
        reasons.append("price-fit")

    if product.margin_rate >= 0.35:
        score += 0.15
        reasons.append("healthy-margin")

    if product.stock <= 3:
        score -= 0.2
        reasons.append("low-stock")

    return score, reasons


def _add_weight(bucket: dict[str, float], key: str, weight: float) -> None:
    bucket[key] = round(bucket.get(key, 0.0) + weight, 4)
