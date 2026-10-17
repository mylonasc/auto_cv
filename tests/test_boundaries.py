"""Cross-layer regressions; strict xfails identify defects owned by later RFKs."""

import copy
import json
from pathlib import Path

import pytest


@pytest.fixture
def cv_payload():
    return {
        "candidate": {"candidate_id": "test", "full_name": "Test Candidate",
                      "profile": {"location": "Test City"}},
        "personal_statement": "Original statement",
        "alternative_statements": ["Alternative statement"],
        "experience_sections": [{
            "company": "OldCorp", "position": "Engineer", "duration": "2020-2024",
            "text_items": ["Developed Python software.", "Did admin work."],
        }],
        "cv_template": {"template_id": "default_cv",
                        "template_path": "assets/latex_cv_template_v0.tex"},
        "motivation_letter_template": {"template_id": "default_motivation_letter",
                                      "template_path": "assets/cover_letter/CoverLetter_Template.tex"},
    }


@pytest.mark.parametrize("path", ["/v1/cv-data/test", "/v1/cv-data/test/versions/master"])
def test_cv_read_round_trip_preserves_content_and_metadata(client, cv_payload, path):
    created = client.post("/v1/cv-data/test/versions/master", json=cv_payload)
    assert created.status_code == 200
    loaded = client.get(path)
    assert loaded.status_code == 200
    data = loaded.json()
    for key in ("personal_statement", "alternative_statements", "experience_sections",
                "cv_template", "motivation_letter_template"):
        if isinstance(cv_payload[key], dict):
            for name, value in cv_payload[key].items():
                assert data[key][name] == value
        else:
            assert data[key] == cv_payload[key]
    assert data["candidate"]["full_name"] == "Test Candidate"
    assert data["candidate"]["profile"] == {"location": "Test City"}
    assert client.put(path, json=data).status_code == 200
    assert client.get(path).json() == data


@pytest.mark.parametrize("path", ["/v1/cv-data/test", "/v1/cv-data/test/versions/master"])
@pytest.mark.parametrize("field", ["personal_statement", "alternative_statements", "experience_sections"])
def test_cv_editor_changes_survive_save(client, cv_payload, path, field):
    assert client.post("/v1/cv-data/test/versions/master", json=cv_payload).status_code == 200
    edited = client.get(path).json()
    if field == "personal_statement":
        edited[field] = "Edited statement"
    elif field == "alternative_statements":
        edited[field].append("New alternative")
    else:
        edited[field][0]["text_items"].append("New experience")
    expected = copy.deepcopy(edited[field])
    assert client.put(path, json=edited).status_code == 200
    assert client.get(path).json()[field] == expected


@pytest.fixture
def completed_job(client, cv_payload):
    from jobs.job_manager import job_manager

    assert client.post("/v1/cv-data/test/versions/master", json=cv_payload).status_code == 200
    response = client.post("/v1/cv-jobs/", json={
        "candidate": "test", "job_description": "TechCorp needs Python experience.",
        "config": {"outputs": {"render_pdf": False, "include_latex": False}},
    })
    assert response.status_code == 200
    job = job_manager.get_job(response.json()["id"])
    assert job.status == "succeeded", job.error
    return job


def stream_events(client, job):
    response = client.get(f"/v1/cv-jobs/{job.id}/stream")
    assert response.status_code == 200
    return dict((frame.splitlines()[0].removeprefix("event: "),
                 json.loads(frame.splitlines()[1].removeprefix("data: ")))
                for frame in response.text.strip().split("\n\n"))


@pytest.mark.parametrize("event", ["job_update", "job_complete"])
@pytest.mark.xfail(strict=True, raises=AssertionError, reason="RFK-03 #8: SSE must preserve HTTP job identity")
def test_sse_uses_the_http_job_identity(client, completed_job, event):
    http = client.get(f"/v1/cv-jobs/{completed_job.id}").json()
    assert stream_events(client, completed_job)[event].get("id") == http["id"]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="RFK-03 #8: SSE completion omits posting analysis")
def test_sse_completion_preserves_posting_analysis(client, completed_job):
    assert stream_events(client, completed_job)["job_complete"].get("job_analysis") == completed_job.job_analysis


def test_bullet_evidence_survives_http_and_working_copy(client, completed_job):
    result = client.get(f"/v1/cv-jobs/{completed_job.id}/result").json()
    assert result["sections"][0]["items"][0]["posting_evidence"] == "Python experience"
    wc = client.get(f"/v1/cv-jobs/{completed_job.id}/working-cv").json()
    assert wc["sections"][0]["items"][0]["posting_evidence"] == "Python experience"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="RFK-03 #8: SectionResult drops posting_evidence")
def test_section_evidence_survives_http_and_working_copy(client, completed_job):
    result = client.get(f"/v1/cv-jobs/{completed_job.id}/result").json()
    wc = client.get(f"/v1/cv-jobs/{completed_job.id}/working-cv").json()
    assert result["sections"][0].get("posting_evidence") == "Software delivery"
    assert wc["sections"][0]["section_posting_evidence"] == "Software delivery"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="RFK-04 #9: filtering discards analyzed content")
def test_working_copy_retains_deselected_bullets(client, completed_job):
    wc = client.get(f"/v1/cv-jobs/{completed_job.id}/working-cv").json()
    items = wc["sections"][0]["items"]
    assert {item["text"] for item in items} == {"Developed Python software.", "Did admin work."}
    assert next(item for item in items if "admin" in item["text"])["kept"] is False


@pytest.mark.parametrize("working_copy", [False, True])
def test_render_uses_explicitly_selected_source(client, completed_job, working_copy, pdf_calls):
    request = {"render_pdf": True, "include_latex": True}
    if working_copy:
        wc = client.get(f"/v1/cv-jobs/{completed_job.id}/working-cv").json()
        wc["personal_statement"] = "Edited working statement"
        wc["sections"][0]["items"][0]["text"] = "Edited working bullet"
        request["working_copy"] = wc
    response = client.post(f"/v1/cv-jobs/{completed_job.id}/render", json=request)
    assert response.status_code == 200
    artifacts = response.json()["result"]["artifacts"]
    latex = next(a for a in artifacts if a["kind"] == "latex")
    content = Path(latex["path"]).read_text()
    assert pdf_calls[-1].latex == content
    assert ("Edited working statement" in content) is working_copy
    assert ("Edited working bullet" in content) is working_copy
    assert ("Developed Python software." in content) is not working_copy
