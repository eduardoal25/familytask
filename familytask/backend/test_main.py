import os

if os.path.exists("./test.db"):
    os.remove("./test.db")

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("AI_TOKEN", "test-ai-token")

from fastapi.testclient import TestClient

from main import app


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_assistant_requires_bearer_token():
    with TestClient(app) as client:
        response = client.post("/api/assistant", params={"message": "Bonjour"})
        assert response.status_code == 401


def test_assistant_calls_github_models_with_token(monkeypatch):
    with TestClient(app) as client:
        signup = client.post(
            "/api/members/signup",
            json={
                "email": "assistant@fam.fr",
                "lien": "maman",
                "name": "Maman",
                "is_admin": False,
                "family_code": "famille-test",
                "password": "secret",
            },
        )
        assert signup.status_code == 201, signup.text
        token = signup.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        async def fake_post(self, url, headers=None, json=None):
            assert url == "https://models.github.ai/inference/chat/completions"
            assert headers["Authorization"] == "Bearer test-ai-token"
            assert headers["Content-Type"] == "application/json"
            assert json["model"] == "openai/gpt-4o-mini"
            assert json["messages"][-1]["content"] == "Bonjour"
            return DummyResponse({"choices": [{"message": {"content": "Salut !"}}]})

        monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

        response = client.post("/api/assistant", params={"message": "Bonjour"}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["reply"] == "Salut !"
