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
            assert json["tools"][0]["function"]["name"] == "ajouter_tache"
            return DummyResponse({"choices": [{"message": {"content": "Salut !"}}]})

        monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

        response = client.post("/api/assistant", params={"message": "Bonjour"}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["reply"] == "Salut !"


def test_assistant_executes_tool_call(monkeypatch):
    with TestClient(app) as client:
        signup = client.post(
            "/api/members/signup",
            json={
                "email": "assistant-tool@fam.fr",
                "lien": "papa",
                "name": "Papa",
                "is_admin": False,
                "family_code": "famille-test-2",
                "password": "secret",
            },
        )
        assert signup.status_code == 201, signup.text
        token = signup.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        async def fake_post(self, url, headers=None, json=None):
            if json and json.get("tools"):
                return DummyResponse({
                    "choices": [{
                        "message": {
                            "tool_calls": [{
                                "id": "call_1",
                                "function": {
                                    "name": "ajouter_tache",
                                    "arguments": '{"titre": "Faire les courses", "personne": "Papa"}'
                                }
                            }]
                        }
                    }]
                })

            return DummyResponse({"choices": [{"message": {"content": "Tâche ajoutée"}}]})

        monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

        response = client.post("/api/assistant", params={"message": "Ajoute une tâche"}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["reply"].startswith("Tâche ajoutée pour Papa")
        tasks = client.get("/api/tasks", headers=headers)
        assert tasks.status_code == 200
        assert any(task["title"] == "Faire les courses" for task in tasks.json())


def test_assistant_asks_for_clarification_on_ambiguous_link():
    with TestClient(app) as client:
        family = "famille-ambigu"
        client.post(
            "/api/members/signup",
            json={
                "email": "lea@fam.fr",
                "lien": "fille",
                "name": "Léa",
                "is_admin": False,
                "family_code": family,
                "password": "secret",
            },
        )
        client.post(
            "/api/members/signup",
            json={
                "email": "emma@fam.fr",
                "lien": "fille",
                "name": "Emma",
                "is_admin": False,
                "family_code": family,
                "password": "secret",
            },
        )

        login = client.post("/api/members/login", params={"email": "lea@fam.fr", "password": "secret"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/api/assistant", params={"message": "Ajoute une tâche pour ma fille"}, headers=headers)
        assert response.status_code == 200
        assert "Il y a plusieurs filles (Léa, Emma). Pour qui ?" in response.json()["reply"]
