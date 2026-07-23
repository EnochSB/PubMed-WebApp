"""PubMed E-utilities API 클라이언트와 XML 파서입니다."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable

import requests

from models import Article, SearchConditions


DEFAULT_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedApiError(RuntimeError):
    """PubMed 요청 또는 응답 처리 실패를 UI에 전달하는 예외입니다."""


class PubMedXmlParser:
    """PubMed XML에서 DB 필수 필드를 추출합니다."""

    def parse(self, xml_data: bytes | str) -> list[Article]:
        """XML 문서의 각 PubmedArticle을 Article 객체 목록으로 변환합니다."""

        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as error:
            raise PubMedApiError("PubMed XML 응답을 해석할 수 없습니다.") from error

        articles: list[Article] = []
        for node in root.findall(".//PubmedArticle"):
            citation = node.find("MedlineCitation")
            article_node = citation.find("Article") if citation is not None else None
            if citation is None or article_node is None:
                continue

            pmid = self._text(citation.find("PMID"))
            if not pmid:
                continue

            articles.append(
                Article(
                    pmid=pmid,
                    title=self._text(article_node.find("ArticleTitle")) or "제목 없음",
                    abstract=self._abstract(article_node),
                    journal=self._journal(article_node),
                    pub_year=self._publication_year(citation, article_node),
                    authors=self._authors(article_node),
                )
            )
        return articles

    @staticmethod
    def _text(node: ET.Element | None) -> str:
        """하위 강조 태그의 내용까지 포함하고 불필요한 공백을 정리합니다."""

        if node is None:
            return ""
        return " ".join("".join(node.itertext()).split())

    def _abstract(self, article_node: ET.Element) -> str:
        """여러 구획으로 나뉜 초록을 라벨이 포함된 하나의 문자열로 합칩니다."""

        sections: list[str] = []
        for node in article_node.findall("Abstract/AbstractText"):
            text = self._text(node)
            if not text:
                continue
            label = (node.get("Label") or "").strip()
            sections.append(f"{label}: {text}" if label else text)
        return "\n".join(sections)

    def _journal(self, article_node: ET.Element) -> str:
        """저널 전체 이름을 우선 반환하고 없으면 ISO 약어를 사용합니다."""

        journal = article_node.find("Journal")
        if journal is None:
            return ""
        return self._text(journal.find("Title")) or self._text(
            journal.find("ISOAbbreviation")
        )

    def _publication_year(
        self,
        citation: ET.Element,
        article_node: ET.Element,
    ) -> int | None:
        """여러 PubMed 날짜 경로에서 출판연도를 찾아 정수로 반환합니다."""

        # PubMed 문서마다 출판일 위치가 달라 여러 경로를 우선순위대로 확인합니다.
        for path in ("Journal/JournalIssue/PubDate/Year", "ArticleDate/Year"):
            year = self._text(article_node.find(path))
            if year.isdigit():
                return int(year)

        medline_date = self._text(
            article_node.find("Journal/JournalIssue/PubDate/MedlineDate")
        )
        match = re.search(r"(?:18|19|20)\d{2}", medline_date)
        if match:
            return int(match.group())

        completed_year = self._text(citation.find("DateCompleted/Year"))
        return int(completed_year) if completed_year.isdigit() else None

    def _authors(self, article_node: ET.Element) -> str:
        """개인 저자와 단체 저자 이름을 쉼표로 구분된 문자열로 만듭니다."""

        names: list[str] = []
        for author in article_node.findall("AuthorList/Author"):
            collective_name = self._text(author.find("CollectiveName"))
            if collective_name:
                names.append(collective_name)
                continue

            given_name = self._text(author.find("ForeName")) or self._text(
                author.find("Initials")
            )
            last_name = self._text(author.find("LastName"))
            full_name = " ".join(part for part in (given_name, last_name) if part)
            if full_name:
                names.append(full_name)
        return ", ".join(names)


class PubMedClient:
    """PMID 검색과 논문 상세 정보 요청을 담당하는 API 클라이언트입니다."""

    def __init__(
        self,
        session: requests.Session | None = None,
        parser: PubMedXmlParser | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
    ) -> None:
        """HTTP 세션, XML 파서, API 주소와 요청 제한 시간을 설정합니다."""

        self.session = session or requests.Session()
        self.parser = parser or PubMedXmlParser()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search_pmids(self, conditions: SearchConditions) -> list[str]:
        """검색 조건에 맞는 PMID를 최신 출판일 순으로 가져옵니다."""

        params: dict[str, str | int] = {
            **self._common_params(),
            "db": "pubmed",
            "term": conditions.keyword,
            "datetype": "pdat",
            "mindate": str(conditions.start_year),
            "maxdate": str(conditions.end_year),
            "retmax": conditions.max_results,
            "retmode": "json",
            "sort": "pub date",
        }
        try:
            response = self.session.get(
                f"{self.base_url}/esearch.fcgi",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            return [str(pmid) for pmid in payload["esearchresult"]["idlist"]]
        except (requests.RequestException, KeyError, TypeError, ValueError) as error:
            raise PubMedApiError("PubMed 논문 ID 검색에 실패했습니다.") from error

    def fetch_articles(self, pmids: Iterable[str]) -> list[Article]:
        """PMID 목록에 해당하는 논문의 상세 메타데이터를 가져옵니다."""

        pmid_list = [str(pmid).strip() for pmid in pmids if str(pmid).strip()]
        if not pmid_list:
            return []

        params = {
            **self._common_params(),
            "db": "pubmed",
            "id": ",".join(pmid_list),
            "retmode": "xml",
        }
        try:
            response = self.session.get(
                f"{self.base_url}/efetch.fcgi",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self.parser.parse(response.content)
        except requests.RequestException as error:
            raise PubMedApiError("PubMed 논문 상세 정보 수집에 실패했습니다.") from error

    @staticmethod
    def _common_params() -> dict[str, str]:
        """NCBI 요청 식별 정보와 선택적 API 키를 구성합니다."""

        params = {"tool": os.getenv("NCBI_TOOL", "pubmed_metadata_collector")}
        email = os.getenv("NCBI_EMAIL", "").strip()
        api_key = os.getenv("NCBI_API_KEY", "").strip()
        if email:
            params["email"] = email
        if api_key:
            params["api_key"] = api_key
        return params
