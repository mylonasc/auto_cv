/** Pure, typed transport-to-view mappings, shared by HTTP and SSE consumers. */
import type * as API from '../types/api.generated';
import type * as View from '../types/view';

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
      company: s.company, position: s.position, duration: s.duration,
      sectionScore: s.section_score, sectionExplanation: s.section_explanation,
      sectionPostingEvidence: s.section_posting_evidence,
      filterConfig: {
        minRelevanceScore: s.filter_config.min_relevance_score,
        minItemsKeep: s.filter_config.min_items_keep,
        maxItemsKeep: s.filter_config.max_items_keep,
      },
      items: s.items.map(it => ({
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
      company: s.company, position: s.position, duration: s.duration,
      section_score: s.sectionScore, section_explanation: s.sectionExplanation,
      section_posting_evidence: s.sectionPostingEvidence,
      filter_config: {
        min_relevance_score: s.filterConfig.minRelevanceScore,
        min_items_keep: s.filterConfig.minItemsKeep,
        max_items_keep: s.filterConfig.maxItemsKeep,
      },
      items: s.items.map(it => ({
        text: it.text, original_text: it.originalText, relevance_score: it.relevanceScore,
        explanation: it.explanation, posting_evidence: it.postingEvidence, kept: it.kept,
      })),
    })),
  };
}
