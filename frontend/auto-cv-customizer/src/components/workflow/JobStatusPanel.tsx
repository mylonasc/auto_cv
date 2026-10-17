import type { JobAnalysis, ProcessingState } from '../../types/view';
import { StatusBadge } from '../common/Primitives';

export function PostingAnalysis({ analysis }: { analysis: JobAnalysis }) {
  const industry = analysis.industry_and_position_analysis;
  return <div className="job-analysis-details"><h3>Job Posting Analysis Results</h3><div className="analysis-grid">
    {industry && <div className="analysis-card"><h4>Industry & Position</h4><p>Title: {industry.job_title}</p>
      <p>Company: {industry.company_name}</p><p>Industry: {industry.industry}</p>
      <p>Hands-on: {industry.hands_on_skills ?? 'N/A'}/10 · Business: {industry.business_skills ?? 'N/A'}/10</p></div>}
    {(['skills', 'qualifications', 'preferred_qualifications'] as const).map(field => analysis.basic_analysis?.[field] &&
      <div className="analysis-card" key={field}><h4>{field === 'skills' ? 'Extracted Skills' : field === 'qualifications' ? 'Qualifications' : 'Preferred'}</h4>
        {analysis.provenance?.[field]?.status === 'fallback' && <p role="note">Heuristic fallback — {analysis.provenance[field].reason}</p>}
        <ul>{analysis.basic_analysis[field]?.split(';').map((text, index) => <li key={index}>{text.trim()}</li>)}</ul></div>)}
  </div></div>;
}

export function JobStatusPanel({ job }: { job: ProcessingState }) {
  return <section className="processing-content"><div className="status-card"><div className="status-header">
    <span>Status:</span><StatusBadge status={job.status} /></div><p>{job.progress || 'Initializing...'}</p><p>{job.message}</p>
    {job.status === 'processing' && <div className="loader-container"><div className="loader" /></div>}</div>
    {job.error && <div className="error-card" role="alert"><h3>Error</h3><p>{job.error}</p></div>}
    {job.jobAnalysis && <PostingAnalysis analysis={job.jobAnalysis} />}
  </section>;
}
