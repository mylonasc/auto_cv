"""Serializable, immutable analysis and pure selection/metric policies."""

from math import fsum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Assessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    experience_relevance_score: float = Field(ge=0, le=10)
    explanation: str
    posting_evidence: str


class AnalyzedBullet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    text: str
    assessment: Assessment | None = None


class AnalyzedRole(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    company: str
    position: str
    duration: str
    items: tuple[AnalyzedBullet, ...]
    assessment: Assessment | None = None


class AnalysisSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    roles: tuple[AnalyzedRole, ...]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [id for role in self.roles for id in (role.id, *(item.id for item in role.items))]
        if len(ids) != len(set(ids)):
            raise ValueError("Analysis role and bullet IDs must be unique")
        return self


class SelectionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    min_items: int = Field(default=1, ge=0)
    max_items: int = Field(default=6, ge=0)
    min_score: float = Field(default=3, ge=0, le=10)

    @model_validator(mode="after")
    def valid_limits(self):
        if self.min_items > self.max_items:
            raise ValueError("min_items cannot exceed max_items")
        return self


def select_bullets(items: tuple[AnalyzedBullet, ...], policy: SelectionPolicy) -> frozenset[str]:
    return select_scored_ids(tuple((item.id, item.assessment.experience_relevance_score
                                    if item.assessment else None) for item in items), policy)


def select_scored_ids(items: tuple[tuple[str, float | None], ...], policy: SelectionPolicy) -> frozenset[str]:
    """Stable ties preserve source order; missing assessments rank as zero."""
    ranked = sorted(items, key=lambda item: -(item[1] or 0))
    selected = []
    for id, raw_score in ranked:
        score = raw_score or 0
        if len(selected) < policy.min_items or (len(selected) < policy.max_items and score >= policy.min_score):
            selected.append(id)
    return frozenset(selected)


def aggregate_metrics(snapshot: AnalysisSnapshot, selected: frozenset[str] | None = None) -> dict[str, float | None]:
    """Weight original role scores by selected content, never by render comments.

    Scores describe the analyzed source, not a new LLM assessment of edited text.
    Empty/unscored selections have no metric (null), not a fabricated zero/NaN.
    """
    scores, weights = [], []
    for role in snapshot.roles:
        items = [item for item in role.items if selected is None or item.id in selected]
        if not items or role.assessment is None:
            continue
        content = " ".join([role.company, role.position, role.duration, *(item.text for item in items)])
        scores.append(role.assessment.experience_relevance_score)
        weights.append(max(1, len(content.split())))
    if not scores:
        return {"mean_section_relevance": None, "weighted_mean_section_relevance": None,
                "conciseness_relevance_metric": None}
    mean = fsum(scores) / len(scores)
    weighted = fsum(score * weight for score, weight in zip(scores, weights)) / sum(weights)
    return {"mean_section_relevance": mean, "weighted_mean_section_relevance": weighted,
            "conciseness_relevance_metric": weighted - mean}


def score_comment(score, explanation, evidence):
    """Plain-text annotation; rendering escapes it, never modifies analysis."""
    if score is None:
        return None
    return f"Source relevance {score}/10: {explanation or ''}. Evidence: {evidence or ''}"
