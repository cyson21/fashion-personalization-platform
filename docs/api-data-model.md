# API and Data Model

## Optional REST API

FastAPI가 설치된 환경에서 `fashion_personalization.api:create_app` factory를 사용한다.

| Method | Path | 목적 |
|---|---|---|
| `GET` | `/health` | API 상태 확인 |
| `GET` | `/products` | keyword, category, size 기반 상품 검색 |
| `POST` | `/events` | 사용자 행동 이벤트 기록 |
| `GET` | `/users/{user_id}/recommendations` | 현재 profile 기준 추천 조회 |
| `POST` | `/admin/batches/{batch_id}` | 추천 batch snapshot 생성 |
| `GET` | `/admin/report` | 운영 지표 조회 |

## Domain Models

| 모델 | 주요 필드 | 설명 |
|---|---|---|
| `Product` | brand, category, price, tags, sizes, stock, margin_rate | 패션 상품 catalog |
| `UserProfile` | preferred_brands, preferred_categories, preferred_tags, target_price | 행동 이벤트에서 만든 개인화 profile |
| `UserEvent` | idempotency_key, user_id, product_id, event_type, status, attempts | 이벤트 처리와 retry 단위 |
| `Recommendation` | product_id, score, reasons | 추천 결과와 설명 가능한 scoring 이유 |
| `RecommendationSnapshot` | user_id, recommendations, generated_at, source_event_count | batch 결과 materialized view |
| `BatchReport` | users_scanned, snapshots_written, skipped_users, failed_events, event_watermark_at_run, stale_snapshot_users | 관리자 batch 결과와 freshness 지표 |
| `AdminReport` | processed_events, pending_events, failed_events, dead_letter_events, event_watermark, batch_age_seconds | 운영 상태와 batch freshness 지표 |

## Event Types

| 이벤트 | 추천 반영 |
|---|---|
| `view` | 낮은 가중치로 선호 신호 반영 |
| `click` | 중간 가중치로 선호 신호 반영 |
| `add_to_cart` | 높은 가중치로 선호 신호 반영 |
| `purchase` | 가장 높은 긍정 신호로 반영 |
| `dislike` | 해당 상품을 negative set에 넣고 추천에서 제외 |

## Data Store Boundary

현재 구현은 `InMemoryStore`를 사용한다. 운영 전환 시에는 아래처럼 분리한다.

| 저장 영역 | 운영 후보 |
|---|---|
| Products | PostgreSQL |
| User profiles | PostgreSQL 또는 MongoDB |
| Event log | DynamoDB, MongoDB, Kafka compacted topic |
| Dead-letter | SQS DLQ 또는 PostgreSQL event table |
| Batch snapshots | PostgreSQL table 또는 S3 artifact |

## 운영 Alert 기준

| 지표 | 의미 | 예시 기준 |
|---|---|---|
| `failed_events` | retry 가능한 실패 backlog | 0보다 크면 worker 상태 확인 |
| `dead_letter_events` | retry budget을 소진한 미해결 이벤트 | 0보다 크면 원인별 재처리 |
| `pending_events` | 아직 처리되지 않은 이벤트 | 지속 증가 시 worker 지연 확인 |
| `batch_age_seconds` | 최신 batch report 생성 후 경과 시간 | 허용 주기 초과 시 batch 재실행 |
| `batch_event_lag_seconds` | batch 이후 처리 이벤트와 batch 시점 차이 | 0보다 크면 snapshot freshness 확인 |
