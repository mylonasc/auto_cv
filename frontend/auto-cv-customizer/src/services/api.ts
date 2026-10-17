/** HTTP transport and explicit view adapters; no dependency on React context. */
import axios from 'axios';
import type * as API from '../types/api.generated';
import type { CVData } from '../types/cv';
import type { BackendConfig } from '../types/view';
import { jobToView, resultToView, workingCopyToAPI, workingCopyToView, configToAPI, configToView } from './mappers';

export interface TemplateRegistryResponse {
  cv_templates: Record<string, string>;
  motivation_letter_templates: Record<string, string>;
}
export type RescoreRequestPayload = API.RescoreRequestInput;
export type RescoreResponse = API.RescoreResponse;
export type RescoredItemResult = API.RescoredItemResult;
export type RenderCVRequestPayload = API.RenderCVRequestInput;
export type JobAnalysisOnlyResponse = API.JobAnalysisResponse;
export interface CVVersionInfo { id: string; name: string; last_modified: number }

const API_BASE_URL = '/api/v1';

class ApiService {
  private client = axios.create({ baseURL: API_BASE_URL, headers: { 'Content-Type': 'application/json' } });

  private toBackendConfig = configToAPI;
  private fromBackendConfig = configToView;

  async createJob(jobDescription: string, candidate = 'charilaos_mylonas', cvVersionId = 'master', config?: BackendConfig) {
    const payload: API.CreateJobRequestInput = {
      job_description: jobDescription, candidate, cv_version_id: cvVersionId,
      config: config ? this.toBackendConfig(config) : null,
    };
    return jobToView((await this.client.post<API.CVJobResponse>('/cv-jobs/', payload)).data);
  }
  async analyzeJobOnly(jobDescription: string, config?: BackendConfig) {
    const payload: API.JobAnalysisRequestInput = {
      job_description: jobDescription, config: config ? this.toBackendConfig(config) : null,
    };
    return (await this.client.post<API.JobAnalysisResponse>('/cv-jobs/job-analysis', payload)).data;
  }
  async getJob(id: string) { return jobToView((await this.client.get<API.CVJobResponse>(`/cv-jobs/${id}`)).data); }
  async cancelJob(id: string) { return jobToView((await this.client.post<API.CVJobResponse>(`/cv-jobs/${id}/cancel`)).data); }
  async listJobs() { return (await this.client.get<API.CVJobResponse[]>('/cv-jobs/')).data; }
  async getJobResult(id: string) { return resultToView((await this.client.get<API.CVJobResult>(`/cv-jobs/${id}/result`)).data); }
  async archiveJob(id: string) { return (await this.client.post<API.CVJobResponse>(`/cv-jobs/${id}/archive`)).data; }
  async unarchiveJob(id: string) { return (await this.client.post<API.CVJobResponse>(`/cv-jobs/${id}/unarchive`)).data; }
  async deleteJob(id: string) { await this.client.delete(`/cv-jobs/${id}`); }

  async downloadArtifact(jobId: string, artifactId: string, filename: string): Promise<void> {
    const response = await this.client.get(`/cv-jobs/${jobId}/artifacts/${artifactId}`, { responseType: 'blob' });
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
    return `${API_BASE_URL}/cv-jobs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(artifactId)}?inline=1`;
  }
  createJobStream(id: string) { return new EventSource(`${API_BASE_URL}/cv-jobs/${id}/stream`); }
  async getConfig() { return this.fromBackendConfig((await this.client.get<API.BackendConfig>('/config')).data); }
  async updateConfig(config: BackendConfig) {
    return this.fromBackendConfig((await this.client.put<API.BackendConfig>('/config', this.toBackendConfig(config))).data);
  }
  async getAvailableModels(provider?: string) {
    return (await this.client.get<{ ollama?: string[]; google?: string[] }>('/models/available', { params: provider ? { provider } : {} })).data;
  }
  async healthCheck() { return (await this.client.get<{ status: string }>('/health')).data; }

  async getCVData(candidate = 'charilaos_mylonas') { return this.getCVVersion('master', candidate); }
  async updateCVData(data: CVData, candidate = 'charilaos_mylonas') { return this.updateCVVersion('master', data, candidate); }
  async listCVVersions(candidate = 'charilaos_mylonas') {
    return (await this.client.get<CVVersionInfo[]>(`/cv-data/${candidate}/versions`)).data;
  }
  async getCVVersion(id: string, candidate = 'charilaos_mylonas') {
    return (await this.client.get<CVData>(`/cv-data/${candidate}/versions/${id}`)).data;
  }
  async createCVVersion(id: string, data: CVData, candidate = 'charilaos_mylonas') {
    return (await this.client.post<CVData>(`/cv-data/${candidate}/versions/${id}`, data)).data;
  }
  async updateCVVersion(id: string, data: CVData, candidate = 'charilaos_mylonas') {
    return (await this.client.put<CVData>(`/cv-data/${candidate}/versions/${id}`, data)).data;
  }
  async deleteCVVersion(id: string, candidate = 'charilaos_mylonas') {
    return (await this.client.delete<{ status: string; message: string }>(`/cv-data/${candidate}/versions/${id}`)).data;
  }
  async getTemplateRegistry() { return (await this.client.get<TemplateRegistryResponse>('/cv-data/templates')).data; }
  async renderJobArtifacts(id: string, payload: API.RenderCVRequestInput) {
    return jobToView((await this.client.post<API.CVJobResponse>(`/cv-jobs/${id}/render`, payload)).data);
  }
  async getWorkingCopy(id: string) { return (await this.client.get<API.WorkingCopy>(`/cv-jobs/${id}/working-cv`)).data; }
  async saveWorkingCopy(id: string, data: API.WorkingCopy) {
    return (await this.client.put<API.WorkingCopy>(`/cv-jobs/${id}/working-cv`, data)).data;
  }
  async rescoreWorkingCopyItems(id: string, payload: API.RescoreRequestInput) {
    return (await this.client.post<API.RescoreResponse>(`/cv-jobs/${id}/working-cv/rescore`, payload)).data;
  }

  public transformJobToProcessingState = jobToView;
  public transformResult = resultToView;
  public transformWorkingCopyFromBackend = workingCopyToView;
  public transformWorkingCopyToBackend = workingCopyToAPI;

  async createSubmission(payload: API.SubmissionCreateRequestInput) {
    return (await this.client.post<API.Submission>('/submissions/', payload)).data;
  }
  async listSubmissions() { return (await this.client.get<API.Submission[]>('/submissions/')).data; }
  async getSubmission(id: string) { return (await this.client.get<API.Submission>(`/submissions/${id}`)).data; }
  async updateSubmission(id: string, payload: API.SubmissionUpdateRequestInput) {
    return (await this.client.put<API.Submission>(`/submissions/${id}`, payload)).data;
  }
  async deleteSubmission(id: string) { await this.client.delete(`/submissions/${id}`); }
}

export const apiService = new ApiService();
export default apiService;
