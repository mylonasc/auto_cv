/**
 * API service for communicating with the CV Customizer backend.
 * All API calls go through this service.
 */
import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  ProcessingState, CVJobResult,
  BackendConfig,
  BackendJob,
  CVData,
  CVVersionInfo,
  Artifact,
  CVResultSection,
  SummaryMetrics,
  JobAnalysis,
} from '../contexts/AppStateContext';

export interface TemplateRegistryResponse {
  cv_templates: Record<string, string>;
  motivation_letter_templates: Record<string, string>;
}

export interface RescoreItemPayload {
  index: number;
  text?: string;
}

export interface RescoreRequestPayload {
  section_index: number;
  item_indices: number[];
  items?: RescoreItemPayload[];
}

export interface RescoredItemResult {
  index: number;
  relevance_score: number;
  explanation: string;
  posting_evidence: string;
}

export interface RescoreResponse {
  section_index: number;
  items: RescoredItemResult[];
}

export interface RenderCVRequestPayload {
  min_relevance_score: number;
  min_section_items_keep: number;
  max_section_items_keep: number;
  cv_template_id: string;
  cv_template_path?: string;
  include_latex: boolean;
  render_pdf: boolean;
  working_copy?: Record<string, unknown>;
}

export interface JobAnalysisOnlyResponse {
  job_analysis: Record<string, unknown>;
}

const API_BASE_URL = '/api/v1';

type BackendModelConfig = {
  provider: 'ollama' | 'google';
  model: string;
  config?: Record<string, unknown>;
};

type BackendConfigPayload = {
  analysisModel?: BackendModelConfig;
  statementEditorModel?: BackendModelConfig;
  coverLetterEditorModel?: BackendModelConfig;
  analysis_model?: BackendModelConfig;
  statement_editor_model?: BackendModelConfig;
  cover_letter_editor_model?: BackendModelConfig;
  rewritePolicy?: {
    maxSectionItemsKeep?: number;
    minSectionItemsKeep?: number;
    minRelevanceScore?: number;
  };
  rewrite_policy?: {
    max_section_items_keep?: number;
    min_section_items_keep?: number;
    min_relevance_score?: number;
  };
  analysis_policy?: {
    max_section_parse_retries?: number;
  };
  analysisPolicy?: {
    maxSectionParseRetries?: number;
  };
  outputs?: {
    include_cover_letter?: boolean;
    render_pdf?: boolean;
    include_latex?: boolean;
    include_scoring_comments?: boolean;
    includeCoverLetter?: boolean;
    renderPDF?: boolean;
    includeLaTeX?: boolean;
    includeScoringComments?: boolean;
  };
  concurrency_limit?: number;
  [key: string]: unknown;
};

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  private toBackendConfig(config: BackendConfig): BackendConfigPayload {
    return {
      analysis_model: config.analysisModel,
      statement_editor_model: config.statementEditorModel,
      cover_letter_editor_model: config.coverLetterEditorModel,
      rewrite_policy: {
        max_section_items_keep: config.rewritePolicy.maxSectionItemsKeep,
        min_section_items_keep: config.rewritePolicy.minSectionItemsKeep,
        min_relevance_score: config.rewritePolicy.minRelevanceScore,
      },
      analysis_policy: {
        max_section_parse_retries: config.analysisPolicy.maxSectionParseRetries,
      },
      outputs: {
        include_cover_letter: config.outputs.includeCoverLetter,
        render_pdf: config.outputs.renderPDF,
        include_latex: config.outputs.includeLaTeX,
        include_scoring_comments: config.outputs.includeScoringComments,
      },
      concurrency_limit: config.concurrency_limit,
    };
  }

  private fromBackendConfig(config: BackendConfigPayload): BackendConfig {
    const analysisModel = (config.analysis_model || config.analysisModel || { provider: 'ollama', model: 'gemma4:31b', config: {} }) as BackendConfig['analysisModel'];
    const statementEditorModel = (config.statement_editor_model || config.statementEditorModel || {
      provider: 'google',
      model: 'models/gemini-2.5-flash-preview-05-20',
      config: {},
    }) as BackendConfig['statementEditorModel'];
    const coverLetterEditorModel = (config.cover_letter_editor_model || config.coverLetterEditorModel || {
      provider: 'google',
      model: 'models/gemini-2.5-flash-preview-05-20',
      config: {},
    }) as BackendConfig['coverLetterEditorModel'];

    return {
      analysisModel,
      statementEditorModel,
      coverLetterEditorModel,
      rewritePolicy: {
        maxSectionItemsKeep: config.rewrite_policy?.max_section_items_keep ?? config.rewritePolicy?.maxSectionItemsKeep ?? 6,
        minSectionItemsKeep: config.rewrite_policy?.min_section_items_keep ?? config.rewritePolicy?.minSectionItemsKeep ?? 1,
        minRelevanceScore: config.rewrite_policy?.min_relevance_score ?? config.rewritePolicy?.minRelevanceScore ?? 3,
      },
      analysisPolicy: {
        maxSectionParseRetries: config.analysis_policy?.max_section_parse_retries ?? config.analysisPolicy?.maxSectionParseRetries ?? 3,
      },
      outputs: {
        includeCoverLetter: config.outputs?.include_cover_letter ?? config.outputs?.includeCoverLetter ?? true,
        renderPDF: config.outputs?.render_pdf ?? config.outputs?.renderPDF ?? true,
        includeLaTeX: config.outputs?.include_latex ?? config.outputs?.includeLaTeX ?? true,
        includeScoringComments: config.outputs?.include_scoring_comments ?? config.outputs?.includeScoringComments ?? true,
      },
      concurrency_limit: config.concurrency_limit ?? 5,
    };
  }

  // Job Management
  async createJob(
    jobDescription: string,
    candidate: string = 'charilaos_mylonas',
    cvVersionId: string = 'master',
    config?: BackendConfig
  ): Promise<ProcessingState> {
    const response = await this.client.post('/cv-jobs/', {
      job_description: jobDescription,
      candidate: candidate,
      cv_version_id: cvVersionId,
      config: config ? this.toBackendConfig(config) : undefined,
    });
    return this.transformJobToProcessingState(response.data);
  }

  async analyzeJobOnly(jobDescription: string, config?: BackendConfig): Promise<JobAnalysisOnlyResponse> {
    const response = await this.client.post('/cv-jobs/job-analysis', {
      job_description: jobDescription,
      config: config ? this.toBackendConfig(config) : undefined,
    });
    return response.data;
  }

  async getJob(jobId: string): Promise<ProcessingState> {
    const response = await this.client.get(`/cv-jobs/${jobId}`);
    return this.transformJobToProcessingState(response.data);
  }

  async cancelJob(jobId: string): Promise<ProcessingState> {
    const response = await this.client.post(`/cv-jobs/${jobId}/cancel`);
    return this.transformJobToProcessingState(response.data);
  }

  async listJobs(): Promise<BackendJob[]> {
    const response = await this.client.get('/cv-jobs/');
    return response.data;
  }

  async getJobResult(jobId: string): Promise<CVJobResult> {
    const response = await this.client.get(`/cv-jobs/${jobId}/result`);
    return this.transformResult(response.data);
  }

  async archiveJob(jobId: string): Promise<BackendJob> {
    const response = await this.client.post(`/cv-jobs/${jobId}/archive`);
    return response.data;
  }

  async unarchiveJob(jobId: string): Promise<BackendJob> {
    const response = await this.client.post(`/cv-jobs/${jobId}/unarchive`);
    return response.data;
  }

  async deleteJob(jobId: string): Promise<void> {
    await this.client.delete(`/cv-jobs/${jobId}`);
  }

  async downloadArtifact(jobId: string, artifactId: string, filename: string): Promise<void> {
    const response = await this.client.get(`/cv-jobs/${jobId}/artifacts/${artifactId}`, {
      responseType: 'blob'
    });
    
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  }

  getArtifactPreviewUrl(jobId: string, artifactId: string): string {
    return `/api/v1/cv-jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(artifactId)}?inline=1`;
  }

  // Job stream (SSE) for real-time updates
  createJobStream(jobId: string): EventSource {
    return new EventSource(`${API_BASE_URL}/cv-jobs/${jobId}/stream`);
  }

  // Configuration
  async getConfig(): Promise<BackendConfig> {
    const response = await this.client.get('/config');
    return this.fromBackendConfig(response.data);
  }

  async updateConfig(config: BackendConfig): Promise<BackendConfig> {
    const payload = this.toBackendConfig(config);
    const response = await this.client.put('/config', payload);
    return this.fromBackendConfig(response.data);
  }

  // Models
  async getAvailableModels(provider?: string): Promise<{ ollama?: string[]; google?: string[] }> {
    const params = provider ? { provider } : {};
    const response = await this.client.get('/models/available', { params });
    return response.data;
  }

  // Health check
  async healthCheck(): Promise<{ status?: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // CV Data Management
  async getCVData(candidate: string = 'charilaos_mylonas'): Promise<CVData> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.get(`/cv-data/${c}`);
    return response.data;
  }

  async updateCVData(data: CVData, candidate: string = 'charilaos_mylonas'): Promise<CVData> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.put(`/cv-data/${c}`, data);
    return response.data;
  }

  async listCVVersions(candidate: string = 'charilaos_mylonas'): Promise<CVVersionInfo[]> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.get(`/cv-data/${c}/versions`);
    return response.data;
  }

  async getCVVersion(versionId: string, candidate: string = 'charilaos_mylonas'): Promise<CVData> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.get(`/cv-data/${c}/versions/${versionId}`);
    return response.data;
  }

  async createCVVersion(versionId: string, data: CVData, candidate: string = 'charilaos_mylonas'): Promise<CVData> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.post(`/cv-data/${c}/versions/${versionId}`, data);
    return response.data;
  }

  async updateCVVersion(versionId: string, data: CVData, candidate: string = 'charilaos_mylonas'): Promise<CVData> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.put(`/cv-data/${c}/versions/${versionId}`, data);
    return response.data;
  }

  async deleteCVVersion(versionId: string, candidate: string = 'charilaos_mylonas'): Promise<{ status: string; message: string }> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.delete(`/cv-data/${c}/versions/${versionId}`);
    return response.data;
  }

  async getTemplateRegistry(): Promise<TemplateRegistryResponse> {
    const response = await this.client.get('/cv-data/templates');
    return response.data;
  }

  async renderJobArtifacts(jobId: string, payload: RenderCVRequestPayload): Promise<ProcessingState> {
    const response = await this.client.post(`/cv-jobs/${jobId}/render`, payload);
    return this.transformJobToProcessingState(response.data);
  }

  // ── Working Copy API ──

  async getWorkingCopy(jobId: string): Promise<Record<string, unknown>> {
    const response = await this.client.get(`/cv-jobs/${jobId}/working-cv`);
    return response.data;
  }

  async saveWorkingCopy(jobId: string, workingCopy: Record<string, unknown>): Promise<Record<string, unknown>> {
    const response = await this.client.put(`/cv-jobs/${jobId}/working-cv`, workingCopy);
    return response.data;
  }

  async rescoreWorkingCopyItems(jobId: string, payload: RescoreRequestPayload): Promise<RescoreResponse> {
    const response = await this.client.post(`/cv-jobs/${jobId}/working-cv/rescore`, payload);
    return response.data;
  }

  // Transform backend job format to frontend ProcessingState
  public transformJobToProcessingState(job: BackendJob): ProcessingState {
    return {
      jobId: job.id ?? null,
      status: job.status,
      progress: job.progress ?? null,
      message: job.message ?? null,
      result: job.result ? this.transformResult(job.result) : null,
      jobAnalysis: (job.job_analysis as JobAnalysis | null) ?? null,
      error: job.error ?? null,
    };
  }

  // Transform backend result format to frontend CVJobResult
  public transformResult(result: Record<string, unknown>): CVJobResult {
    const sections = (result.sections as Array<Record<string, unknown>> | undefined) || [];
    const summary_metrics = (result.summary_metrics as SummaryMetrics | undefined) || {
      overall_score: result.overall_score as number | undefined,
      sections_count: sections.length,
    };

    return {
      job_id: (result.job_id as string) || '',
      status: (result.status as string) || 'succeeded',
      summary_metrics,
      experience_analysis: sections.map((section) => ({
        section_title: (section.section_title as string) || (section.title as string) || '',
        company: section.company as string | undefined,
        position: section.position as string | undefined,
        duration: section.duration as string | undefined,
        section_score: section.section_score as number | undefined,
        explanation: section.explanation as string | undefined,
        items: (section.items as CVResultSection['items']) || [],
      })),
      artifacts: ((result.artifacts as Artifact[] | undefined) || []),
    };
  }

  // ── Working Copy Transforms ──

  public transformWorkingCopyFromBackend(data: Record<string, unknown>): import('../contexts/AppStateContext').WorkingCopy {
    return {
      jobId: (data.job_id as string) || '',
      personalStatement: (data.personal_statement as string) || '',
      sections: ((data.sections as Array<Record<string, unknown>>) || []).map((s: Record<string, unknown>) => ({
        company: (s.company as string) || '',
        position: (s.position as string) || '',
        duration: (s.duration as string) || '',
        sectionScore: (s.section_score as number | null) ?? null,
        sectionExplanation: (s.section_explanation as string | null) ?? null,
        sectionPostingEvidence: (s.section_posting_evidence as string | null) ?? null,
        filterConfig: {
          minRelevanceScore: ((s.filter_config as Record<string, unknown>)?.min_relevance_score as number) ?? 3,
          minItemsKeep: ((s.filter_config as Record<string, unknown>)?.min_items_keep as number) ?? 1,
          maxItemsKeep: ((s.filter_config as Record<string, unknown>)?.max_items_keep as number) ?? 6,
        },
        items: ((s.items as Array<Record<string, unknown>>) || []).map((it: Record<string, unknown>) => ({
          text: (it.text as string) || '',
          originalText: (it.original_text as string) || '',
          relevanceScore: (it.relevance_score as number | null) ?? null,
          explanation: (it.explanation as string | null) ?? null,
          postingEvidence: (it.posting_evidence as string | null) ?? null,
          kept: (it.kept as boolean) ?? true,
        })),
      })),
      createdAt: (data.created_at as string | null) ?? null,
      updatedAt: (data.updated_at as string | null) ?? null,
    };
  }

  public transformWorkingCopyToBackend(wc: import('../contexts/AppStateContext').WorkingCopy): Record<string, unknown> {
    return {
      job_id: wc.jobId,
      personal_statement: wc.personalStatement,
      sections: wc.sections.map((s) => ({
        company: s.company,
        position: s.position,
        duration: s.duration,
        section_score: s.sectionScore,
        section_explanation: s.sectionExplanation,
        section_posting_evidence: s.sectionPostingEvidence,
        filter_config: {
          min_relevance_score: s.filterConfig.minRelevanceScore,
          min_items_keep: s.filterConfig.minItemsKeep,
          max_items_keep: s.filterConfig.maxItemsKeep,
        },
        items: s.items.map((it) => ({
          text: it.text,
          original_text: it.originalText,
          relevance_score: it.relevanceScore,
          explanation: it.explanation,
          posting_evidence: it.postingEvidence,
          kept: it.kept,
        })),
      })),
      created_at: wc.createdAt,
      updated_at: wc.updatedAt,
    };
  }

  // ── Submissions API ──

  async createSubmission(payload: { job_id: string; artifact_ids?: string[]; notes?: string }): Promise<import('../contexts/AppStateContext').Submission> {
    const response = await this.client.post('/submissions/', payload);
    return response.data;
  }

  async listSubmissions(): Promise<import('../contexts/AppStateContext').Submission[]> {
    const response = await this.client.get('/submissions/');
    return response.data;
  }

  async getSubmission(submissionId: string): Promise<import('../contexts/AppStateContext').Submission> {
    const response = await this.client.get(`/submissions/${submissionId}`);
    return response.data;
  }

  async updateSubmission(submissionId: string, payload: { result?: string; notes?: string }): Promise<import('../contexts/AppStateContext').Submission> {
    const response = await this.client.put(`/submissions/${submissionId}`, payload);
    return response.data;
  }

  async deleteSubmission(submissionId: string): Promise<void> {
    await this.client.delete(`/submissions/${submissionId}`);
  }
}

export const apiService = new ApiService();
export default apiService;
