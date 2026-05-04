/**
 * API service for communicating with the CV Customizer backend.
 * All API calls go through this service.
 */
import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type { 
  ProcessingState, CVJobResult, 
  BackendConfig 
} from '../contexts/AppStateContext';

const API_BASE_URL = '/api/v1';

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

  private toBackendConfig(config: BackendConfig): any {
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

  private fromBackendConfig(config: any): BackendConfig {
    const analysisModel = config.analysis_model || config.analysisModel || { provider: 'ollama', model: 'gemma4:31b', config: {} };
    const statementEditorModel = config.statement_editor_model || config.statementEditorModel || {
      provider: 'google',
      model: 'models/gemini-2.5-flash-preview-05-20',
      config: {},
    };
    const coverLetterEditorModel = config.cover_letter_editor_model || config.coverLetterEditorModel || {
      provider: 'google',
      model: 'models/gemini-2.5-flash-preview-05-20',
      config: {},
    };

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

  async listJobs(): Promise<any[]> {
    const response = await this.client.get('/cv-jobs/');
    return response.data;
  }

  async getJobResult(jobId: string): Promise<CVJobResult> {
    const response = await this.client.get(`/cv-jobs/${jobId}/result`);
    return this.transformResult(response.data);
  }

  async archiveJob(jobId: string): Promise<any> {
    const response = await this.client.post(`/cv-jobs/${jobId}/archive`);
    return response.data;
  }

  async unarchiveJob(jobId: string): Promise<any> {
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
  async getAvailableModels(provider?: string): Promise<any> {
    const params = provider ? { provider } : {};
    const response = await this.client.get('/models/available', { params });
    return response.data;
  }

  // Health check
  async healthCheck(): Promise<any> {
    const response = await this.client.get('/health');
    return response.data;
  }

  // CV Data Management
  async getCVData(candidate: string = 'charilaos_mylonas'): Promise<any> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.get(`/cv-data/${c}`);
    return response.data;
  }

  async updateCVData(data: any, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.put(`/cv-data/${c}`, data);
    return response.data;
  }

  async listCVVersions(candidate: string = 'charilaos_mylonas'): Promise<any[]> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.get(`/cv-data/${c}/versions`);
    return response.data;
  }

  async getCVVersion(versionId: string, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.get(`/cv-data/${c}/versions/${versionId}`);
    return response.data;
  }

  async createCVVersion(versionId: string, data: any, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.post(`/cv-data/${c}/versions/${versionId}`, data);
    return response.data;
  }

  async updateCVVersion(versionId: string, data: any, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.put(`/cv-data/${c}/versions/${versionId}`, data);
    return response.data;
  }

  async deleteCVVersion(versionId: string, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const c = candidate || 'charilaos_mylonas';
    const response = await this.client.delete(`/cv-data/${c}/versions/${versionId}`);
    return response.data;
  }

  // Transform backend job format to frontend ProcessingState
  public transformJobToProcessingState(job: any): ProcessingState {
    return {
      jobId: job.id ?? null,
      status: job.status,
      progress: job.progress ?? null,
      message: job.message ?? null,
      result: job.result ? this.transformResult(job.result) : null,
      jobAnalysis: job.job_analysis ?? null,
      error: job.error ?? null,
    };
  }

  // Transform backend result format to frontend CVJobResult
  public transformResult(result: any): CVJobResult {
    return {
      job_id: result.job_id || '',
      status: result.status || 'succeeded',
      summary_metrics: result.summary_metrics || {
        overall_score: result.overall_score,
        sections_count: result.sections?.length || 0,
      },
      experience_analysis: result.sections?.map((section: any) => ({
        section_title: section.title,
        company: section.company,
        position: section.position,
        duration: section.duration,
        section_score: section.section_score,
        explanation: section.explanation,
        items: section.items || [],
      })) || [],
      artifacts: result.artifacts || [],
    };
  }
}

export const apiService = new ApiService();
export default apiService;
