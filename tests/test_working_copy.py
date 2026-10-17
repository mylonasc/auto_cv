"""Tests for the WorkingCopy system — models, helpers, and endpoints."""

import json
from pathlib import Path

import pytest

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
                RescoredItemResult(index=0, relevance_score=9.5, explanation="Good match", posting_evidence="All requirements", scored_text="Built feature"),
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

        from services.working_copy import create_working_copy

        wc = create_working_copy(FakeJob())

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

        from services.working_copy import create_working_copy

        wc = create_working_copy(FakeJob())
        assert wc.personal_statement == "Just a statement"
        assert len(wc.sections) == 0


class TestWorkingCopyDiskPersistence:
    def test_save_and_load(self, services):
        from models.api_models import WorkingCopy, WorkingCopySection, WorkingCopyItem

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

        services.working.save(wc)
        loaded = services.working.get("disk_test")

        assert loaded is not None
        assert loaded.job_id == "disk_test"
        assert loaded.personal_statement == "Disk test statement"
        assert len(loaded.sections) == 1
        assert loaded.sections[0].items[0].text == "Test item"

    def test_load_nonexistent(self, services):
        loaded = services.working.get("nonexistent_job")
        assert loaded is None


class TestRenderFromWorkingCopy:
    def test_render_uses_only_kept_content(self, pdf_calls, client, job_manager):
        from models.api_models import WorkingCopy, WorkingCopySection, WorkingCopyItem, RenderCVRequest
        from models.api_models import JobStatus
        job = job_manager.create_job()
        job_manager.update_job_status(job.id, JobStatus.SUCCEEDED, result={"sections": []})

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

        response = client.post(f"/v1/cv-jobs/{job.id}/render", json={"working_copy": wc.model_dump()})
        assert response.status_code == 200
        artifacts = response.json()["result"]["artifacts"]
        assert {artifact["kind"] for artifact in artifacts} == {"pdf", "latex"}
        latex = next(artifact for artifact in artifacts if artifact["kind"] == "latex")
        content = Path(latex["path"]).read_text()
        assert "Rendered statement" in content
        assert "RenderCorp" in content
        assert "Kept item" in content
        assert "Another kept" in content
        assert "Removed item" not in content
        assert "AllRemoved" not in content
        assert pdf_calls[0].latex == content
        assert all(artifact["source"] == "working_copy" for artifact in artifacts)


# ── Endpoint Tests ─────────────────────────────────────────────────────


class TestWorkingCopyEndpoints:
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
        assert response.status_code == 404

    def test_rescore_no_working_copy(self, client):
        payload = {"section_index": 0, "item_indices": [0]}
        response = client.post("/v1/cv-jobs/nonexistent/working-cv/rescore", json=payload)
        assert response.status_code == 404


# ── Artifact Source Tagging ──────────────────────────────────────────────


class TestArtifactSourceTagging:
    """Working copy renders tag artifacts with source='working_copy'."""

    @pytest.mark.parametrize("render_pdf,include_latex", [(True, False), (False, True), (True, True)])
    def test_actual_render_artifacts_survive_job_persistence(self, render_pdf, include_latex, client, job_manager):
        from jobs.job_manager import JobManager
        from models.api_models import WorkingCopy, RenderCVRequest, JobStatus

        job = job_manager.create_job()
        job_manager.update_job_status(job.id, JobStatus.SUCCEEDED, result={"sections": []})
        response = client.post(f"/v1/cv-jobs/{job.id}/render", json={
            "working_copy": WorkingCopy(job_id=job.id).model_dump(),
            "render_pdf": render_pdf, "include_latex": include_latex,
        })
        assert response.status_code == 200
        artifacts = response.json()["result"]["artifacts"]
        restored = JobManager(storage_dir=job_manager.storage_dir).get_job(job.id)
        assert restored.result.artifacts == artifacts
        assert {a["kind"] for a in artifacts} == (
            ({"pdf"} if render_pdf else set()) | ({"latex"} if include_latex else set())
        )
        for artifact in artifacts:
            assert artifact["source"] == "working_copy"
            assert Path(artifact["path"]).is_file()
