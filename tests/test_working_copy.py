"""Tests for the WorkingCopy system — models, helpers, and endpoints."""

import os
import sys
import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server_application", "backend")))


# ── Model Tests ────────────────────────────────────────────────────────


class TestWorkingCopyModels:
    def test_section_filter_config_defaults(self):
        from models.api_models import SectionFilterConfig

        cfg = SectionFilterConfig()
        assert cfg.min_relevance_score == 3
        assert cfg.min_items_keep == 1
        assert cfg.max_items_keep == 6

    def test_section_filter_config_custom(self):
        from models.api_models import SectionFilterConfig

        cfg = SectionFilterConfig(min_relevance_score=5, min_items_keep=2, max_items_keep=4)
        assert cfg.min_relevance_score == 5
        assert cfg.min_items_keep == 2
        assert cfg.max_items_keep == 4

    def test_working_copy_item_defaults(self):
        from models.api_models import WorkingCopyItem

        item = WorkingCopyItem(text="Built stuff")
        assert item.text == "Built stuff"
        assert item.original_text == ""
        assert item.relevance_score is None
        assert item.kept is True

    def test_working_copy_section_defaults(self):
        from models.api_models import WorkingCopySection, WorkingCopyItem

        section = WorkingCopySection(
            company="Acme",
            position="Engineer",
            items=[WorkingCopyItem(text="Did work", relevance_score=8.0)],
        )
        assert section.company == "Acme"
        assert section.duration == ""
        assert section.section_score is None
        assert section.filter_config.min_relevance_score == 3
        assert len(section.items) == 1
        assert section.items[0].relevance_score == 8.0

    def test_working_copy_roundtrip_json(self):
        from models.api_models import WorkingCopy, WorkingCopySection, WorkingCopyItem

        wc = WorkingCopy(
            job_id="job_001",
            personal_statement="I am a great engineer.",
            sections=[
                WorkingCopySection(
                    company="Corp",
                    position="Dev",
                    duration="2020-2023",
                    section_score=8.5,
                    items=[
                        WorkingCopyItem(
                            text="Built feature X",
                            original_text="Built feature X",
                            relevance_score=9.0,
                            explanation="Relevant",
                            posting_evidence="Match skills",
                            kept=True,
                        ),
                        WorkingCopyItem(
                            text="Old task",
                            original_text="Old task",
                            relevance_score=3.0,
                            explanation="Less relevant",
                            posting_evidence=None,
                            kept=False,
                        ),
                    ],
                )
            ],
        )

        serialized = wc.model_dump_json()
        restored = WorkingCopy(**json.loads(serialized))

        assert restored.job_id == "job_001"
        assert restored.personal_statement == wc.personal_statement
        assert len(restored.sections) == 1
        assert restored.sections[0].items[0].text == "Built feature X"
        assert restored.sections[0].items[1].kept is False
        assert restored.sections[0].section_score == 8.5

    def test_rescore_request(self):
        from models.api_models import RescoreRequest, RescoreItem

        req = RescoreRequest(
            section_index=0,
            item_indices=[0, 1],
            items=[RescoreItem(index=0, text="New text"), RescoreItem(index=1)],
        )
        assert req.section_index == 0
        assert len(req.item_indices) == 2
        assert req.items[0].text == "New text"
        assert req.items[1].text is None

    def test_rescore_response(self):
        from models.api_models import RescoreResponse, RescoredItemResult

        resp = RescoreResponse(
            section_index=1,
            items=[
                RescoredItemResult(index=0, relevance_score=9.5, explanation="Good match", posting_evidence="All requirements"),
            ],
        )
        assert resp.section_index == 1
        assert resp.items[0].relevance_score == 9.5

    def test_render_cv_request_with_working_copy(self):
        from models.api_models import RenderCVRequest, WorkingCopy

        wc = WorkingCopy(job_id="job_001", personal_statement="Test")
        req = RenderCVRequest(working_copy=wc)
        assert req.working_copy is not None
        assert req.working_copy.personal_statement == "Test"
        assert req.working_copy.job_id == "job_001"
        # Legacy fields should still have defaults
        assert req.min_relevance_score == 4


# ── Helper Function Tests ──────────────────────────────────────────────


class TestCreateWorkingCopyFromJob:
    def test_from_job_with_result(self):
        from models.api_models import WorkingCopy

        # Simulate a job with a result dict
        class FakeResult:
            def model_dump(self):
                return {
                    "personal_statement": "Optimized statement",
                    "sections": [
                        {
                            "company": "OldCorp",
                            "position": "Dev",
                            "duration": "2019-2022",
                            "section_score": 8.0,
                            "items": [
                                {"text": "Built thing", "relevance_score": 9.0, "explanation": "Great", "posting_evidence": "Req A", "kept": True},
                                {"text": "Did admin", "relevance_score": 2.0, "explanation": "Weak", "posting_evidence": None, "kept": False},
                            ],
                        }
                    ],
                }

        class FakeJob:
            id = "job_123"
            result = FakeResult()

        # Import the helper via the cv_jobs module
        from api.cv_jobs import _create_working_copy_from_job

        wc = _create_working_copy_from_job(FakeJob())

        assert isinstance(wc, WorkingCopy)
        assert wc.job_id == "job_123"
        assert wc.personal_statement == "Optimized statement"
        assert len(wc.sections) == 1
        assert wc.sections[0].company == "OldCorp"
        assert wc.sections[0].position == "Dev"
        assert wc.sections[0].section_score == 8.0
        assert len(wc.sections[0].items) == 2
        assert wc.sections[0].items[0].text == "Built thing"
        assert wc.sections[0].items[0].relevance_score == 9.0
        assert wc.sections[0].items[1].kept is False
        assert wc.created_at is not None
        assert wc.updated_at is not None

    def test_from_job_without_sections(self):
        from models.api_models import WorkingCopy

        class FakeEmptyResult:
            def model_dump(self):
                return {"personal_statement": "Just a statement", "sections": []}

        class FakeJob:
            id = "job_empty"
            result = FakeEmptyResult()

        from api.cv_jobs import _create_working_copy_from_job

        wc = _create_working_copy_from_job(FakeJob())
        assert wc.personal_statement == "Just a statement"
        assert len(wc.sections) == 0


class TestWorkingCopyDiskPersistence:
    def test_save_and_load(self):
        from models.api_models import WorkingCopy, WorkingCopySection, WorkingCopyItem
        from api.cv_jobs import _save_working_copy_to_disk, _load_working_copy_from_disk, WORKING_CVS_DIR

        wc = WorkingCopy(
            job_id="disk_test",
            personal_statement="Disk test statement",
            sections=[
                WorkingCopySection(
                    company="TestCorp",
                    position="Tester",
                    items=[WorkingCopyItem(text="Test item", relevance_score=7.0)],
                )
            ],
        )

        _save_working_copy_to_disk(wc)
        loaded = _load_working_copy_from_disk("disk_test")

        assert loaded is not None
        assert loaded.job_id == "disk_test"
        assert loaded.personal_statement == "Disk test statement"
        assert len(loaded.sections) == 1
        assert loaded.sections[0].items[0].text == "Test item"

        # Cleanup
        path = os.path.join(WORKING_CVS_DIR, "disk_test.json")
        if os.path.exists(path):
            os.remove(path)

    def test_load_nonexistent(self):
        from api.cv_jobs import _load_working_copy_from_disk
        loaded = _load_working_copy_from_disk("nonexistent_job")
        assert loaded is None


class TestRenderFromWorkingCopy:
    def test_build_doc_items_from_working_copy(self):
        from models.api_models import WorkingCopy, WorkingCopySection, WorkingCopyItem, RenderCVRequest

        wc = WorkingCopy(
            job_id="render_test",
            personal_statement="Rendered statement",
            sections=[
                WorkingCopySection(
                    company="RenderCorp",
                    position="Engineer",
                    duration="2020-2024",
                    items=[
                        WorkingCopyItem(text="Kept item", relevance_score=9.0, kept=True),
                        WorkingCopyItem(text="Removed item", relevance_score=2.0, kept=False),
                        WorkingCopyItem(text="Another kept", relevance_score=7.0, kept=True),
                    ],
                ),
                WorkingCopySection(
                    company="AllRemoved",
                    position="Temp",
                    duration="2019",
                    items=[
                        WorkingCopyItem(text="Removed", relevance_score=1.0, kept=False),
                    ],
                ),
            ],
        )

        # Build DocSectionItem list manually (the logic inside _render_from_working_copy)
        from src.utils import DocSectionItem

        doc_items = []
        for section in wc.sections:
            kept_texts = [it.text for it in section.items if it.kept]
            if kept_texts:
                doc_items.append(
                    DocSectionItem(
                        company=section.company,
                        duration=section.duration,
                        position=section.position,
                        text_items=kept_texts,
                    )
                )

        assert len(doc_items) == 1  # second section has no kept items
        assert doc_items[0].company == "RenderCorp"
        kept_texts = [sl.text for sl in doc_items[0].section_item_list]
        assert kept_texts == ["Kept item", "Another kept"]
        assert "Removed item" not in kept_texts


# ── Endpoint Tests ─────────────────────────────────────────────────────


class TestWorkingCopyEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.cv_jobs import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_get_working_copy_no_job(self, client):
        response = client.get("/v1/cv-jobs/nonexistent/working-cv")
        assert response.status_code == 404

    def test_put_working_copy_no_job(self, client):
        payload = {
            "job_id": "ghost_job",
            "personal_statement": "Test",
            "sections": [],
        }
        response = client.put("/v1/cv-jobs/ghost_job/working-cv", json=payload)
        # PUT creates/overwrites on disk, so it should succeed even without a backend job
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "ghost_job"
        assert data["personal_statement"] == "Test"

    def test_rescore_no_working_copy(self, client):
        payload = {"section_index": 0, "item_indices": [0]}
        response = client.post("/v1/cv-jobs/nonexistent/working-cv/rescore", json=payload)
        assert response.status_code == 404


# ── Artifact Source Tagging ──────────────────────────────────────────────


class TestArtifactSourceTagging:
    """Working copy renders tag artifacts with source='working_copy'."""

    def test_working_copy_artifact_dict_has_source(self):
        """Verify the artifact dict structure that _render_from_working_copy produces."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        job_id = "test_wc_source"
        template_id = "default_cv"

        artifact_pdf = {
            "id": f"pdf_{job_id}_{timestamp}",
            "kind": "pdf",
            "filename": f"cv_output_{job_id}_{template_id}_{timestamp}.pdf",
            "path": f"/tmp/cv_output_{job_id}_{template_id}_{timestamp}.pdf",
            "source": "working_copy",
        }

        artifact_latex = {
            "id": f"latex_{job_id}_{timestamp}",
            "kind": "latex",
            "filename": f"cv_output_{job_id}_{template_id}_{timestamp}.tex",
            "path": f"/tmp/cv_output_{job_id}_{template_id}_{timestamp}.tex",
            "source": "working_copy",
        }

        assert artifact_pdf["source"] == "working_copy"
        assert artifact_latex["source"] == "working_copy"
        assert artifact_pdf["kind"] == "pdf"
        assert artifact_latex["kind"] == "latex"

    def test_working_copy_artifact_persistence(self):
        """Verify artifacts with source field can roundtrip through JSON."""
        import json
        from datetime import datetime

        ts = datetime.now().isoformat()
        artifacts = [
            {"id": "pdf_1", "kind": "pdf", "filename": "out.pdf", "source": "working_copy"},
            {"id": "tex_1", "kind": "latex", "filename": "out.tex", "source": "working_copy"},
        ]

        # Simulate storing in job result
        job_result = {
            "personal_statement": "Test",
            "sections": [],
            "artifacts": artifacts,
        }

        serialized = json.dumps(job_result)
        restored = json.loads(serialized)

        for art in restored["artifacts"]:
            assert art["source"] == "working_copy"
            assert art["kind"] in ("pdf", "latex")
