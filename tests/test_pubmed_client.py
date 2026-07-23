"""검색 조건 객체와 PubMed XML 파서 테스트입니다."""

import unittest

from models import SearchConditions
from pubmed_client import PubMedXmlParser


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
          <Title>Example Journal</Title>
        </Journal>
        <ArticleTitle>COVID-19 <i>vaccine</i> study</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">First section.</AbstractText>
          <AbstractText Label="RESULTS">Second section.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>Kim</LastName><ForeName>Min Su</ForeName></Author>
          <Author><CollectiveName>Study Group</CollectiveName></Author>
        </AuthorList>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""

MULTIPLE_PUBLICATION_DATES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>10000001</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
          <Title>Example Journal</Title>
        </Journal>
        <ArticleDate><Year>2021</Year><Month>09</Month><Day>02</Day></ArticleDate>
        <ArticleTitle>Online first article</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>10000002</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><MedlineDate>2020 Jan-Feb</MedlineDate></PubDate></JournalIssue>
          <Title>Another Journal</Title>
        </Journal>
        <ArticleDate><Year>2021</Year><Month>01</Month><Day>10</Day></ArticleDate>
        <ArticleTitle>Print first article</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


class SearchConditionsTest(unittest.TestCase):
    """PubMed 검색 조건의 입력값 검증 규칙을 테스트합니다."""

    def test_max_results_cannot_exceed_100(self) -> None:
        """최대 수집 논문 수가 100개를 초과하면 오류가 발생하는지 확인합니다."""

        with self.assertRaisesRegex(ValueError, "100개"):
            SearchConditions("vaccine", 2022, 2025, 101)

    def test_start_year_cannot_be_after_end_year(self) -> None:
        """검색 시작 연도가 끝 연도보다 늦을 때 오류가 발생하는지 확인합니다."""

        with self.assertRaisesRegex(ValueError, "끝 연도"):
            SearchConditions("vaccine", 2025, 2022, 10)


class PubMedXmlParserTest(unittest.TestCase):
    """PubMed XML에서 필수 논문 필드를 추출하는 동작을 테스트합니다."""

    def test_parse_required_fields(self) -> None:
        """PMID, 제목, 초록, 저널, 연도와 저자가 올바르게 파싱되는지 확인합니다."""

        article = PubMedXmlParser().parse(SAMPLE_XML)[0]

        self.assertEqual(article.pmid, "12345678")
        self.assertEqual(article.title, "COVID-19 vaccine study")
        self.assertIn("BACKGROUND: First section.", article.abstract)
        self.assertEqual(article.journal, "Example Journal")
        self.assertEqual(article.pub_year, 2024)
        self.assertEqual(article.authors, "Min Su Kim, Study Group")

    def test_uses_earlier_year_when_print_and_electronic_dates_differ(self) -> None:
        """인쇄일과 전자출판일 중 더 이른 연도가 저장되는지 확인합니다."""

        articles = PubMedXmlParser().parse(MULTIPLE_PUBLICATION_DATES_XML)

        self.assertEqual(articles[0].pub_year, 2021)
        self.assertEqual(articles[1].pub_year, 2020)


if __name__ == "__main__":
    unittest.main()
