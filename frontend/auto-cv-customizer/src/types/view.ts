/** UI models are separate from serialized API contracts and from React context. */
import type * as API from './api.generated';

export type Artifact = API.Artifact;
export type BackendJob = API.CVJobResponse;
export type JobAnalysis = API.JobAnalysis;
export type Submission = API.Submission;
export type CVResultItem = API.ResultItem;
export type SummaryMetrics = Record<string, number | null | undefined>;
export type CVResultSection = Omit<API.SectionResult, 'title'> & { section_title: string };

export interface CVJobResult {
  personal_statement: string | null;
  overall_score: number | null;
  summary_metrics: SummaryMetrics;
  experience_analysis: CVResultSection[];
  artifacts: Artifact[];
}

export interface ModelConfig {
  provider: 'ollama' | 'google';
  model: string;
  config: Record<string, unknown>;
}

export interface RewritePolicy {
  maxSectionItemsKeep: number;
  minSectionItemsKeep: number;
  minRelevanceScore: number;
}

export interface AnalysisPolicy { maxSectionParseRetries: number }
export interface OutputsConfig {
  includeCoverLetter: boolean;
  renderPDF: boolean;
  includeLaTeX: boolean;
  includeScoringComments: boolean;
}

export interface BackendConfig {
  analysisModel: ModelConfig;
  statementEditorModel: ModelConfig;
  coverLetterEditorModel: ModelConfig;
  rewritePolicy: RewritePolicy;
  analysisPolicy: AnalysisPolicy;
  outputs: OutputsConfig;
  concurrency_limit: number;
}

export interface ProcessingState {
  jobId: string | null;
  status: API.JobStatus;
  progress: string | null;
  message: string | null;
  result: CVJobResult | null;
  jobAnalysis: JobAnalysis | null;
  error: string | null;
}

export interface SectionFilterConfig {
  minRelevanceScore: number;
  minItemsKeep: number;
  maxItemsKeep: number;
}
export interface WorkingCopyItem {
  id: string;
  text: string;
  scoredText: string | null;
  originalText: string;
  relevanceScore: number | null;
  explanation: string | null;
  postingEvidence: string | null;
  kept: boolean;
}
export interface WorkingCopySection {
  id: string;
  company: string;
  position: string;
  duration: string;
  sectionScore: number | null;
  sectionExplanation: string | null;
  sectionPostingEvidence: string | null;
  filterConfig: SectionFilterConfig;
  items: WorkingCopyItem[];
}
export interface WorkingCopy {
  jobId: string;
  personalStatement: string;
  sections: WorkingCopySection[];
  createdAt: string | null;
  updatedAt: string | null;
}
