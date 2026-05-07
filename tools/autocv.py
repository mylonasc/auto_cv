"""Run AutoCV pipeline from CLI inputs.

Example:
  python tools/autocv.py \
    --candidate-json data/cv_section_data/charilaos_mylonas/master.json \
    --job-posting job_postings_text/Google_GNNs_Apr30-2026.txt
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.domain import candidate_bundle_from_legacy
from src.models import ModelFactory
from src.utils import JobPostAnalysis, FullCVDocument, CoverLetterModel, DocSectionItem, DocSection
from src.utils_cross_analysis import CVCrossAnalyzer, CoverLetterDrafter


def _log(*parts: object) -> None:
    """ log.

    Returns:
        TODO: describe return value.
    """
    print(*parts)


def _log_agg_metrics(agg_metrics, txt_suff: str) -> None:
    """ log agg metrics.

    Args:
        agg_metrics: TODO: describe.
        txt_suff: TODO: describe.

    Returns:
        TODO: describe return value.
    """
    _log(f" - ({txt_suff}) Weighted Mean Section Relevance:", agg_metrics[0]["weighted_mean_section_relevance"])
    _log(f" - ({txt_suff}) Mean Section Relevance:", agg_metrics[0]["mean_section_relevance"])
    _log(f" - ({txt_suff}) Conciseness Relevance Metric:", agg_metrics[0]["conciseness_relevance_metric"])
    _log(f" - ({txt_suff}) Section Scores:\n", agg_metrics[1])


def _load_json(path: str) -> dict:
    """ load json.

    Args:
        path: TODO: describe.

    Returns:
        TODO: describe return value.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_parser() -> argparse.ArgumentParser:
    """ make parser.

    Returns:
        TODO: describe return value.
    """
    parser = argparse.ArgumentParser(description="Generate CV and cover letter for a job posting.")
    parser.add_argument("--candidate-json", required=True, help="Path to candidate CV json (legacy or new structure).")
    parser.add_argument("--job-posting", required=True, help="Path to job posting text file.")
    parser.add_argument("--output-dir", default=None, help="Output directory. Defaults to autocv_output_<job-file-stem>.")

    parser.add_argument("--candidate-id", default="charilaos_mylonas", help="Candidate identifier.")
    parser.add_argument("--candidate-name", default="Charilaos Mylonas", help="Candidate display name for cover letter.")
    parser.add_argument("--company-name", default="Company", help="Target company name used in cover letter template.")
    parser.add_argument("--prof-signature", default="\\\\Machine Learning Engineer \\\\ Zurich", help="Cover letter professional signature.")

    parser.add_argument("--cv-template", default=None, help="CV latex template path (overrides template ID).")
    parser.add_argument("--cv-template-id", default="default_cv", help="CV template identifier from config/templates.json.")
    parser.add_argument("--motivation-template", default=None, help="Motivation letter template path (overrides template ID).")
    parser.add_argument("--motivation-template-id", default="default_motivation_letter", help="Motivation template identifier from config/templates.json.")

    parser.add_argument("--analysis-provider", default="google", choices=["google", "ollama"], help="Analysis model provider.")
    parser.add_argument("--analysis-model", default="gemini-3.1-pro-preview", help="Analysis model name.")
    parser.add_argument("--authoring-provider", default="google", choices=["google", "ollama"], help="Statement editor provider.")
    parser.add_argument("--authoring-model", default="gemini-3.1-pro-preview", help="Statement editor model name.")
    parser.add_argument("--cover-letter-provider", default="google", choices=["google", "ollama"], help="Cover letter model provider.")
    parser.add_argument("--cover-letter-model", default="gemini-3.1-pro-preview", help="Cover letter model name.")

    parser.add_argument("--max-section-items-keep", type=int, default=5)
    parser.add_argument("--min-relevance-score-keep", type=int, default=7)
    parser.add_argument("--min-section-items-keep", type=int, default=1)

    parser.add_argument("--skip-cover-letter", action="store_true", help="Skip cover letter generation.")
    return parser


async def run_pipeline(args: argparse.Namespace) -> str:
    """Run pipeline.

    Args:
        args: TODO: describe.

    Returns:
        TODO: describe return value.
    """
    candidate_payload = _load_json(args.candidate_json)
    bundle = candidate_bundle_from_legacy(
        candidate_payload,
        candidate_id=args.candidate_id,
        cv_template_id=args.cv_template_id,
        cv_template_path=args.cv_template,
        motivation_template_id=args.motivation_template_id,
        motivation_template_path=args.motivation_template,
    )

    output_dir = args.output_dir
    if not output_dir:
        output_dir = f"autocv_output_{Path(args.job_posting).stem}"

    tmp_dir = tempfile.mkdtemp(prefix="autocv_")
    _log(f"- using temp folder: {tmp_dir}")
    _log(f"- loaded {len(bundle.candidate.alternative_statements)} personal statements.")
    _log(f"- loaded {len(bundle.candidate.experience_sections)} professional experiences.")

    analysis_model = ModelFactory(
        model_provider=args.analysis_provider,
        model_str=args.analysis_model,
    ).get_llm_model()
    authoring_model = ModelFactory(
        model_provider=args.authoring_provider,
        model_str=args.authoring_model,
    ).get_llm_model()
    cover_letter_model = ModelFactory(
        model_provider=args.cover_letter_provider,
        model_str=args.cover_letter_model,
    ).get_llm_model()

    jpa = JobPostAnalysis(args.job_posting, llm_model=analysis_model)
    await jpa.analyze()

    doc_section_items = [DocSectionItem(**item.model_dump()) for item in bundle.candidate.experience_sections]
    doc_section = DocSection(bundle.cv_template.experience_section_title, doc_section_items)
    fcv = FullCVDocument(bundle.candidate.personal_statement, doc_section.copy(), cv_template=bundle.cv_template)

    cvca = CVCrossAnalyzer(
        jpa,
        fcv,
        llm_model=analysis_model,
        llm_editor_model=authoring_model,
    )

    if bundle.candidate.alternative_statements:
        await cvca.analyze_rewrite_personal_statement(bundle.candidate.alternative_statements)
        rewritten_statement = cvca.data.get("edited_statement") or bundle.candidate.personal_statement
    else:
        rewritten_statement = bundle.candidate.personal_statement

    fcv = FullCVDocument(rewritten_statement, doc_section.copy(), cv_template=bundle.cv_template)
    cvca = CVCrossAnalyzer(
        jpa,
        fcv,
        llm_model=analysis_model,
        llm_editor_model=authoring_model,
    )

    await cvca.analyze_job_experience_section()
    metrics_prev = cvca.get_section_aggregate_metrics()
    _log_agg_metrics(metrics_prev, "prev")

    cvca.rewrite_reviewed_experience_section(
        max_section_items_keep=args.max_section_items_keep,
        min_relevance_score=args.min_relevance_score_keep,
        min_section_items_keep=args.min_section_items_keep,
    )

    metrics_post = cvca.get_section_aggregate_metrics()
    _log_agg_metrics(metrics_post, "after edits")

    if not args.skip_cover_letter:
        clm = CoverLetterModel(motivation_template=bundle.motivation_letter_template)
        cld = CoverLetterDrafter(cvca, cover_letter_model)
        letter_body = await cld.get_cover_letter_text()
        letter_body = letter_body.replace("&", "\\&")
        date_str = datetime.now().strftime("%-d %B %Y")
        clm.set_data(date_str, args.company_name, letter_body, args.candidate_name, args.prof_signature)
        clm.to_pdf(os.path.join(tmp_dir, "cover_letter_tmp.pdf"))
        with open(os.path.join(tmp_dir, "cover_letter_tmp.tex"), "w", encoding="utf-8") as f:
            f.write(clm.render_tex_template())

    cvca.cv_model.copy().render_pdf(os.path.join(tmp_dir, "test_before_edits.pdf"))
    cvca.cv_model.render_pdf(os.path.join(tmp_dir, "test_after_edits.pdf"))
    cvca.cv_model.copy().render_pdf(os.path.join(tmp_dir, "test_after_edits_nocomments.pdf"))

    with open(os.path.join(tmp_dir, "metrics_summary.txt"), "w", encoding="utf-8") as f:
        f.write(json.dumps(metrics_post[0]))

    with open(os.path.join(tmp_dir, "job_post.txt"), "w", encoding="utf-8") as f:
        f.write(jpa.post_txt)

    latex_root = os.path.join(tmp_dir, "latex_folder")
    os.makedirs(latex_root, exist_ok=True)
    with open(os.path.join(latex_root, "cv_edited_with_comments.tex"), "w", encoding="utf-8") as f:
        f.write(cvca.cv_model.make_latex())
    with open(os.path.join(latex_root, "cv_edited_no_comments.tex"), "w", encoding="utf-8") as f:
        f.write(cvca.cv_model.copy().make_latex())

    resume_cls_src = os.path.join(os.getenv("CV_CUSTOMIZER_ROOT", os.getcwd()), "assets", "resume.cls")
    pic_src = os.path.join(os.getenv("CV_CUSTOMIZER_ROOT", os.getcwd()), "assets", "images", "my_pic.jpeg")
    if os.path.exists(resume_cls_src):
        shutil.copy(resume_cls_src, latex_root)
    if os.path.exists(pic_src):
        shutil.copy(pic_src, latex_root)

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    shutil.move(tmp_dir, output_dir)
    _log(f"- output written to: {output_dir}")
    return output_dir


def main() -> None:
    """Main.

    Returns:
        TODO: describe return value.
    """
    parser = _make_parser()
    args = parser.parse_args()
    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
