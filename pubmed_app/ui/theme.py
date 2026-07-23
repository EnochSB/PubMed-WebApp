"""Soft Glass Research 전역 디자인을 로드하는 UI 도우미."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


SOFT_GLASS_STYLESHEET = (
    Path(__file__).resolve().parents[2] / "assets" / "soft_glass.css"
)


def apply_soft_glass_theme() -> None:
    """별도 CSS 파일을 로드해 모든 페이지에 동일한 Glass 테마를 적용한다."""

    st.html(SOFT_GLASS_STYLESHEET)

