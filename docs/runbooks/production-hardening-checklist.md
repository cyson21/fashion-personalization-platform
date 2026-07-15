# Production Hardening Checklist

이 문서는 운영 전환 전에 필요한 후속 작업을 분리해 둔다. 현재 포트폴리오 완료 범위는 local deterministic proof다.

## API

- FastAPI dependency 고정과 OpenAPI schema snapshot 추가
- request validation model 분리
- 인증/인가, 관리자 role guard 추가
- rate limit과 idempotency key 보존 기간 정책 추가

## Persistence

- PostgreSQL repository 구현
- 행동 이벤트용 append-only store 구현
- batch snapshot table 또는 S3 artifact schema 확정
- migration과 rollback 절차 추가

## Async Processing

- SQS/EventBridge message schema 고정
- Lambda/Fargate worker 배포 구성 추가
- retry backoff, DLQ replay, poison message 격리 구현
- batch freshness metric과 alert 추가

## Recommendation Quality

- offline evaluation dataset 추가
- click-through proxy metric과 cold-start metric 추가
- A/B assignment와 experiment report 추가
- feature drift 감지 추가

## Deployment

- ECS Fargate task definition
- Lambda worker IaC
- RDS, S3, SQS, CloudWatch 구성
- 비용 상한과 staging/prod 분리

## Security

- secret manager 연동
- 관리자 endpoint audit log
- 개인정보 삭제 요청 처리
- event payload PII minimization 점검
