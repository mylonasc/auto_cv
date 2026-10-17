import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.analysis import (Assessment, AnalyzedBullet, AnalyzedRole, AnalysisSnapshot,
                          SelectionPolicy, select_bullets, aggregate_metrics)
from src.utils import DocSection, DocSectionItem, FullCVDocument, JobPostAnalysis
from src.utils_cross_analysis import CVCrossAnalyzer


def bullet(id, score):
    return AnalyzedBullet(id=id, text=f"Text {id}", assessment=None if score is None else Assessment(
        experience_relevance_score=score, explanation="Explanation", posting_evidence="Evidence"))


@pytest.mark.parametrize("scores,policy,expected", [
    ([8, 8, 2], SelectionPolicy(max_items=1), {"0"}),
    ([None, 0, 9], SelectionPolicy(min_items=0, min_score=5), {"2"}),
    ([None, 0], SelectionPolicy(min_items=1, min_score=5), {"0"}),
    ([9, 8], SelectionPolicy(min_items=0, max_items=0), set()),
    ([], SelectionPolicy(), set()),
])
def test_selection_boundaries_and_stable_ties(scores, policy, expected):
    items = tuple(bullet(str(index), score) for index, score in enumerate(scores))
    original = tuple(item.model_dump_json() for item in items)
    assert select_bullets(items, policy) == expected
    assert tuple(item.model_dump_json() for item in items) == original


@pytest.mark.parametrize("policy", [{"min_items": -1}, {"min_items": 3, "max_items": 2}, {"min_score": 11}])
def test_invalid_selection_policies_fail_explicitly(policy):
    with pytest.raises(ValidationError):
        SelectionPolicy(**policy)


def test_metrics_handle_empty_and_unscored_content_without_nan():
    assert all(value is None for value in aggregate_metrics(AnalysisSnapshot(roles=())).values())
    role = AnalyzedRole(id="role", company="Example", position="Engineer", duration="2020", items=(bullet("a", 8),))
    snapshot = AnalysisSnapshot(roles=(role,))
    assert aggregate_metrics(snapshot)["weighted_mean_section_relevance"] is None
    scored = role.model_copy(update={"assessment": Assessment(experience_relevance_score=8,
                                                             explanation="Role", posting_evidence="Evidence")})
    snapshot = AnalysisSnapshot(roles=(scored,))
    assert aggregate_metrics(snapshot)["weighted_mean_section_relevance"] == 8
    assert aggregate_metrics(snapshot, frozenset())["weighted_mean_section_relevance"] is None


def test_duplicate_snapshot_ids_are_rejected():
    role = AnalyzedRole(id="role", company="Example", position="Engineer", duration="2020",
                        items=(bullet("same", 8), bullet("same", 2)))
    with pytest.raises(ValidationError, match="unique"):
        AnalysisSnapshot(roles=(role,))


def test_metrics_weight_selected_plain_content_only():
    roles = tuple(AnalyzedRole(
        id=f"role-{index}", company="A", position="P", duration="X",
        items=(AnalyzedBullet(id=f"bullet-{index}", text=text),),
        assessment=Assessment(experience_relevance_score=score, explanation="Role", posting_evidence="Evidence"),
    ) for index, (text, score) in enumerate((("one", 2), ("two words", 8))))
    snapshot = AnalysisSnapshot(roles=roles)
    metrics = aggregate_metrics(snapshot)
    assert metrics["mean_section_relevance"] == 5
    assert metrics["weighted_mean_section_relevance"] == pytest.approx(48 / 9)
    assert aggregate_metrics(snapshot, frozenset({"bullet-0"}))["weighted_mean_section_relevance"] == 2


@pytest.mark.asyncio
async def test_analysis_is_frozen_serializable_and_independent_of_document_identity(tmp_path, fake_model):
    posting = tmp_path / "post.txt"
    posting.write_text("Python engineer")
    source_role = DocSectionItem("Example", "2020", "Engineer", ["Python work", "Did admin work"])
    source = FullCVDocument("Statement", DocSection("Experience", [source_role]))
    source_json = [role.to_dict() for role in source.experience_section.doc_section_items]
    jpa = JobPostAnalysis(str(posting), llm_model=fake_model)
    await jpa.analyze()
    analyzer = CVCrossAnalyzer(jpa, source, llm_model=fake_model)
    snapshot = await analyzer.analyze_job_experience_section()
    assert source_json == [role.to_dict() for role in source.experience_section.doc_section_items]
    assert source_role.comment is None
    assert all(item.comment is None for item in source_role.section_item_list)
    assert AnalysisSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert json.loads(json.dumps(analyzer.data))["experience_section_analysis"]["roles"][0]["id"] == source_role.id
    with pytest.raises(ValidationError):
        snapshot.roles[0].items[0].text = "Mutation"
    analyzer.rewrite_reviewed_experience_section(min_relevance_score=5)
    assert len(snapshot.roles[0].items) == 2
    assert len(source_role.section_item_list) == 2
    assert len(analyzer.cv_model.experience_section.doc_section_items[0].section_item_list) == 1
    assert analyzer.cv_model.experience_section.doc_section_items[0].id == source_role.id
    assert snapshot.roles[0].items[0].id == analyzer.cv_model.experience_section.doc_section_items[0].section_item_list[0].id
    before = aggregate_metrics(snapshot)
    annotated = analyzer.render_document(True)
    assert r'\pdfcomment' not in annotated.make_latex()
    assert r'\pdfcomment' in annotated.make_latex(include_scoring_comments=True)
    assert aggregate_metrics(snapshot) == before
    assert snapshot.model_dump_json() == analyzer.snapshot.model_dump_json()


def test_document_copy_and_json_preserve_ids_comments_and_parent_links(tmp_path):
    role = DocSectionItem("Example", "2020", "Engineer", ["Same text", "Same text"])
    role.set_comment("Role & evidence")
    role.section_item_list[0].set_comment("Bullet_score 8%")
    document = FullCVDocument("Statement", DocSection("Experience", [role]))
    copied = document.copy()
    copied_role = copied.experience_section.doc_section_items[0]
    assert copied_role.id == role.id
    assert copied_role.comment == role.comment
    assert copied_role.section_item_list[0].comment == role.section_item_list[0].comment
    assert copied_role.section_item_list[0].parent is copied_role
    assert copied_role.section_item_list[0].id != copied_role.section_item_list[1].id
    assert r'Bullet\_score 8\%' in copied.make_latex(include_scoring_comments=True)
    assert r'\pdfcomment' not in copied.make_latex()
    path = tmp_path / "document.json"
    document.to_json(str(path))
    restored = FullCVDocument.from_json(str(path))
    assert restored.experience_section.doc_section_items[0].to_dict() == role.to_dict()


def test_legacy_working_copy_ids_are_stable_without_rewriting(services, isolated_runtime):
    path = isolated_runtime / "working_cvs" / "legacy.json"
    original = json.dumps({"job_id": "legacy", "sections": [{"items": [
        {"text": "Same", "relevance_score": 8}, {"text": "Same", "relevance_score": 8},
    ]}]}).encode()
    path.write_bytes(original)
    first = services.working.get("legacy").model_dump()
    second = services.working.get("legacy").model_dump()
    assert first == second
    assert first["sections"][0]["items"][0]["id"] != first["sections"][0]["items"][1]["id"]
    assert first["sections"][0]["items"][0]["scored_text"] is None
    assert path.read_bytes() == original


def test_rescore_records_the_exact_scored_text_and_preserves_identity(client, job_manager, services):
    from models.api_models import WorkingCopy, WorkingCopySection, WorkingCopyItem, JobStatus

    job = job_manager.create_job()
    job_manager.update_job_status(job.id, JobStatus.SUCCEEDED, result={"sections": []})
    item = WorkingCopyItem(text="Original", original_text="Original", scored_text="Original", relevance_score=8)
    wc = WorkingCopy(job_id=job.id, sections=[WorkingCopySection(items=[item])])
    services.working.save(wc)
    response = client.post(f"/v1/cv-jobs/{job.id}/working-cv/rescore", json={
        "section_index": 0, "item_indices": [0], "items": [{"index": 0, "text": "Edited Python work"}],
    })
    assert response.status_code == 200
    assert response.json()["items"][0]["scored_text"] == "Edited Python work"
    restored = client.get(f"/v1/cv-jobs/{job.id}/working-cv").json()["sections"][0]["items"][0]
    assert restored["id"] == item.id
    assert restored["text"] == restored["scored_text"] == "Edited Python work"
    assert restored["original_text"] == "Original"


def test_working_copy_comment_options_do_not_publish_stale_bullet_scores(client, pdf_calls, job_manager):
    from models.api_models import WorkingCopy, WorkingCopySection, WorkingCopyItem, JobStatus

    job = job_manager.create_job()
    job_manager.update_job_status(job.id, JobStatus.SUCCEEDED, result={"sections": []})
    wc = WorkingCopy(job_id=job.id, sections=[WorkingCopySection(items=[
        WorkingCopyItem(text="Edited", scored_text="Original", relevance_score=8, explanation="Stale evidence"),
        WorkingCopyItem(text="Current", scored_text="Current", relevance_score=9, explanation="Current evidence"),
    ])])
    response = client.post(f"/v1/cv-jobs/{job.id}/render", json={
        "working_copy": wc.model_dump(), "include_scoring_comments": True,
    })
    assert response.status_code == 200
    content = pdf_calls[-1].latex
    assert r'\pdfcomment' in content
    assert 'Current evidence' in content
    assert 'Stale evidence' not in content
