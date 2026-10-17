/** Pure, typed transport-to-view mappings, shared by HTTP and SSE consumers. */
import type * as API from '../types/api.generated';
import type * as View from '../types/view';

export function configToAPI(config: View.BackendConfig): API.BackendConfig {
  return {
    analysis_model: config.analysisModel, statement_editor_model: config.statementEditorModel,
    cover_letter_editor_model: config.coverLetterEditorModel,
    rewrite_policy: {
      max_section_items_keep: config.rewritePolicy.maxSectionItemsKeep,
      min_section_items_keep: config.rewritePolicy.minSectionItemsKeep,
      min_relevance_score: config.rewritePolicy.minRelevanceScore,
    },
    analysis_policy: { max_section_parse_retries: config.analysisPolicy.maxSectionParseRetries },
    outputs: {
      include_cover_letter: config.outputs.includeCoverLetter, render_pdf: config.outputs.renderPDF,
      include_latex: config.outputs.includeLaTeX, include_scoring_comments: config.outputs.includeScoringComments,
    },
    concurrency_limit: config.concurrency_limit,
  };
}

export function configToView(config: API.BackendConfig): View.BackendConfig {
  const model = (value: API.ModelConfig): View.ModelConfig => ({ ...value, config: value.config ?? {} });
  return {
    analysisModel: model(config.analysis_model), statementEditorModel: model(config.statement_editor_model),
    coverLetterEditorModel: model(config.cover_letter_editor_model),
    rewritePolicy: {
      maxSectionItemsKeep: config.rewrite_policy.max_section_items_keep,
      minSectionItemsKeep: config.rewrite_policy.min_section_items_keep,
      minRelevanceScore: config.rewrite_policy.min_relevance_score,
    },
    analysisPolicy: { maxSectionParseRetries: config.analysis_policy.max_section_parse_retries },
    outputs: {
      includeCoverLetter: config.outputs.include_cover_letter, renderPDF: config.outputs.render_pdf,
      includeLaTeX: config.outputs.include_latex, includeScoringComments: config.outputs.include_scoring_comments,
    },
    concurrency_limit: config.concurrency_limit,
  };
}

export function resultToView(result: API.CVJobResult): View.CVJobResult {
  return {
    personal_statement: result.personal_statement,
    overall_score: result.overall_score,
    summary_metrics: result.summary_metrics ?? {},
    experience_analysis: result.sections.map(({ title, ...section }) => ({
      ...section, section_title: title,
    })),
    artifacts: result.artifacts,
  };
}

export function jobToView(job: API.CVJobResponse): View.ProcessingState {
  return {
    jobId: job.id, status: job.status, progress: job.progress, message: job.message,
    result: job.result ? resultToView(job.result) : null,
    jobAnalysis: job.job_analysis, error: job.error,
  };
}

export function workingCopyToView(data: API.WorkingCopy): View.WorkingCopy {
  return {
    jobId: data.job_id, personalStatement: data.personal_statement,
    createdAt: data.created_at, updatedAt: data.updated_at,
    sections: data.sections.map(s => ({
      id: s.id,
      company: s.company, position: s.position, duration: s.duration,
      sectionScore: s.section_score, sectionExplanation: s.section_explanation,
      sectionPostingEvidence: s.section_posting_evidence,
      filterConfig: {
        minRelevanceScore: s.filter_config.min_relevance_score,
        minItemsKeep: s.filter_config.min_items_keep,
        maxItemsKeep: s.filter_config.max_items_keep,
      },
      items: s.items.map(it => ({
        id: it.id, scoredText: it.scored_text,
        text: it.text, originalText: it.original_text, relevanceScore: it.relevance_score,
        explanation: it.explanation, postingEvidence: it.posting_evidence, kept: it.kept,
      })),
    })),
  };
}

export function workingCopyToAPI(wc: View.WorkingCopy): API.WorkingCopy {
  return {
    job_id: wc.jobId, personal_statement: wc.personalStatement,
    created_at: wc.createdAt, updated_at: wc.updatedAt,
    sections: wc.sections.map(s => ({
      id: s.id,
      company: s.company, position: s.position, duration: s.duration,
      section_score: s.sectionScore, section_explanation: s.sectionExplanation,
      section_posting_evidence: s.sectionPostingEvidence,
      filter_config: {
        min_relevance_score: s.filterConfig.minRelevanceScore,
        min_items_keep: s.filterConfig.minItemsKeep,
        max_items_keep: s.filterConfig.maxItemsKeep,
      },
      items: s.items.map(it => ({
        id: it.id, scored_text: it.scoredText,
        text: it.text, original_text: it.originalText, relevance_score: it.relevanceScore,
        explanation: it.explanation, posting_evidence: it.postingEvidence, kept: it.kept,
      })),
    })),
  };
}
