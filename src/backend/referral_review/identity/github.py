"""GitHub-only OAuth Adapter. Tokens stay request-local; no email/repo scopes."""

from dataclasses import dataclass

from authlib.integrations.requests_client import OAuth2Session

from ..errors import ApiError
from ..schemas import ErrorCode

AUTHORIZE = "https://github.com/login/oauth/authorize"
TOKEN = "https://github.com/login/oauth/access_token"
PROFILE = "https://api.github.com/user"
ISSUER = "https://github.com/login/oauth"


@dataclass(frozen=True)
class GitHubIdentity:
    subject: str
    display_name: str


class GitHubOAuth:
    def __init__(self, settings, *, http_adapter=None):
        self.settings = settings
        self.http_adapter = http_adapter  # Test transport, never runtime environment configuration.

    def _client(self, state):
        client = OAuth2Session(
            self.settings.github_client_id,
            self.settings.github_client_secret.get_secret_value(),
            redirect_uri=self.settings.github_callback_url, state=state,
            scope="", code_challenge_method="S256",
            token_endpoint_auth_method="client_secret_post",
        )
        client.trust_env = False  # No ambient proxy or netrc credentials.
        if self.http_adapter is not None:
            client.mount("https://", self.http_adapter)
        return client

    def authorization_url(self, state: str, verifier: str) -> str:
        with self._client(state) as client:
            url, _ = client.create_authorization_url(
                AUTHORIZE, state=state, code_verifier=verifier, allow_signup="false")
            return url

    def identify(self, *, state: str, verifier: str, authorization_response: str) -> GitHubIdentity:
        try:
            with self._client(state) as client:
                token = client.fetch_token(
                    TOKEN, authorization_response=authorization_response, code_verifier=verifier,
                    headers={"Accept": "application/json"}, timeout=(5, 10), allow_redirects=False,
                )
                if not token.get("access_token") or str(token.get("token_type", "")).lower() != "bearer":
                    raise ValueError("Invalid bearer token")
                response = client.get(PROFILE, headers={"Accept": "application/vnd.github+json"},
                                      timeout=(5, 10), allow_redirects=False)
                if response.status_code != 200 or len(response.content) > 64 * 1024:
                    raise ValueError("Invalid profile response")
                data = response.json()
                subject = data.get("id")
                if type(subject) is not int or subject <= 0:
                    raise ValueError("Stable numeric subject required")
                name = data.get("name") or data.get("login")
                if not isinstance(name, str) or not name.strip():
                    raise ValueError("Display name required")
                return GitHubIdentity(str(subject), name.strip()[:200])
        except Exception:
            # Provider errors may include token/body/client secrets: never log/echo repr.
            raise ApiError(ErrorCode.OAUTH_FAILED) from None
