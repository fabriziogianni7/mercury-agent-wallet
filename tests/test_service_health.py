from fastapi.testclient import TestClient
from mercury.config import MercurySettings
from mercury.service import create_app


def test_healthz_returns_process_health() -> None:
    app = create_app(settings=MercurySettings(app_name="Mercury Test"))
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Mercury Test"}


def test_readyz_uses_static_config_without_secret_fetches() -> None:
    app = create_app(settings=MercurySettings(app_name="Mercury Test", default_chain="base"))
    client = TestClient(app)

    response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["default_chain"] == "base"
    assert payload["supported_chains"] == [
        "ethereum",
        "base",
        "arbitrum",
        "optimism",
        "monad",
    ]
