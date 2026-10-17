"""Shared application stages; HTTP, CLI and telemetry are adapters, not pipelines."""

from dataclasses import dataclass

from .config import BackendConfig, build_model
from .domain import CVData
from .template_registry import resolve_cv_templates
from .utils import JobPostAnalysis, FullCVDocument, DocSection, DocSectionItem
from .utils_cross_analysis import CVCrossAnalyzer, BulletAnalysis, section_experience_analysis_prompt
from langchain_core.prompts import ChatPromptTemplate


@dataclass(frozen=True)
class CVRun:
    source: CVData
    config: BackendConfig
    job: JobPostAnalysis
    analyzer: CVCrossAnalyzer


async def analyze_posting(text: str, config: BackendConfig, *, model=None):
    analyzer = JobPostAnalysis(post_text=text, llm_model=model if model is not None else build_model(config.analysis_model))
    await analyzer.analyze()
    return analyzer


async def analyze_cv(source: CVData, text: str, config: BackendConfig | None = None, *,
                     model_builder=build_model, progress_callback=None, cache=None) -> CVRun:
    config = (config or BackendConfig()).model_copy(deep=True)

    async def progress(message):
        if progress_callback:
            await progress_callback(message)

    await progress("Analyzing job posting...")
    analysis_model = model_builder(config.analysis_model)
    posting = await analyze_posting(text, config, model=analysis_model)
    source = resolve_cv_templates(source)
    document = FullCVDocument(source.personal_statement, DocSection(source.cv_template.experience_section_title, [
        DocSectionItem(**section.model_dump()) for section in source.experience_sections
    ]), cv_template=source.cv_template)
    editor_model = model_builder(config.statement_editor_model) if source.alternative_statements else analysis_model
    analyzer = CVCrossAnalyzer(posting, document, llm_model=analysis_model, llm_editor_model=editor_model, cache=cache)
    if source.alternative_statements:
        await progress("Optimizing personal statement...")
        await analyzer.analyze_rewrite_personal_statement(source.alternative_statements + [source.personal_statement])
        analyzer.cv_model.statement = analyzer.data['edited_statement']
    await progress("Analyzing complete CV experience...")
    await analyzer.analyze_job_experience_section(config.concurrency_limit, progress_callback)
    policy = config.rewrite_policy
    analyzer.rewrite_reviewed_experience_section(policy.min_section_items_keep,
                                                policy.max_section_items_keep, policy.min_relevance_score)
    return CVRun(source=source, config=config, job=posting, analyzer=analyzer)


def bullet_scoring_chain(config: BackendConfig, *, model_builder=build_model):
    """Rescoring uses the same analysis model role and prompt as initial analysis."""
    return (ChatPromptTemplate.from_template(section_experience_analysis_prompt)
            | model_builder(config.analysis_model).with_structured_output(BulletAnalysis))
