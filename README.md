# PubMed API 기반 논문 데이터 수집·분석 웹 애플리케이션

현재 담당 구현 범위는 요구사항 1(검색 조건 입력)과 요구사항 2(PubMed 수집 및 중복 방지 저장)입니다.

## 코드 구조

- `app.py`: Streamlit 사이드바와 수집 결과 메시지
- `collection_service.py`: 검색, 상세 조회, 저장 작업의 실행 순서
- `pubmed_client.py`: PubMed E-utilities 호출과 XML 파싱
- `database.py`: SQLite 테이블 생성과 PMID 중복 방지 저장
- `models.py`: 계층 사이에서 전달하는 데이터 객체

## 실행

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

선택적으로 `NCBI_EMAIL`, `NCBI_API_KEY` 환경변수를 설정할 수 있습니다.
