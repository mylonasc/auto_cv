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
}

export const apiService = new ApiService();
export default apiService;
