"""Pure conversion/render adapters: no storage paths or process-global stores."""

from datetime import datetime

from models.api_models import WorkingCopy
from models.legacy import normalize_working_copy
from src.analysis import SelectionPolicy, select_scored_ids, score_comment
from src.domain import CVTemplateData
from src.template_registry import resolve_template_path
from src.utils import FullCVDocument, DocSection, DocSectionItem


def create_working_copy(job):
    data = job.result.model_dump()
    now = datetime.now().isoformat()
    sections = []
    for section in data["sections"]:
        value = {
            "company": section.get("company") or "", "position": section.get("position") or "",
            "duration": section.get("duration") or "", "section_score": section.get("section_score"),
            "section_explanation": section.get("explanation"),
            "section_posting_evidence": section.get("posting_evidence"), "items": [],
        }
        if section.get("id"):
            value["id"] = section["id"]
        for item in section["items"]:
            bullet = {"text": item["text"], "original_text": item["text"],
                      "scored_text": item["text"] if item.get("relevance_score") is not None else None,
                      "relevance_score": item.get("relevance_score"), "explanation": item.get("explanation"),
                      "posting_evidence": item.get("posting_evidence"), "kept": item.get("kept", True)}
            if item.get("id"):
                bullet["id"] = item["id"]
            value["items"].append(bullet)
        sections.append(value)
    return WorkingCopy.model_validate(normalize_working_copy({
        "job_id": job.id, "personal_statement": data.get("personal_statement") or "", "sections": sections,
        "created_at": now, "updated_at": now,
    }))


def select_working_copy(job, request):
    copy = create_working_copy(job)
    policy = SelectionPolicy(min_items=request.min_section_items_keep,
                             max_items=request.max_section_items_keep, min_score=request.min_relevance_score)
    for section in copy.sections:
        selected = select_scored_ids(tuple((item.id, item.relevance_score) for item in section.items), policy)
        for item in section.items:
            item.kept = item.id in selected
    return copy


def document_from_working_copy(copy, request, section_title="Work Experience"):
    roles = []
    for section in copy.sections:
        kept = [item for item in section.items if item.kept]
        if not kept:
            continue
        role = DocSectionItem(section.company, section.duration, section.position, [item.text for item in kept],
                              id=section.id, item_ids=[item.id for item in kept])
        if request.include_scoring_comments:
            role.set_comment(score_comment(section.section_score, section.section_explanation, section.section_posting_evidence))
            for point, item in zip(role.section_item_list, kept):
                if item.scored_text == item.text:
                    point.set_comment(score_comment(item.relevance_score, item.explanation, item.posting_evidence))
        roles.append(role)
    template = CVTemplateData(template_id=request.cv_template_id,
                              template_path=resolve_template_path("cv_templates", request.cv_template_id, request.cv_template_path),
                              experience_section_title=section_title)
    return FullCVDocument(copy.personal_statement, DocSection(section_title, roles), cv_template=template)
