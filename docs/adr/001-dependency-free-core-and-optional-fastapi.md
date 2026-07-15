# ADR-001. Dependency-free Core와 선택 FastAPI Adapter 분리

## 상태

Accepted

## 배경

핵심 추천·이벤트 로직은 웹 프레임워크 설치 여부와 무관하게 반복 검증할 수 있어야 한다. FastAPI는 HTTP 경계를 제공하지만, 외부 의존성 설치가 core 검증의 선행 조건이 되면 실행 재현성이 낮아진다.

## 결정

추천, 이벤트, batch, 관리자 리포트는 표준 라이브러리 기반 core로 구현한다. FastAPI endpoint는 `api.py`의 선택 adapter로 분리하고, FastAPI가 설치된 환경에서만 app factory가 실행되도록 한다.

## 결과

- 기본 검증은 `pytest`와 `compileall`로 통과한다.
- FastAPI API surface는 코드로 제시하되, 선택 의존성 설치 전에는 runtime 증거로 주장하지 않는다.
- 서비스 계층은 Django/FastAPI 어느 쪽으로도 감쌀 수 있는 형태로 유지된다.
