# gPlanner PPA Agent 테스트 스위트

본 디렉토리는 gPlanner PPA Agent의 안정성을 검증하기 위한 테스트 코드를 포함하고 있습니다.

## 1. 테스트 환경 설정
테스트를 실행하기 위해 `uv`를 통해 의존성을 동기화합니다.
```bash
uv sync
```

## 2. 테스트 실행 방법
### 전체 테스트 실행
```bash
uv run python -m pytest
```
또는 스크립트 사용: `./scripts/test.sh`

### 커버리지 리포트 포함 실행
`pytest.ini`에 기본적으로 설정되어 있으며, 실행 후 CLI 터미널에서 확인 가능합니다.

### 특정 테스트 파일 실행
```bash
python -m pytest tests/api/v1/test_chat.py
```

## 3. 테스트 구조

- `conftest.py`: 전역 Fixtures (FastAPI app, Async Client, Supabase Mock 등)
- `unit/`: 단위 테스트 (Core 유틸리티, Service 로직, Schema 검증)
- `api/`: API 통합 테스트 (Endpoint 호출 및 연동 검증)
- `mocks/`: 재사용 가능한 모킹 객체 및 데이터

## 4. 주요 기술 스택

- **pytest**: 메인 테스트 프레임워크
- **pytest-asyncio**: 비동기 테스트 지원
- **httpx**: 비동기 HTTP 클라이언트 및 API 테스트
- **respx**: 외부 HTTP 호출(LLM API 등) 모킹
- **pytest-mock**: Mocking 및 Monkeypatching 지원
- **freezegun**: 시간 의존성 로직 테스트 (JWT 만료 등)
- **pytest-cov**: 테스트 커버리지 측정
