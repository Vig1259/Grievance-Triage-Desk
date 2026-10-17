import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app import config
config.DB_PATH = Path(tempfile.gettempdir()) / "grievance_test.sqlite3"
from app import main as main_module
app = main_module.app
from app.database import init_db, connection

@pytest.fixture
def client():
    init_db()
    with connection() as conn: conn.execute("DELETE FROM grievances")
    with TestClient(app) as c: yield c

def test_health(client):
    assert client.get("/health").json()["status"]=="ok"

def test_empty_and_out_of_scope_complaints_are_rejected(client):
    empty = client.post("/grievances", data={"text": "   "})
    assert empty.status_code == 400
    assert "Enter complaint text" in empty.json()["detail"]

    unrelated = client.post("/grievances", data={"text": "A pothole damaged my bicycle on the street."})
    assert unrelated.status_code == 400
    assert "consumer-finance complaints only" in unrelated.json()["detail"]

def test_financial_keywords_pass_scope_check(client):
    result = main_module.predict("My bank transaction was charged twice.", bundle={
        "model": type("Model", (), {
            "classes_": ["Checking or savings account", "Credit card", "Other"],
            "predict_proba": lambda self, _: [[0.7, 0.2, 0.1]],
        })(),
        "threshold": 0.55,
    })
    assert result["predicted_department"] == "Checking or savings account"

def test_staff_routes_require_authentication(client, monkeypatch):
    monkeypatch.setenv("STAFF_USERNAME", "worker")
    monkeypatch.setenv("STAFF_PASSWORD", "test-secret")
    assert client.get("/grievances").status_code == 401
    assert client.get("/stats").status_code == 401
    assert client.patch("/grievances/1", json={"status": "solved"}).status_code == 401

def test_staff_routes_fail_closed_without_config(client, monkeypatch):
    monkeypatch.delenv("STAFF_USERNAME", raising=False)
    monkeypatch.delenv("STAFF_PASSWORD", raising=False)
    monkeypatch.setattr(main_module, "ENV_FILE", Path(tempfile.gettempdir()) / "missing_staff_config.env")
    assert client.get("/stats", auth=("worker", "test-secret")).status_code == 503

def test_create_track_and_staff_update_if_model_exists(client, monkeypatch):
    if not config.MODEL_PATH.exists(): pytest.skip("Train model first.")
    monkeypatch.setenv("STAFF_USERNAME", "worker")
    monkeypatch.setenv("STAFF_PASSWORD", "test-secret")
    r=client.post("/grievances",data={"text":"My bank charged an overdraft fee I dispute."})
    assert r.status_code==200
    item=r.json()
    assert len(item["top3"])<=3
    assert item["status"] == "pending"
    code = item["tracking_code"]
    status_url = f"/grievances/{item['id']}/status"
    status_headers = {"X-Tracking-Code": code}
    assert client.get(status_url, headers=status_headers).json()["status"] == "pending"
    assert client.get(status_url, headers={"X-Tracking-Code": "x" * 32}).status_code == 404
    assert "tracking_token_hash" not in item

    response = client.patch(
        f"/grievances/{item['id']}",
        json={"department": "Banking", "status": "solved", "resolution_note": "Fee was refunded."},
        auth=("worker", "test-secret"),
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["original_prediction"]==item["original_prediction"]
    assert updated["corrected_department"]=="Banking"
    assert updated["status"] == "solved"
    assert updated["resolution_note"] == "Fee was refunded."
    assert client.get(status_url, headers=status_headers).json()["status"] == "solved"

    staff_list = client.get("/grievances", auth=("worker", "test-secret"))
    assert staff_list.status_code == 200 and len(staff_list.json()) == 1
    stats = client.get("/stats", auth=("worker", "test-secret"))
    assert stats.status_code == 200 and "needs_review_pct" in stats.json()
