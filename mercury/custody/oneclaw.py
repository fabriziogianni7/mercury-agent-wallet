"""1Claw secret-store abstractions for non-wallet Mercury secrets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mercury.custody.errors import (
    EmptySecretValueError,
    SecretNotFoundError,
    SecretStoreUnavailableError,
)


@dataclass(frozen=True, repr=False)
class SecretValue:
    """Typed secret value whose raw string is only available by explicit reveal."""

    path: str
    _value: str

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("Secret path must not be empty.")
        if not self._value.strip():
            raise EmptySecretValueError(self.path)

    def reveal(self) -> str:
        """Return the raw secret value for the narrow caller that needs it."""

        return self._value

    def __repr__(self) -> str:
        return f"SecretValue(path={self.path!r}, value=<redacted>)"


@runtime_checkable
class SecretStore(Protocol):
    """Path-based secret store interface."""

    def get_secret(self, path: str) -> SecretValue:
        """Resolve a secret path into a typed secret value."""


@runtime_checkable
class OneClawClient(Protocol):
    """Minimal 1Claw client shape used by the secret-store wrapper."""

    def get_secret(self, *, vault_id: str, path: str, agent_id: str | None = None) -> str:
        """Return the raw secret string for a path."""


class OneClawSecretStore:
    """SecretStore implementation backed by a 1Claw client."""

    def __init__(
        self,
        *,
        client: OneClawClient,
        vault_id: str,
        agent_id: str | None = None,
    ) -> None:
        if not vault_id.strip():
            raise ValueError("1Claw vault ID must not be empty.")

        self._client = client
        self._vault_id = vault_id
        self._agent_id = agent_id

    def get_secret(self, path: str) -> SecretValue:
        """Resolve a non-wallet secret path through 1Claw."""

        if not path.strip():
            raise ValueError("Secret path must not be empty.")

        try:
            value = self._client.get_secret(
                vault_id=self._vault_id,
                path=path,
                agent_id=self._agent_id,
            )
        except SecretNotFoundError:
            raise
        except EmptySecretValueError:
            raise
        except Exception as exc:
            raise SecretStoreUnavailableError(path, store_name="1Claw") from exc

        if value is None:
            raise SecretNotFoundError(path)

        return SecretValue(path=path, _value=value)


class OneClawHttpClient:
    """Small stdlib HTTP adapter for 1Claw-compatible secret reads."""

    def __init__(self, *, base_url: str, api_key: str) -> None:
        if not base_url.strip():
            raise ValueError("1Claw base URL must not be empty.")
        if not api_key.strip():
            raise ValueError("1Claw API key must not be empty.")

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def get_secret(self, *, vault_id: str, path: str, agent_id: str | None = None) -> str:
        """Read a secret value from 1Claw without exposing it in errors."""

        url = f"{self._base_url}/v1/vaults/{vault_id}/secrets:resolve"
        payload: dict[str, str] = {"path": path}
        if agent_id is not None:
            payload["agent_id"] = agent_id

        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=10) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise SecretNotFoundError(path) from exc
            raise SecretStoreUnavailableError(path, store_name="1Claw") from exc
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise SecretStoreUnavailableError(path, store_name="1Claw") from exc

        value = _extract_secret_value(response_payload)
        if value is None:
            raise SecretNotFoundError(path)
        return value


class FakeSecretStore:
    """In-memory SecretStore for tests."""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = dict(secrets or {})

    def get_secret(self, path: str) -> SecretValue:
        try:
            value = self._secrets[path]
        except KeyError as exc:
            raise SecretNotFoundError(path) from exc

        return SecretValue(path=path, _value=value)


class FakeOneClawClient:
    """In-memory 1ClawClient for wrapper tests."""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = dict(secrets or {})
        self.requests: list[dict[str, str | None]] = []

    def get_secret(self, *, vault_id: str, path: str, agent_id: str | None = None) -> str:
        self.requests.append({"vault_id": vault_id, "path": path, "agent_id": agent_id})
        try:
            return self._secrets[path]
        except KeyError as exc:
            raise SecretNotFoundError(path) from exc


def _extract_secret_value(payload: dict[str, Any]) -> str | None:
    value = payload.get("value")
    if isinstance(value, str):
        return value

    secret = payload.get("secret")
    if isinstance(secret, dict):
        nested_value = secret.get("value")
        if isinstance(nested_value, str):
            return nested_value

    return None
