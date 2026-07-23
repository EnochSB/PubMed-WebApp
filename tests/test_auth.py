"""Google OIDC 클레임을 내부 사용자로 변환하는 규칙 테스트."""

import unittest

from pubmed_app.auth import AuthenticatedUser, InvalidIdentityError


class AuthenticatedUserTest(unittest.TestCase):
    def test_google_subject_is_used_as_stable_user_key(self) -> None:
        user = AuthenticatedUser.from_claims(
            {
                "iss": "https://accounts.google.com",
                "sub": "google-user-123",
                "email": "researcher@example.com",
                "name": "연구자",
            }
        )

        self.assertEqual(
            user.user_id,
            "https://accounts.google.com|google-user-123",
        )
        self.assertEqual(user.display_name, "연구자")

    def test_missing_subject_is_rejected(self) -> None:
        with self.assertRaises(InvalidIdentityError):
            AuthenticatedUser.from_claims(
                {
                    "iss": "https://accounts.google.com",
                    "email": "researcher@example.com",
                }
            )


if __name__ == "__main__":
    unittest.main()
