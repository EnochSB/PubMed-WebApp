# PubMed API 기반 논문 데이터 수집·분석 웹 애플리케이션

PubMed 논문을 검색·수집해 SQLite에 저장하고, 저장된 메타데이터의 개요와
검색 결과를 확인하며 CSV 다운로드 및 메모리 챗봇을 사용할 수 있는
Streamlit 애플리케이션입니다. 서비스 이름은 **메디톡톡**이며 Google 계정으로
로그인한 사용자는 자신이 수집한 논문만 조회할 수 있습니다.

## 코드 구조

- `app.py`: 전체 기능의 객체 조립과 Streamlit 진입점
- `collection_service.py`: PubMed 검색·조회·저장 흐름
- `pubmed_client.py`: PubMed E-utilities 호출과 XML 파싱
- `database.py`: SQLite 테이블 생성과 PMID 중복 방지 저장
- `models.py`: 수집 계층 데이터 객체
- `pubmed_app/domain`: 분석 계층 데이터 모델
- `pubmed_app/repositories`: SQLite 조회 저장소
- `pubmed_app/services`: 개요 집계와 검색 조건 검증
- `pubmed_app/ui`: 개요·논문 목록·CSV 다운로드 화면
- `pubmed_app/chatbot.py`: 대화 이력과 논문 문맥을 사용하는 GPT-5.4 mini 챗봇
- `pubmed_app/medical_middleware.py`: 개인 의료 질문을 차단하는 두 단계 미들웨어

## Google 로그인 설정

1. Google Cloud Console에서 OAuth 2.0 웹 애플리케이션 클라이언트를 만듭니다.
2. 승인된 리디렉션 URI에 `http://localhost:8501/oauth2callback`을 등록합니다.
3. `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사합니다.
4. Google Client ID, Client Secret과 무작위 `cookie_secret`을 입력합니다.

배포 시에는 Google Console과 `secrets.toml`의 `redirect_uri`를 실제 서비스
주소의 `/oauth2callback`으로 함께 변경해야 합니다. 실제 비밀값이 포함된
`.streamlit/secrets.toml`은 Git에서 제외됩니다.

DB에는 전역 논문 원본을 보관하는 `articles`, Google 사용자를 보관하는
`app_users`, 사용자와 수집 논문을 연결하는 `user_articles` 테이블이 생성됩니다.
개요·검색·CSV·챗봇은 로그인한 사용자의 `user_articles`에 연결된 논문만 조회합니다.

## 실행

```powershell
uv pip install -r requirements.txt
uv run streamlit run app.py
```

기본 DB 경로는 `data/pubmed.db`, 기본 테이블명은 `articles`입니다.

OpenAI API 키는 Git에서 제외된 `.env` 파일에 저장합니다.

```dotenv
OPENAI_API_KEY=발급받은_API_키
```

챗봇은 모델 호출 직전에 `load_dotenv()`로 키를 읽고 공식 모델 ID인
`gpt-5.4-mini`를 사용합니다. 그 밖의 설정은 다음 환경 변수로 지정할 수 있습니다.

챗봇 질문 처리 규칙은 다음과 같습니다.

- 의료 조언·진단·처방 키워드가 있으면 고정 안내 문구를 반환하고 DB와 모델 호출 차단
- 논문 관련 질문이며 DB 검색 결과가 있으면 논문 메타데이터를 문맥으로 모델 호출
- 논문 관련 질문이지만 검색 결과가 없으면 모델을 호출하지 않고 미검색 안내 반환
- 논문과 관련 없는 일반 질문이면 논문 문맥 없이 모델 호출

의료 질문은 LangChain의 Node-style `before_agent`에서 먼저 검사하고,
Wrap-style `wrap_model_call`에서는 최신 사용자 질문의 의미를 `BLOCK/ALLOW`로
분류합니다. `BLOCK`이면 고정 안내 문구를 반환하고, `ALLOW`일 때만 원래 질문의
답변을 생성합니다.

대화 이력은 논문 DB와 같은 SQLite 파일의 `chat_messages`, `chat_states` 테이블에
저장합니다. 로그인된 사용자는 `sub` 또는 이메일을 해시한 사용자 ID로 분리되어
다른 사용자의 대화와 섞이지 않으며, 서버를 재시작해도 이전 대화가 유지됩니다.
로그인이 설정되지 않은 개발 환경에서는 브라우저 세션별 임시 ID를 사용합니다.

단일 Streamlit 서버에는 SQLite가 적합하지만 여러 서버 인스턴스가 동시에 동일한
대화를 공유해야 하는 환경에서는 PostgreSQL 같은 공용 DB로 이전해야 합니다.

```powershell
$env:PUBMED_DB_PATH="data/pubmed.db"
$env:PUBMED_ARTICLE_TABLE="articles"
$env:PUBMED_TOP_JOURNAL_LIMIT="10"
$env:NCBI_EMAIL="researcher@example.com"
$env:NCBI_API_KEY="..."
uv run streamlit run app.py
```

## 테스트

```powershell
$env:UV_CACHE_DIR=".uv-cache"
uv run python -m pytest -q
```
