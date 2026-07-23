# PubMed 논문 분석 웹 애플리케이션

이 브랜치는 팀 요구사항 중 **3번(개요)**, **4번(논문 검색)**,
**5번(메모리 챗봇)**, **6번(필터 결과 CSV 다운로드)**을 통합합니다.
PubMed 수집과 DB 저장 등 다른 요구사항은 포함하지 않습니다.

## 실행

```powershell
uv pip install -r requirements.txt
uv run streamlit run app.py
```

기본 DB 경로는 `data/pubmed.db`, 기본 테이블명은 `articles`입니다. 팀의 DB 설정이
다르면 실행 전에 다음 환경 변수를 지정합니다.

```powershell
$env:PUBMED_DB_PATH="data/pubmed.db"
$env:PUBMED_ARTICLE_TABLE="articles"
$env:PUBMED_TOP_JOURNAL_LIMIT="10"
uv run streamlit run app.py
```

`articles` 테이블에는 아래 필드가 있어야 합니다.

- `pmid` (PK)
- `title`
- `abstract`
- `journal`
- `pub_year`
- `authors`

이 구현은 테이블을 생성하거나 데이터를 변경하지 않고 읽기 전용으로 조회합니다.
DB나 필수 필드가 아직 준비되지 않았으면 Streamlit 화면에 안내 문구를 표시합니다.

## 팀 모듈 연동

수집 담당 모듈은 수집 완료 후 아래 Streamlit 세션 키에 정수 값을 기록하면 됩니다.

```python
st.session_state["last_collection_new_count"] = inserted_count
st.session_state["last_collection_skipped_count"] = skipped_count
```

개요 화면은 이 값을 최근 신규 수집 수와 중복 Skip 수로 표시합니다.

구조는 다음과 같이 분리되어 있습니다.

- `pubmed_app/domain`: 화면·DB에 독립적인 데이터 모델
- `pubmed_app/repositories`: SQLite 조회 및 저장소 인터페이스
- `pubmed_app/services`: 개요 집계와 검색 조건 검증
- `pubmed_app/ui`: Streamlit 개요/논문 목록 및 CSV 다운로드 화면
- `pubmed_app/chatbot.py`: 대화 이력을 기억하는 논문 탐색 챗봇
- `pubmed_app/paper_search.py`: 챗봇 조회와 CSV 변환
- `app.py`: 객체 조립과 Streamlit 실행 진입점

## 테스트

```powershell
$env:UV_CACHE_DIR=".uv-cache"
uv run python -m unittest discover -v
```
