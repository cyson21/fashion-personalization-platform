# ADR-002. 이벤트 처리와 Batch 추천의 증거 경계 분리

## 상태

Accepted

## 배경

추천/개인화 프로젝트는 ranking 결과만 보여주면 백엔드 운영 역량이 약하게 보인다. 공고는 비동기 처리, 이벤트 기반 시스템, batch workflow, 운영 자동화를 함께 요구한다.

## 결정

사용자 행동 이벤트 처리와 batch recommendation snapshot 생성을 분리한다. 이벤트는 idempotency, retry, dead-letter를 갖고, batch는 active user profile을 기준으로 materialized snapshot과 report를 남긴다.

## 결과

- 실시간 이벤트 처리 실패가 추천 조회 전체 장애로 번지지 않는다.
- batch freshness와 DLQ를 관리자 리포트로 확인할 수 있다.
- Local proof와 AWS Lambda/ECS 운영 설계가 분리되어 과장 표기를 피할 수 있다.
