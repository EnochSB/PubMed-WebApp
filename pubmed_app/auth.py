"""Streamlit OIDC 인증과 메디톡톡 랜딩 화면."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st


class InvalidIdentityError(ValueError):
    """OIDC 공급자가 사용자 식별에 필요한 클레임을 주지 않았을 때 발생한다."""


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Google OIDC ID 토큰에서 앱이 사용하는 최소 사용자 정보."""

    user_id: str
    email: str
    display_name: str

    @classmethod
    def from_claims(cls, claims: Mapping[str, Any]) -> "AuthenticatedUser":
        issuer = str(claims.get("iss", "")).strip()
        subject = str(claims.get("sub", "")).strip()
        email = str(claims.get("email", "")).strip()
        display_name = str(claims.get("name", "")).strip() or email

        if not issuer or not subject or not email:
            raise InvalidIdentityError(
                "Google 계정에서 사용자 식별 정보를 확인할 수 없습니다."
            )

        # 이메일은 변경될 수 있으므로 발급자와 sub 조합을 영구 사용자 키로 사용한다.
        return cls(
            user_id=f"{issuer}|{subject}",
            email=email,
            display_name=display_name,
        )


def get_authenticated_user() -> AuthenticatedUser | None:
    """로그인하지 않은 세션에서는 None을 반환해 앱 기능 진입을 차단한다."""

    if not getattr(st.user, "is_logged_in", False):
        return None
    return AuthenticatedUser.from_claims(st.user.to_dict())


def render_landing_page() -> None:
    """비로그인 사용자에게만 메디톡톡 소개와 Google 로그인 버튼을 표시한다."""

    st.markdown(
        """
        <style>
        .meditoktok-hero {
            max-width: 760px;
            margin: 10vh auto 2rem auto;
            padding: 3.5rem 3rem;
            border: 1px solid rgba(49, 51, 63, 0.14);
            border-radius: 24px;
            background: linear-gradient(145deg, #f7fbff 0%, #eef7f5 100%);
            box-shadow: 0 18px 50px rgba(26, 71, 88, 0.10);
            text-align: center;
        }
        .meditoktok-eyebrow {
            color: #147d72;
            font-weight: 700;
            letter-spacing: 0.08em;
            margin-bottom: 0.6rem;
        }
        .meditoktok-title {
            color: #16343f;
            font-size: 3.4rem;
            font-weight: 800;
            margin: 0;
        }
        .meditoktok-description {
            color: #47636d;
            font-size: 1.15rem;
            line-height: 1.8;
            margin: 1.4rem auto 0 auto;
            max-width: 610px;
        }
        </style>
        <section class="meditoktok-hero">
            <div class="meditoktok-eyebrow">PUBMED RESEARCH ASSISTANT</div>
            <h1 class="meditoktok-title">메디톡톡</h1>
            <p class="meditoktok-description">
                메디톡톡은 논문을 수집하고, 수집한 논문 데이터를 안전하게 저장하며,
                저장된 논문 데이터를 분석해 연구 흐름을 더 쉽게 탐색하도록 돕습니다.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.2, 1])
    with center:
        if st.button(
            "Google로 로그인",
            type="primary",
            width="stretch",
            icon=":material/login:",
        ):
            try:
                st.login("google")
            except Exception:
                # 실제 비밀값은 코드에 넣지 않고 secrets.toml에서만 관리한다.
                st.error(
                    "Google OAuth 설정을 확인해 주세요. "
                    "`.streamlit/secrets.toml.example`을 참고할 수 있습니다."
                )
        st.caption("로그인한 사용자만 논문 수집·검색·분석·챗봇을 사용할 수 있습니다.")
