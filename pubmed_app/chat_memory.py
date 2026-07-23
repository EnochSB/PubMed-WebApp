"""로그인 사용자별 챗봇 대화를 영구 저장하는 SQLite 저장소."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


VALID_CHAT_ROLES = {"user", "assistant"}


class ChatMemoryError(RuntimeError):
    """SQLite 대화 메모리를 읽거나 저장하지 못했을 때 발생한다."""


@dataclass(frozen=True, slots=True)
class StoredChatMessage:
    """SQLite에서 읽어 온 한 건의 챗봇 메시지."""

    role: str
    content: str


class SQLiteConversationStore:
    """사용자와 대화 ID를 기준으로 메시지 및 검색 상태를 저장한다."""

    def __init__(self, db_path: str | Path) -> None:
        """SQLite 파일 경로를 설정하고 필요한 테이블을 준비한다."""

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        """대화 메시지·상태 테이블과 조회 인덱스를 생성한다."""

        try:
            with closing(self._connect()) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        conversation_id TEXT NOT NULL,
                        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (
                            strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                        )
                    );

                    CREATE INDEX IF NOT EXISTS idx_chat_messages_scope
                    ON chat_messages (user_id, conversation_id, id);

                    CREATE TABLE IF NOT EXISTS chat_states (
                        user_id TEXT NOT NULL,
                        conversation_id TEXT NOT NULL,
                        last_keyword TEXT NOT NULL DEFAULT '',
                        updated_at TEXT NOT NULL DEFAULT (
                            strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                        ),
                        PRIMARY KEY (user_id, conversation_id)
                    );
                    """
                )
                connection.commit()
        except sqlite3.Error as error:
            raise ChatMemoryError("챗봇 대화 DB를 초기화할 수 없습니다.") from error

    def list_messages(
        self,
        user_id: str,
        conversation_id: str,
    ) -> list[StoredChatMessage]:
        """특정 사용자의 대화 메시지를 입력 순서대로 반환한다."""

        self._validate_scope(user_id, conversation_id)
        try:
            with closing(self._connect()) as connection:
                with closing(
                    connection.execute(
                        """
                        SELECT role, content
                        FROM chat_messages
                        WHERE user_id = ? AND conversation_id = ?
                        ORDER BY id
                        """,
                        (user_id, conversation_id),
                    )
                ) as cursor:
                    rows = cursor.fetchall()
        except sqlite3.Error as error:
            raise ChatMemoryError("이전 챗봇 대화를 불러올 수 없습니다.") from error
        return [StoredChatMessage(str(row[0]), str(row[1])) for row in rows]

    def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
    ) -> None:
        """사용자 또는 어시스턴트 메시지 한 건을 대화에 추가한다."""

        self._validate_scope(user_id, conversation_id)
        if role not in VALID_CHAT_ROLES:
            raise ValueError("챗봇 메시지 역할은 user 또는 assistant여야 합니다.")
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO chat_messages
                        (user_id, conversation_id, role, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, conversation_id, role, content),
                )
                connection.commit()
        except sqlite3.Error as error:
            raise ChatMemoryError("챗봇 대화를 저장할 수 없습니다.") from error

    def get_last_keyword(self, user_id: str, conversation_id: str) -> str:
        """사용자의 직전 논문 검색어를 반환하며 없으면 빈 문자열을 반환한다."""

        self._validate_scope(user_id, conversation_id)
        try:
            with closing(self._connect()) as connection:
                with closing(
                    connection.execute(
                        """
                        SELECT last_keyword
                        FROM chat_states
                        WHERE user_id = ? AND conversation_id = ?
                        """,
                        (user_id, conversation_id),
                    )
                ) as cursor:
                    row = cursor.fetchone()
        except sqlite3.Error as error:
            raise ChatMemoryError("챗봇 검색 상태를 불러올 수 없습니다.") from error
        return str(row[0]) if row else ""

    def set_last_keyword(
        self,
        user_id: str,
        conversation_id: str,
        keyword: str,
    ) -> None:
        """사용자의 직전 논문 검색어를 추가하거나 갱신한다."""

        self._validate_scope(user_id, conversation_id)
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    INSERT INTO chat_states
                        (user_id, conversation_id, last_keyword)
                    VALUES (?, ?, ?)
                    ON CONFLICT (user_id, conversation_id) DO UPDATE SET
                        last_keyword = excluded.last_keyword,
                        updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    """,
                    (user_id, conversation_id, keyword),
                )
                connection.commit()
        except sqlite3.Error as error:
            raise ChatMemoryError("챗봇 검색 상태를 저장할 수 없습니다.") from error

    def clear_conversation(self, user_id: str, conversation_id: str) -> None:
        """현재 사용자의 선택된 대화와 검색 상태만 삭제한다."""

        self._validate_scope(user_id, conversation_id)
        try:
            with closing(self._connect()) as connection:
                connection.execute(
                    """
                    DELETE FROM chat_messages
                    WHERE user_id = ? AND conversation_id = ?
                    """,
                    (user_id, conversation_id),
                )
                connection.execute(
                    """
                    DELETE FROM chat_states
                    WHERE user_id = ? AND conversation_id = ?
                    """,
                    (user_id, conversation_id),
                )
                connection.commit()
        except sqlite3.Error as error:
            raise ChatMemoryError("챗봇 대화를 삭제할 수 없습니다.") from error

    def _connect(self) -> sqlite3.Connection:
        """동시 요청을 잠시 대기하도록 설정한 새 SQLite 연결을 반환한다."""

        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @staticmethod
    def _validate_scope(user_id: str, conversation_id: str) -> None:
        """빈 사용자 ID나 대화 ID가 저장소 네임스페이스로 사용되지 않게 한다."""

        if not user_id.strip():
            raise ValueError("챗봇 메모리에 사용할 사용자 ID가 필요합니다.")
        if not conversation_id.strip():
            raise ValueError("챗봇 메모리에 사용할 대화 ID가 필요합니다.")
