"""Tests for the CV Submissions tracking system."""

import os
import sys
import json
import uuid
from datetime import datetime

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server_application", "backend")))


class TestSubmissionModels:
    def test_submission_create_request(self):
        from models.api_models import SubmissionCreateRequest

        req = SubmissionCreateRequest(job_id="job_001", artifact_ids=["pdf_1"])
        assert req.job_id == "job_001"
        assert req.artifact_ids == ["pdf_1"]
        assert req.notes is None

    def test_submission_update_request(self):
        from models.api_models import SubmissionUpdateRequest

        req = SubmissionUpdateRequest(result="INTERVIEW", notes="Phone screen scheduled")
        assert req.result == "INTERVIEW"
        assert req.notes == "Phone screen scheduled"

    def test_submission_full(self):
        from models.api_models import Submission

        sub = Submission(
            id="sub_001",
            job_id="job_001",
            company="TechCorp",
            job_title="Senior Engineer",
            overall_score=8.5,
            submitted_at="2025-01-15T10:00:00",
            result="INTERVIEW",
            notes="Had a great chat",
            artifacts=[{"id": "pdf_1", "kind": "pdf", "filename": "cv.pdf"}],
            created_at="2025-01-15T10:00:00",
            updated_at="2025-01-15T10:00:00",
        )
        assert sub.company == "TechCorp"
        assert sub.overall_score == 8.5
        assert sub.result == "INTERVIEW"
        assert len(sub.artifacts) == 1
        assert sub.artifacts[0]["filename"] == "cv.pdf"

    def test_submission_roundtrip_json(self):
        from models.api_models import Submission

        sub = Submission(
            id="sub_002",
            job_id="job_002",
            company="Corp",
            job_title="Dev",
            overall_score=7.2,
            cv_snapshot={"personal_statement": "Test"},
            scoring_snapshot={"sections": []},
            artifacts=[{"id": "p1", "kind": "pdf", "filename": "out.pdf", "source": "working_copy"}],
            created_at="2025-02-01T00:00:00",
            updated_at="2025-02-01T00:00:00",
        )
        serialized = sub.model_dump_json()
        restored = Submission(**json.loads(serialized))
        assert restored.company == "Corp"
        assert restored.overall_score == 7.2
        assert restored.cv_snapshot["personal_statement"] == "Test"
        assert restored.artifacts[0]["source"] == "working_copy"


class TestSubmissionEndpoints:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Ensure clean submissions dir."""
        from core.paths import SUBMISSIONS_DIR, ensure_data_dirs
        ensure_data_dirs()
        # Clean up test submissions
        if os.path.exists(SUBMISSIONS_DIR):
            for f in os.listdir(SUBMISSIONS_DIR):
                if f.endswith(".json"):
                    os.remove(os.path.join(SUBMISSIONS_DIR, f))

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.submissions import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_create_submission_no_job(self, client):
        payload = {"job_id": "nonexistent"}
        response = client.post("/v1/submissions/", json=payload)
        assert response.status_code == 404

    def test_list_submissions_empty(self, client):
        response = client.get("/v1/submissions/")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_submission_not_found(self, client):
        response = client.get("/v1/submissions/nonexistent")
        assert response.status_code == 404

    def test_delete_submission_not_found(self, client):
        response = client.delete("/v1/submissions/nonexistent")
        assert response.status_code == 404

    def test_submission_crud_cycle(self, client):
        # Create a submission by directly saving one
        from models.api_models import Submission
        from core.paths import SUBMISSIONS_DIR

        sub = Submission(
            id="crud_test",
            job_id="job_test",
            company="TestCo",
            job_title="Tester",
            overall_score=9.0,
            result=None,
            artifacts=[],
            created_at="2025-03-01T00:00:00",
            updated_at="2025-03-01T00:00:00",
        )
        path = os.path.join(SUBMISSIONS_DIR, "crud_test.json")
        with open(path, "w") as f:
            json.dump(json.loads(sub.model_dump_json()), f)

        # List
        resp = client.get("/v1/submissions/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["company"] == "TestCo"

        # Get by ID
        resp = client.get("/v1/submissions/crud_test")
        assert resp.status_code == 200
        assert resp.json()["job_title"] == "Tester"

        # Update result
        resp = client.put("/v1/submissions/crud_test", json={"result": "OFFER"})
        assert resp.status_code == 200
        assert resp.json()["result"] == "OFFER"

        # Verify update persisted
        resp = client.get("/v1/submissions/crud_test")
        assert resp.json()["result"] == "OFFER"

        # Update notes
        resp = client.put("/v1/submissions/crud_test", json={"notes": "Accepted offer!"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Accepted offer!"

        # Delete
        resp = client.delete("/v1/submissions/crud_test")
        assert resp.status_code == 200

        # Verify gone
        resp = client.get("/v1/submissions/")
        assert resp.json() == []

    def test_update_nonexistent(self, client):
        resp = client.put("/v1/submissions/nonexistent", json={"result": "REJECTED"})
        assert resp.status_code == 404
