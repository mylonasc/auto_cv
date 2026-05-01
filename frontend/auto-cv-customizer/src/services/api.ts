/**
 * API service for communicating with the CV Customizer backend.
 * All API calls go through this service.
 */
import axios, { AxiosInstance } from 'axios';
import { 
  JobDescription, ProcessingState, CVJobResult, 
  BackendConfig, SectionResult 
} from '../contexts/AppStateContext';

const API_BASE_URL = 'http://127.0.0.1:8005/v1';

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
  async createJob(jobDescription: string, candidate: string = 'charilaos_mylonas'): Promise<ProcessingState> {
    const response = await this.client.post('/cv-jobs/', {
      job_description: jobDescription,
      candidate: candidate,
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

  // Transform backend job format to frontend ProcessingState
  private transformJobToProcessingState(job: any): ProcessingState {
    return {
      jobId: job.id,
      status: job.status,
      progress: job.progress,
      message: job.message,
      result: job.result ? this.transformResult(job.result) : null,
      error: job.error,
    };
  }

  // Transform backend result format to frontend CVJobResult
  private transformResult(result: any): CVJobResult {
    return {
      job_id: result.job_id || '',
      status: result.status || 'succeeded',
      summary_metrics: {
        overall_score: result.overall_score,
        sections_count: result.sections?.length || 0,
      },
      experience_analysis: result.sections?.map((section: any) => ({
        section_title: section.title,
        aggregate_score: section.aggregate_score,
        items: section.items || [],
      })) || [],
      artifacts: result.artifacts || [],
    };
  }
}

export const apiService = new ApiService();
export default apiService;
