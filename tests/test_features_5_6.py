import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from pubmed_app.chatbot import ConversationMemory, LiteratureChatbot
from pubmed_app.paper_search import PaperCsvExporter, PaperFilter, PaperSearchRepository


class FeatureFiveSixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.execute(
                "CREATE TABLE papers (pmid TEXT PRIMARY KEY, title TEXT, abstract TEXT, "
                "journal TEXT, pub_year INTEGER, authors TEXT)"
            )
            connection.executemany(
                "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?)",
                [
                    ("1", "COVID-19 vaccine study", "A", "Nature", 2024, "Kim"),
                    ("2", "Cancer research", "B", "Cell", 2022, "Lee"),
                ],
            )
            connection.commit()
        self.repository = PaperSearchRepository(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_filters_and_csv(self) -> None:
        papers = self.repository.search(
            PaperFilter(title="vaccine", start_year=2023, end_year=2025, journal="Nature")
        )
        self.assertEqual(["1"], papers["pmid"].tolist())
        self.assertTrue(PaperCsvExporter.export(papers).startswith(b"\xef\xbb\xbf"))

    def test_chatbot_remembers_previous_keyword(self) -> None:
        memory = ConversationMemory()
        chatbot = LiteratureChatbot(self.repository, memory)
        first = chatbot.reply("COVID-19 vaccine 논문 찾아줘")
        follow_up = chatbot.reply("더 보여줘")
        self.assertIn("COVID-19 vaccine study", first)
        self.assertIn("COVID-19 vaccine study", follow_up)
        self.assertEqual(4, len(memory.messages))


if __name__ == "__main__":
    unittest.main()
