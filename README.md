# PubMed API 기반 논문 데이터 수집·분석 웹 애플리케이션

PubMed 논문을 검색·수집해 SQLite에 저장하고, 저장된 메타데이터의 개요와
검색 결과를 확인하며 CSV 다운로드 및 메모리 챗봇을 사용할 수 있는
Streamlit 애플리케이션입니다.

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
- `pubmed_app/chatbot.py`: 대화 이력을 기억하는 논문 탐색 챗봇

## 실행

```powershell
uv pip install -r requirements.txt
uv run streamlit run app.py
```

기본 DB 경로는 `data/pubmed.db`, 기본 테이블명은 `articles`입니다.
필요하면 다음 환경 변수를 지정할 수 있습니다.

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
uv run python -m unittest discover -v
```
