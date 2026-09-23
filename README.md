# Fashion Personalization Platform

[![CI](https://github.com/cyson21/fashion-personalization-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/cyson21/fashion-personalization-platform/actions/workflows/ci.yml)

사용자 행동 이벤트로 상품을 추천하는 Python 3.11 백엔드입니다. 같은 이벤트가 두 번 오거나 처리에 실패해도 사용자 취향 데이터가 틀어지지 않게 했고, 추천마다 이유를 함께 보여 줍니다. 설계부터 구현, 테스트까지 혼자 진행한 개인 프로젝트입니다.

데이터는 메모리에 저장하고, 추천은 머신러닝이 아니라 정해 둔 점수 규칙으로 만듭니다. 핵심 로직은 외부 서비스 없이 돌고, FastAPI는 필요할 때 붙이는 구조입니다.

[포트폴리오](https://cyson21.github.io/projects/fashion-personalization-platform/) · [이력서](https://github.com/cyson21/portfolio-hub/releases/download/latest/resume.pdf)

## 풀려던 문제

같은 클릭이 두 번 들어가거나 실패한 이벤트가 계속 다시 반영되면, 추천 순위가 점점 엇나갑니다. 그래서 이벤트마다 처리 상태와 재시도 횟수를 관리하고, 추천 결과가 어느 이벤트까지 반영한 것인지 알 수 있게 했습니다.

## 설계

```text
명령행 도구 / 선택형 FastAPI
  -> PersonalizationService
       -> Catalog search
       -> InMemoryStore.add_event
       -> EventProcessor
            -> user profile update
            -> retry budget / dead-letter
       -> 규칙 기반 rank_products
       -> RecommendationBatchWorkflow
       -> 관리자 조회
  -> InMemoryStore
       -> 상품 / 프로필 / 이벤트 / 추천 결과 / 배치 이력
```

FastAPI의 `POST /events`는 이벤트를 `PENDING`으로 저장만 하고 바로 처리하지 않습니다. 지금 HTTP 쪽에는 대기 이벤트를 가져가 처리하는 워커가 없고, `PersonalizationService.process_pending_events()`를 직접 불러야 처리됩니다.

### 설계하면서 정한 것

| 결정 | 이유 | 코드 | 테스트 |
|---|---|---|---|
| 핵심 로직과 HTTP 분리 | 추천, 이벤트, 배치 로직을 웹 프레임워크 없이 돌리고, FastAPI는 필요할 때만 설치하려고 | [service.py](src/fashion_personalization/service.py), [api.py](src/fashion_personalization/api.py) | [test_api_adapter.py](tests/test_api_adapter.py) |
| 이벤트 지문으로 중복 확인 | 같은 키의 같은 이벤트는 한 번만 반영하고, 내용이 다른데 키가 같으면 오류로 구분하려고 | [store.py](src/fashion_personalization/store.py) | [test_event_processing.py](tests/test_event_processing.py) |
| 이벤트 상태를 나눠서 관리 | `PENDING`, `FAILED`, `DEAD_LETTER`, `REQUEUED`, `PROCESSED`를 따로 둬야 몇 번 재시도했고 재처리 결과가 어떤지 볼 수 있어서 | [events.py](src/fashion_personalization/events.py), [models.py](src/fashion_personalization/models.py) | [test_event_processing.py](tests/test_event_processing.py) |
| 정해 둔 점수 규칙 | 브랜드, 카테고리, 태그, 가격대, 사이즈, 재고 규칙으로 점수를 매겨야 추천 이유를 설명할 수 있어서 | [recommendation.py](src/fashion_personalization/recommendation.py) | [test_recommendation_engine.py](tests/test_recommendation_engine.py) |
| 추천 결과는 배치로 미리 생성 | 이벤트 처리와 추천 생성을 나누고, 사용자별 결과가 언제 기준인지 남기려고 | [batch.py](src/fashion_personalization/batch.py), [store.py](src/fashion_personalization/store.py) | [test_batch_workflow.py](tests/test_batch_workflow.py) |

## 실패 상황별 결과

- 같은 멱등 키로 같은 이벤트가 다시 와도 사용자 취향 데이터는 한 번만 바뀝니다.
- 같은 멱등 키에 다른 상품이나 내용이 오면, 기존 이벤트로 치지 않고 충돌로 처리합니다.
- 없는 상품처럼 몇 번을 다시 해도 안 되는 이벤트는 재시도를 다 쓴 뒤 정상 대기열에서 빠집니다.

## 확인한 방법

| 상황 | 결과 | 테스트 | 확인하지 않은 것 |
|---|---|---|---|
| 같은 이벤트 재전송 | 멱등 키와 이벤트 지문이 같으면 기존 이벤트 ID를 돌려주고 취향 데이터는 한 번만 바뀜 | [test_event_processing.py](tests/test_event_processing.py) | 프로세스 하나 안에서만 확인 |
| 멱등 키 충돌 | 같은 키에 다른 상품, 내용이면 `IdempotencyConflict` | [store.py](src/fashion_personalization/store.py), [test_event_processing.py](tests/test_event_processing.py) | 분산 저장소 동시 쓰기는 아님 |
| 실패 이벤트 분리 | 없는 상품 이벤트는 재시도를 다 쓰면 `DEAD_LETTER`로 이동 | [events.py](src/fashion_personalization/events.py), [test_event_processing.py](tests/test_event_processing.py) | 외부 큐나 비동기 처리자 없음 |
| 실패 이벤트 재처리 | 서비스 메서드가 새 멱등 키로 재처리 이벤트를 만들고 원본은 `REQUEUED`로 표시 | [service.py](src/fashion_personalization/service.py), [store.py](src/fashion_personalization/store.py) | FastAPI 재처리 API 없음 |
| 개인화 순위 | 행동 가중치와 취향이 순위와 이유에 반영되고, 싫어요 누른 상품과 품절 상품은 빠짐 | [recommendation.py](src/fashion_personalization/recommendation.py), [test_recommendation_engine.py](tests/test_recommendation_engine.py) | 머신러닝이나 온라인 평가는 아님 |
| 배치 갱신 | 활성 사용자별 추천 결과와 반영 이벤트 수, 기준 시점, 최신성 지표가 생성됨 | [batch.py](src/fashion_personalization/batch.py), [test_batch_workflow.py](tests/test_batch_workflow.py) | 스케줄러, 분산 배치 없음 |
| FastAPI | FastAPI 없이도 import되고, 설치하면 JSON 요청, 상품 조회, 이벤트 성공과 입력 오류, 멱등 충돌, 관리자 인증 응답을 TestClient로 확인 | [api.py](src/fashion_personalization/api.py), [test_api_adapter.py](tests/test_api_adapter.py) | 배포 서버, 네트워크, 비동기 처리자는 아님 |

## 대표 코드와 테스트

| 범위 | 코드 | 테스트 |
|---|---|---|
| 이벤트 저장·중복 처리 | [store.py](src/fashion_personalization/store.py) | [test_event_processing.py](tests/test_event_processing.py) |
| 상태 전이·재시도 | [events.py](src/fashion_personalization/events.py) | [test_event_processing.py](tests/test_event_processing.py) |
| 추천 순위와 이유 | [recommendation.py](src/fashion_personalization/recommendation.py) | [test_recommendation_engine.py](tests/test_recommendation_engine.py) |
| 배치 스냅샷 | [batch.py](src/fashion_personalization/batch.py) | [test_batch_workflow.py](tests/test_batch_workflow.py) |
| FastAPI 연결 | [api.py](src/fashion_personalization/api.py) | [test_api_adapter.py](tests/test_api_adapter.py) |

## 실행

### 핵심 로직과 CLI

준비 사항: Python 3.11 이상. 새 가상환경에서는 개발 의존성을 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
python -m compileall -q src
```

`.[dev]`만 설치한 이 단계에서는 FastAPI 경로 등록 테스트가 건너뛰어집니다. HTTP 연결 계층 검증은 다음 단계에서 선택 의존성과 함께 실행합니다.

개별 테스트는 다음처럼 실행할 수 있습니다.

```bash
python -m pytest tests/test_event_processing.py
python -m pytest tests/test_recommendation_engine.py
python -m pytest tests/test_batch_workflow.py
python -m pytest tests/test_cli_audit.py
```

### FastAPI

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

`demo-admin`은 로컬 시연용 고정 값입니다. 자동 테스트는 같은 프로세스 안의 TestClient로 HTTP 상태와 응답 형식만 확인합니다.

## 해 보지 않은 것

- 데이터는 `InMemoryStore`에 있어서 프로세스가 끝나면 사라집니다. 메시지 브로커, Outbox, HTTP 이벤트 워커는 만들지 않았습니다.
- 실패 이벤트 재처리는 서비스 메서드로만 있습니다. 고정 관리자 토큰과 HTTP 테스트가 실제 인증이나 배포 서버를 대신하지는 않습니다.
- 추천은 정해 둔 점수 규칙입니다. 학습 모델, 임베딩, 외부 추천 서비스, 품질 벤치마크는 없습니다.
- AWS 전환은 설계 문서만 있고, 배포, 부하, 장애 복구는 해 보지 않았습니다.

## 관련 문서

| 문서 | 내용 |
|---|---|
| [Architecture](docs/architecture.md) | 핵심 로직과 AWS 전환 후보를 분리한 구조 |
| [API and Data Model](docs/api-data-model.md) | 실제 FastAPI endpoint와 도메인 모델 |
