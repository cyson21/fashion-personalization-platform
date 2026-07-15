from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from fashion_personalization.service import build_demo_service


def main() -> int:
    service = build_demo_service()
    recommendations = service.recommend_now("u-100", limit=3)
    report = {
        "project": "fashion-personalization-platform",
        "verificationScope": "local-deterministic",
        "adminReport": service.admin_report(),
        "sampleRecommendations": recommendations,
        "latestSnapshot": service.get_snapshot("u-100"),
        "claimBoundary": [
            "FastAPI adapter is optional and requires local installation.",
            "AWS Lambda/ECS/S3/RDS architecture is documented, not deployed in this local proof.",
            "Recommendation ranking is deterministic business logic, not an external ML model.",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))
    return 0


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


if __name__ == "__main__":
    raise SystemExit(main())
