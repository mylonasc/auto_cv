"""Entry-point parity and dependency selection for the shared application stages."""

import json
from pathlib import Path
import runpy

import pytest

from src.config import BackendConfig, ModelConfig
from src.domain import CVData, CandidateMetadata, ExperienceSectionData
from src.pipeline import analyze_cv
from tests.fakes import StructuredModel


@pytest.fixture
def source():
    return CVData(candidate=CandidateMetadata(candidate_id="test"), personal_statement="Statement",
                  alternative_statements=["Alternative"], experience_sections=[ExperienceSectionData(
                      company="Example", position="Engineer", duration="2020",
                      text_items=["Python delivery", "Did admin work"],
                  )])


@pytest.mark.asyncio
async def test_shared_pipeline_injects_models_by_role_and_does_not_mutate_source(source):
    config = BackendConfig(analysis_model=ModelConfig(provider="google", model="analysis-test", config={"temperature": 0.1}),
                           statement_editor_model=ModelConfig(model="editor-test"))
    built = []

    def builder(selection):
        model = StructuredModel()
        built.append((selection.model_dump(), model))
        return model

    before = source.model_dump_json()
    run = await analyze_cv(source, "Python engineer", config, model_builder=builder)
    assert [selection["model"] for selection, _ in built] == ["analysis-test", "editor-test"]
    assert built[0][0]["provider"] == "google"
    assert built[0][0]["config"] == {"temperature": 0.1}
    assert {name for name, _ in built[0][1].calls} == {
        "BasicAnalysis", "IndustryPositionAnalysis", "BulletAnalysis", "SectionAnalysis",
    }
    assert [name for name, _ in built[1][1].calls] == ["PersonalStatementRewrite"]
    assert run.analyzer.cv_model.statement == "Experienced Python engineer."
    assert len(run.analyzer.snapshot.roles[0].items) == 2
    assert len(run.analyzer.selected_ids) == 1
    assert source.model_dump_json() == before


def test_http_default_config_and_rescore_use_saved_effective_model(client, source, monkeypatch, fake_model):
    from src.models import ModelFactory

    built = []

    def model(factory):
        built.append((factory._model_provider, factory._model_str, factory._config))
        return fake_model

    monkeypatch.setattr(ModelFactory, "get_llm_model", model)
    config = BackendConfig(analysis_model=ModelConfig(provider="google", model="analysis-A", config={"temperature": 0}),
                           statement_editor_model=ModelConfig(model="editor-A"))
    config.outputs.render_pdf = False
    config.outputs.include_latex = False
    assert client.put("/v1/config/", json=config.model_dump()).status_code == 200
    assert client.post("/v1/cv-data/test/versions/master", json=source.model_dump()).status_code == 200
    created = client.post("/v1/cv-jobs/", json={"candidate": "test", "job_description": "Python engineer"}).json()
    job = client.get(f"/v1/cv-jobs/{created['id']}").json()
    assert job["status"] == "succeeded"
    assert job["effective_config"] == config.model_dump()
    assert built[:2] == [("google", "analysis-A", {"temperature": 0}), ("ollama", "editor-A", None)]
    changed = BackendConfig(analysis_model=ModelConfig(model="different-server-default"))
    assert client.put("/v1/config/", json=changed.model_dump()).status_code == 200
    rescored = client.post(f"/v1/cv-jobs/{job['id']}/working-cv/rescore", json={"section_index": 0, "item_indices": [0]})
    assert rescored.status_code == 200
    assert built[-1] == ("google", "analysis-A", {"temperature": 0})


@pytest.mark.asyncio
async def test_cli_and_http_use_identical_analysis_selection_and_latex(client, tmp_path, source):
    from tools.autocv import _make_parser, run_pipeline, config_from_args
    from src.cv_storage import save_cv_file

    input = tmp_path / "input.json"
    posting = tmp_path / "posting.txt"
    save_cv_file(input, source)
    posting.write_text("Python engineer")
    output = tmp_path / "cli-output"
    args = _make_parser().parse_args(["--candidate-json", str(input), "--candidate-id", "test",
                                      "--job-posting", str(posting), "--output-dir", str(output), "--skip-cover-letter"])
    config = config_from_args(args)
    assert client.post("/v1/cv-data/test/versions/master", json=source.model_dump()).status_code == 200
    job = client.post("/v1/cv-jobs/", json={"candidate": "test", "job_description": posting.read_text(),
                                             "config": config.model_dump()}).json()
    result = client.get(f"/v1/cv-jobs/{job['id']}/result").json()
    await run_pipeline(args)
    api_latex = Path(next(a for a in result["artifacts"] if a["kind"] == "latex")["path"]).read_text()
    cli_latex = (output / "latex_folder/cv_edited_with_comments.tex").read_text()
    assert cli_latex == api_latex
    assert json.loads((output / "metrics_summary.txt").read_text()) == result["summary_metrics"]
    assert json.loads((output / "effective_config.json").read_text()) == config.model_dump()


@pytest.mark.asyncio
async def test_cli_refuses_to_replace_existing_user_output(tmp_path):
    from tools.autocv import _make_parser, run_pipeline

    directory = tmp_path / "valuable-output"
    directory.mkdir()
    sentinel = directory / "keep.txt"
    sentinel.write_text("user output")
    args = _make_parser().parse_args(["--candidate-json", "not-read.json", "--job-posting", "not-read.txt",
                                      "--output-dir", str(directory), "--skip-cover-letter"])
    with pytest.raises(FileExistsError, match="fresh directory"):
        await run_pipeline(args)
    assert sentinel.read_text() == "user output"


@pytest.mark.asyncio
async def test_cli_only_cover_letter_uses_its_configured_model(tmp_path, source, monkeypatch, fake_model, pdf_calls):
    from tools.autocv import _make_parser, run_pipeline
    from src.cv_storage import save_cv_file
    from src.models import ModelFactory

    built = []

    def model(factory):
        built.append(factory._model_str)
        return fake_model

    monkeypatch.setattr(ModelFactory, "get_llm_model", model)
    input = tmp_path / "input.json"
    posting = tmp_path / "post.txt"
    save_cv_file(input, source)
    posting.write_text("Python engineer")
    output = tmp_path / "cover-output"
    args = _make_parser().parse_args(["--candidate-json", str(input), "--candidate-id", "test",
                                      "--job-posting", str(posting), "--output-dir", str(output),
                                      "--cover-letter-model", "letter-test"])
    await run_pipeline(args)
    assert built[-1] == "letter-test"
    assert "CoverLetter" in [name for name, _ in fake_model.calls]
    assert (output / "cover_letter_tmp.pdf").is_file()
    assert "Python delivery experience" in (output / "cover_letter_tmp.tex").read_text()
    assert len(pdf_calls) == 4


def test_http_rejects_cli_only_outputs_instead_of_silently_ignoring_them(client):
    config = BackendConfig()
    config.outputs.include_cover_letter = True
    response = client.post("/v1/cv-jobs/", json={"job_description": "Python", "config": config.model_dump()})
    assert response.status_code == 422
    assert "CLI-only" in response.json()["detail"]
    assert client.get("/v1/cv-jobs/").json() == []


def test_persisted_effective_configuration_excludes_credentials():
    from jobs.job_manager import job_manager

    config = BackendConfig(analysis_model=ModelConfig(config={
        "API_KEY": "request-secret", "temperature": 0.1,
        "nested": {"authorization": "bearer-secret", "max_tokens": 100},
    }))
    job = job_manager.create_job(effective_config=config)
    assert job.effective_config.analysis_model.config == {
        "temperature": 0.1, "nested": {"max_tokens": 100},
    }
    assert config.analysis_model.config["API_KEY"] == "request-secret"
    saved = (Path(job_manager.storage_dir) / f"{job.id}.json").read_text()
    assert "request-secret" not in saved
    assert "bearer-secret" not in saved


@pytest.mark.parametrize("fails", [False, True])
def test_telemetry_wraps_the_cli_and_always_flushes_without_import_time_exporters(fails):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tools/autocv-otel.py"))
    calls = []

    class Provider:
        def force_flush(self): calls.append("flush")
        def shutdown(self): calls.append("shutdown")

    def cli():
        calls.append("cli")
        if fails:
            raise RuntimeError("CLI failure")

    module["main"].__globals__.update(initialize_tracing=lambda: Provider(), cli_main=cli)
    if fails:
        with pytest.raises(RuntimeError, match="CLI failure"):
            module["main"]()
    else:
        module["main"]()
    assert calls == ["cli", "flush", "shutdown"]
