# Architecture

## Local Runtime

```text
CLI / Optional FastAPI
  -> PersonalizationService
       -> Catalog search
       -> Event ingestion
       -> EventProcessor
       -> RecommendationBatchWorkflow
       -> Admin report
  -> InMemoryStore
```

## Core Flow

1. 사용자가 상품을 조회하거나 클릭, 장바구니, 구매, dislike 이벤트를 남긴다.
2. API surface는 idempotency key와 함께 이벤트를 저장한다.
3. EventProcessor는 상품 존재 여부를 확인하고 user profile을 갱신한다.
4. 처리 실패는 retry budget을 소진한 뒤 dead-letter로 이동한다.
5. BatchWorkflow는 활성 사용자별 recommendation snapshot을 생성한다.
6. 관리자 report는 상품, 사용자, 이벤트, dead-letter, snapshot 상태를 반환한다.

## AWS 전환 설계

| Local 구성 | AWS 전환 후보 | 역할 |
|---|---|---|
| Optional FastAPI app | ECS Fargate service | 사용자 API와 관리자 API |
| EventProcessor | Lambda worker 또는 Fargate worker | SQS/EventBridge 이벤트 처리 |
| InMemoryStore products/profiles | RDS PostgreSQL | 상품, 사용자 profile, batch metadata |
| Event log | DynamoDB 또는 MongoDB | append-oriented 행동 이벤트 저장 |
| Recommendation snapshot | RDS table 또는 S3 JSON/Parquet | 추천 결과 조회 최적화 |
| CLI audit | CloudWatch scheduled check | batch freshness와 DLQ 모니터링 |

## Failure Handling

| 실패 모드 | 처리 |
|---|---|
| 중복 이벤트 | `idempotency_key`로 기존 이벤트를 반환하고 profile 중복 반영을 막는다. |
| 알 수 없는 상품 | retry budget을 소진한 뒤 dead-letter로 분리한다. |
| 추천 batch 누락 | user별 snapshot과 batch report를 비교한다. |
| 재고 없음 | ranking 후보에서 제외한다. |
| 선호도 오염 | dislike event를 negative product set에 반영한다. |

## 확장 포인트

- FastAPI dependency를 설치하면 REST endpoint를 즉시 띄울 수 있다.
- `InMemoryStore`를 PostgreSQL/MongoDB 구현으로 교체할 수 있도록 service boundary를 분리했다.
- 대량 추천 batch는 S3 artifact와 event-driven worker로 분산할 수 있다.
- 고성능 내부 추천 scoring 서비스가 필요해지면 gRPC adapter를 별도 모듈로 추가한다.
