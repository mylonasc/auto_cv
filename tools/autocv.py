"""CLI adapter for shared posting/CV analysis, selection and rendering stages."""

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import BackendConfig, ModelConfig, PROVIDER_DEFAULTS, build_model, public_config
from src.cv_storage import load_cv_file
from src.template_registry import resolve_cv_templates
from src.pipeline import analyze_cv
from src.artifacts import render_artifacts
from src.utils import CoverLetterModel
from src.utils_cross_analysis import CoverLetterDrafter


def _make_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-json", required=True)
    parser.add_argument("--job-posting", required=True)
    parser.add_argument("--output-dir", default=None, help="Fresh output directory; existing paths are never replaced.")
    parser.add_argument("--candidate-id", default="charilaos_mylonas")
    parser.add_argument("--candidate-name", default="Charilaos Mylonas")
    parser.add_argument("--company-name", default="Company")
    parser.add_argument("--prof-signature", default="\\\\Machine Learning Engineer \\\\ Zurich")
    parser.add_argument("--cv-template", default=None)
    parser.add_argument("--cv-template-id", default=None)
    parser.add_argument("--motivation-template", default=None)
    parser.add_argument("--motivation-template-id", default=None)
    for role in ("analysis", "authoring", "cover-letter"):
        parser.add_argument(f"--{role}-provider", default=None, choices=["google", "ollama"])
        parser.add_argument(f"--{role}-model", default=None)
    parser.add_argument("--max-section-items-keep", type=int, default=None)
    parser.add_argument("--min-relevance-score-keep", type=int, default=None)
    parser.add_argument("--min-section-items-keep", type=int, default=None)
    parser.add_argument("--skip-cover-letter", action="store_true")
    return parser


def config_from_args(args):
    config = BackendConfig()
    for role, field in (("analysis", "analysis_model"), ("authoring", "statement_editor_model"),
                        ("cover_letter", "cover_letter_editor_model")):
        default = getattr(config, field)
        provider = getattr(args, f"{role}_provider") or default.provider
        model = getattr(args, f"{role}_model") or (default.model if provider == default.provider else PROVIDER_DEFAULTS[provider])
        setattr(config, field, ModelConfig(provider=provider, model=model))
    policy = config.rewrite_policy.model_dump()
    for argument, field in (("max_section_items_keep", "max_section_items_keep"),
                            ("min_section_items_keep", "min_section_items_keep"),
                            ("min_relevance_score_keep", "min_relevance_score")):
        if getattr(args, argument) is not None:
            policy[field] = getattr(args, argument)
    config.rewrite_policy = type(config.rewrite_policy).model_validate(policy)
    config.outputs.include_cover_letter = not args.skip_cover_letter
    return config


async def run_pipeline(args):
    output = Path(args.output_dir or f"autocv_output_{Path(args.job_posting).stem}")
    if output.exists():
        raise FileExistsError(f"Output already exists; choose a fresh directory: {output}")
    config = config_from_args(args)
    source = resolve_cv_templates(load_cv_file(args.candidate_json, args.candidate_id),
                                  cv_template_id=args.cv_template_id, cv_template_path=args.cv_template,
                                  motivation_template_id=args.motivation_template_id,
                                  motivation_template_path=args.motivation_template)
    text = Path(args.job_posting).read_text(encoding="utf-8")
    run = await analyze_cv(source, text, config)
    with tempfile.TemporaryDirectory(prefix="autocv_") as temporary:
        folder = Path(temporary) / "output"
        folder.mkdir()
        latex = folder / "latex_folder"
        render_artifacts(run.analyzer.source_cv, folder, "test_before_edits", include_latex=False)
        render_artifacts(run.analyzer.render_document(True), folder, "test_after_edits",
                         include_latex=False, include_scoring_comments=True)
        render_artifacts(run.analyzer.render_document(), folder, "test_after_edits_nocomments", include_latex=False)
        render_artifacts(run.analyzer.render_document(True), latex, "cv_edited_with_comments",
                         render_pdf=False, include_scoring_comments=True)
        render_artifacts(run.analyzer.render_document(), latex, "cv_edited_no_comments", render_pdf=False)
        if config.outputs.include_cover_letter:
            model = build_model(config.cover_letter_editor_model)
            body = await CoverLetterDrafter(run.analyzer, model).get_cover_letter_text()
            letter = CoverLetterModel(motivation_template=run.source.motivation_letter_template)
            letter.set_data(datetime.now().strftime("%-d %B %Y"), args.company_name, body.replace("&", "\\&"),
                            args.candidate_name, args.prof_signature)
            render_artifacts(letter, folder, "cover_letter_tmp", source="cover_letter")
        (folder / "metrics_summary.txt").write_text(json.dumps(run.analyzer.get_section_aggregate_metrics()[0]))
        (folder / "effective_config.json").write_text(public_config(config).model_dump_json(indent=2))
        (folder / "job_post.txt").write_text(text, encoding="utf-8")
        for cls in (REPO_ROOT / "assets").glob("resume*.cls"):
            shutil.copy(cls, latex)
        picture = REPO_ROOT / "assets/images/my_pic.jpeg"
        if picture.exists():
            shutil.copy(picture, latex)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(output))
    print(f"Output written to {output}")
    return str(output)


def main():
    asyncio.run(run_pipeline(_make_parser().parse_args()))


if __name__ == "__main__":
    main()
