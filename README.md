# Fashion Personalization Platform

[![CI](https://github.com/cyson21/fashion-personalization-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/cyson21/fashion-personalization-platform/actions/workflows/ci.yml)

패션 커머스의 상품 탐색, 행동 이벤트 처리, 개인화 추천, 배치 스냅샷을 하나의 Python 3.11 서비스 경계에서 검증하는 백엔드 프로젝트입니다. 현재 데이터는 프로세스 내부 `InMemoryStore`에 저장하고, 추천은 머신러닝 모델이 아닌 결정론적 비즈니스 점수 계산으로 생성합니다.

핵심 로직은 외부 서비스 없이 실행되며 FastAPI는 선택형 연결 계층입니다. AWS 전환 구조는 설계 자료일 뿐 실제 배포 결과가 아닙니다.

[웹 사례](https://cyson21.github.io/projects/fashion-personalization-platform/) · [전체 포트폴리오 PDF](https://github.com/cyson21/portfolio-hub/releases/download/latest/portfolio-complete.pdf) · [최신 이력서](https://github.com/cyson21/portfolio-hub/releases/download/latest/resume.pdf)

## 담당 범위

개인 프로젝트로 행동 이벤트 처리, 사용자 프로필 갱신, 규칙 기반 추천 순위, 배치 스냅샷과 FastAPI 어댑터를 직접 설계·구현했습니다.

## 문제

중복되거나 실패한 행동 이벤트가 사용자 프로필에 반복 반영되면 추천 순위가 계속 왜곡됩니다. 이벤트 처리 상태와 재시도 범위를 관리하고, 어떤 이벤트까지 반영한 추천 결과인지 추적할 수 있어야 합니다.

## 아키텍처

```text
CLI / Optional FastAPI
  -> PersonalizationService
       -> Catalog search
       -> InMemoryStore.add_event
       -> EventProcessor
            -> user profile update
            -> retry budget / dead-letter
       -> deterministic rank_products
       -> RecommendationBatchWorkflow
       -> admin report
  -> InMemoryStore
       -> products / profiles / events / snapshots / batch reports
```

FastAPI의 `POST /events`는 이벤트를 `PENDING`으로 저장하고 즉시 처리하지 않습니다. 현재 HTTP 연결 계층에는 대기 이벤트를 소비하는 처리자가 없으며, 처리는 `PersonalizationService.process_pending_events()`를 직접 호출하는 핵심 서비스 흐름에서만 수행됩니다.

## 핵심 설계 판단

| 결정 | 구현 이유 | 코드 | 테스트 |
|---|---|---|---|
| 핵심 로직과 HTTP 분리 | 추천·이벤트·배치 로직을 웹 프레임워크 없이 반복 검증하고 FastAPI를 선택 설치하기 위함 | [service.py](src/fashion_personalization/service.py), [api.py](src/fashion_personalization/api.py) | [test_api_adapter.py](tests/test_api_adapter.py) |
| 이벤트 지문 기반 멱등 처리 | 같은 키의 동일 이벤트는 한 번만 반영하고, 다른 내용이 같은 키를 재사용하면 오류로 구분 | [store.py](src/fashion_personalization/store.py) | [test_event_processing.py](tests/test_event_processing.py) |
| 명시적인 이벤트 상태 전이 | `PENDING`, `FAILED`, `DEAD_LETTER`, `REQUEUED`, `PROCESSED`를 분리해 재시도 횟수와 재처리 결과를 관찰 | [events.py](src/fashion_personalization/events.py), [models.py](src/fashion_personalization/models.py) | [test_event_processing.py](tests/test_event_processing.py) |
| 결정론적 추천 점수 | 브랜드·카테고리·태그·가격대·사이즈·재고 규칙을 결과 이유와 함께 검증 가능하게 유지 | [recommendation.py](src/fashion_personalization/recommendation.py) | [test_recommendation_engine.py](tests/test_recommendation_engine.py) |
| 조회용 배치 스냅샷 | 이벤트 처리와 추천 결과 생성을 분리하고 사용자별 결과·처리 기준 시점·최신성 지표를 기록 | [batch.py](src/fashion_personalization/batch.py), [store.py](src/fashion_personalization/store.py) | [test_batch_workflow.py](tests/test_batch_workflow.py) |

## 검증 시나리오

| 시나리오 | 관찰 결과 | 근거 | 범위 제한 |
|---|---|---|---|
| 동일 이벤트 재전송 | 같은 멱등 키와 이벤트 지문이면 기존 이벤트 ID를 반환하고 사용자 프로필을 한 번만 갱신 | [test_event_processing.py](tests/test_event_processing.py) | 단일 프로세스 메모리 내부 동작 |
| 멱등 키 충돌 | 같은 키에 다른 상품·내용을 사용하면 `IdempotencyConflict` 발생 | [store.py](src/fashion_personalization/store.py), [test_event_processing.py](tests/test_event_processing.py) | 분산 저장소의 동시 쓰기 검증 아님 |
| 실패 이벤트 분리 | 존재하지 않는 상품 이벤트가 재시도 횟수를 소진하면 `DEAD_LETTER`로 이동 | [events.py](src/fashion_personalization/events.py), [test_event_processing.py](tests/test_event_processing.py) | 외부 큐나 비동기 처리자 없음 |
| 실패 이벤트 재처리 | 서비스 메서드가 새 멱등 키로 재처리 이벤트를 만들고 원본을 `REQUEUED`로 표시 | [service.py](src/fashion_personalization/service.py), [store.py](src/fashion_personalization/store.py) | FastAPI 재처리 API 없음 |
| 개인화 순위 | 행동 가중치와 선호 속성이 추천 순위·이유에 반영되고 dislike 상품과 품절 상품은 제외 | [recommendation.py](src/fashion_personalization/recommendation.py), [test_recommendation_engine.py](tests/test_recommendation_engine.py) | ML 학습·온라인 평가 결과 아님 |
| 배치 갱신 | 활성 사용자별 추천 스냅샷과 반영 이벤트 수, 처리 기준 시점, 최신성 지표 생성 | [batch.py](src/fashion_personalization/batch.py), [test_batch_workflow.py](tests/test_batch_workflow.py) | 스케줄러·분산 배치 실행 없음 |
| FastAPI 어댑터 | 선택 의존성 없이 import 가능하며, 설치 시 JSON request body 계약·상품 조회·이벤트 성공/검증 실패/멱등 충돌·관리자 인증 응답을 TestClient로 검증 | [api.py](src/fashion_personalization/api.py), [test_api_adapter.py](tests/test_api_adapter.py) | 배포 서버·네트워크·비동기 워커 검증 아님 |

## 실행

### 핵심 로직과 CLI

준비 사항: Python 3.11 이상. 새 가상환경에서는 개발 의존성을 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/run_portfolio_audit.py
```

`run_portfolio_audit.py`는 임시 바이트코드 경로와 비활성화한 pytest 캐시를 사용해 문법 검사, 전체 pytest, CLI JSON 출력을 순서대로 실행합니다. CLI 결과는 로컬 핵심 로직만 다루며 외부 모델·AWS·HTTP 실행 환경을 포함하지 않습니다.

`.[dev]`만 설치한 이 단계에서는 FastAPI 경로 등록 테스트가 건너뛰어집니다. HTTP 연결 계층 검증은 다음 단계에서 선택 의존성과 함께 실행합니다.

개별 테스트는 다음처럼 실행할 수 있습니다.

```bash
python -m pytest tests/test_event_processing.py
python -m pytest tests/test_recommendation_engine.py
python -m pytest tests/test_batch_workflow.py
python -m pytest tests/test_cli_audit.py
```

### 선택형 FastAPI

FastAPI와 uvicorn을 별도로 설치한 환경에서만 실행합니다.

```bash
python -m pip install -e ".[dev,api]"
python -m pytest tests/test_api_adapter.py
uvicorn "fashion_personalization.api:create_app" --factory --reload
```

서버는 첫 번째 터미널에서 실행하고, 다음 상태·관리자 조회 엔드포인트는 두 번째 터미널에서 확인합니다. 두 요청은 HTTP `200`을 기대합니다.

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS -H 'X-Admin-Token: demo-admin' http://127.0.0.1:8000/admin/report
```

`demo-admin`은 로컬 시연용 고정 값입니다. 자동 테스트는 in-process TestClient에서 주요 HTTP 상태와 응답 구조를 확인하며, 배포 서버·네트워크·비동기 워커 동작을 증명하지 않습니다.

## 제한 사항

- 상태는 `InMemoryStore`에 있어 프로세스 종료 시 사라지고, 메시지 브로커·outbox·HTTP 이벤트 워커는 구현하지 않았습니다.
- 실패 이벤트 재처리는 서비스 메서드 수준이며, 고정 관리자 토큰과 HTTP 회귀 테스트는 운영 인증·배포 서버 검증을 대신하지 않습니다.
- 추천은 결정론적 규칙 기반 점수이며 학습 모델, embedding, 외부 추천 서비스, 품질 벤치마크를 포함하지 않습니다.
- AWS 전환은 설계 자료이며 배포·부하·장애 복구 결과가 없습니다.

## 관련 문서

| 문서 | 내용 |
|---|---|
| [Architecture](docs/architecture.md) | 핵심 로직과 AWS 전환 후보를 분리한 구조 |
| [API and Data Model](docs/api-data-model.md) | 실제 FastAPI endpoint와 도메인 모델 |
