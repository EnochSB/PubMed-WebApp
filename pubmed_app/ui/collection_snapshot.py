"""수집 담당 모듈과 개요 화면 사이의 세션 연동 계약."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pubmed_app.domain.models import CollectionSnapshot


LAST_COLLECTION_NEW_COUNT_KEY = "last_collection_new_count"
LAST_COLLECTION_SKIPPED_COUNT_KEY = "last_collection_skipped_count"


def read_collection_snapshot(session_state: Mapping[str, Any]) -> CollectionSnapshot:
    """수집 모듈이 기록한 값을 읽으며 잘못된 값은 안전하게 0으로 처리한다."""

    return CollectionSnapshot(
        new_count=_to_non_negative_int(session_state.get(LAST_COLLECTION_NEW_COUNT_KEY, 0)),
        skipped_count=_to_non_negative_int(
            session_state.get(LAST_COLLECTION_SKIPPED_COUNT_KEY, 0)
        ),
    )


def _to_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
