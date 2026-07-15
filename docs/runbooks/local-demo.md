# Local Demo Runbook

## 전제

- Python 3.11 이상
- 네트워크 설치 불필요
- API key, Docker 불필요

## 검증

```bash
python3 -m pytest
python3 -m compileall -q src
python3 scripts/run_portfolio_audit.py
```

## Audit Output 확인

`scripts/run_portfolio_audit.py`는 아래를 순서대로 실행한다.

1. Python compile check
2. pytest
3. demo service 기반 JSON audit 출력

JSON audit에는 admin report, sample recommendations, claim boundary가 포함된다.

## 선택 FastAPI 실행

FastAPI는 현재 기본 의존성이 아니다. REST endpoint를 직접 띄우려면 명시적으로 설치한다.

```bash
python3 -m pip install -e ".[api]"
uvicorn "fashion_personalization.api:create_app" --factory --reload
```

## 면접 데모 순서

1. `README.md`의 한눈에 보기와 아키텍처를 보여준다.
2. `python3 scripts/run_portfolio_audit.py`로 로컬 증거를 생성한다.
3. `docs/portfolio-one-pager.md`에서 공고 요구사항 대응표를 설명한다.
4. 실제 AWS 배포가 아닌 local deterministic proof임을 먼저 밝힌다.

## 현재 기본 검증 범위

- FastAPI adapter import와 route 정의는 코드/테스트로 확인한다.
- 실제 HTTP smoke, OpenAPI snapshot, 관리자 인증 운영화는 선택 의존성 설치 후 후속 경로다.
- 이벤트 처리는 로컬 in-process worker로 검증하고, Lambda/ECS 전환은 문서화된 설계 범위다.
