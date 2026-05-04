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

  // Job Management
  async createJob(jobDescription: string, candidate: string = 'charilaos_mylonas', cvVersionId: string = 'master'): Promise<ProcessingState> {
    const response = await this.client.post('/cv-jobs/', {
      job_description: jobDescription,
      candidate: candidate,
      cv_version_id: cvVersionId
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

  async listJobs(): Promise<ProcessingState[]> {
    const response = await this.client.get('/cv-jobs/');
    return response.data.map((job: any) => this.transformJobToProcessingState(job));
  }

  async getJobResult(jobId: string): Promise<CVJobResult> {
    const response = await this.client.get(`/cv-jobs/${jobId}/result`);
    return this.transformResult(response.data);
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

  // Job stream (SSE) for real-time updates
  createJobStream(jobId: string): EventSource {
    return new EventSource(`${API_BASE_URL}/cv-jobs/${jobId}/stream`);
  }

  // Configuration
  async getConfig(): Promise<BackendConfig> {
    const response = await this.client.get('/config');
    return response.data;
  }

  async updateConfig(config: BackendConfig): Promise<BackendConfig> {
    const response = await this.client.put('/config', config);
    return response.data;
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
    const response = await this.client.get(`/cv-data/${candidate}`);
    return response.data;
  }

  async updateCVData(data: any, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const response = await this.client.put(`/cv-data/${candidate}`, data);
    return response.data;
  }

  async listCVVersions(candidate: string = 'charilaos_mylonas'): Promise<any[]> {
    const response = await this.client.get(`/cv-data/${candidate}/versions`);
    return response.data;
  }

  async getCVVersion(versionId: string, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const response = await this.client.get(`/cv-data/${candidate}/versions/${versionId}`);
    return response.data;
  }

  async createCVVersion(versionId: string, data: any, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const response = await this.client.post(`/cv-data/${candidate}/versions/${versionId}`, data);
    return response.data;
  }

  async updateCVVersion(versionId: string, data: any, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const response = await this.client.put(`/cv-data/${candidate}/versions/${versionId}`, data);
    return response.data;
  }

  async deleteCVVersion(versionId: string, candidate: string = 'charilaos_mylonas'): Promise<any> {
    const response = await this.client.delete(`/cv-data/${candidate}/versions/${versionId}`);
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
