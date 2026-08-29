import os

os.environ["DATABASE_URL"] = "sqlite:///./test_docpilot.db"

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_patient_record_flow():
    with TestClient(app) as client:
        patient = client.post(
            "/v1/patients",
            headers={"X-User-Role": "patient"},
            json={"full_name": "Arun Kumar", "date_of_birth": "1968-03-14", "sex": "male", "blood_group": "B+"},
        )
        assert patient.status_code == 201
        patient_id = patient.json()["id"]

        upload = client.post(
            f"/v1/patients/{patient_id}/records/upload",
            headers={"X-User-Role": "patient"},
            json={"filename": "report.pdf", "content_type": "application/pdf", "source_type": "lab_report"},
        )
        assert upload.status_code == 201
        assert upload.json()["record_id"]

        forbidden = client.get(
            f"/v1/patients/{patient_id}/clinical-summary",
            headers={"X-User-Role": "patient"},
        )
        assert forbidden.status_code == 403
