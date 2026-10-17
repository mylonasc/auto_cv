import { useProcessingControls } from '../../hooks/useProcessingControls';
import { Button, StatusBadge } from '../common/Primitives';
import { WorkingCopyEditor } from '../workflow/WorkingCopyEditor';
import { JobStatusPanel, PostingAnalysis } from '../workflow/JobStatusPanel';
import './ProcessingTab.css';

export default function ProcessingTab() {
  const c = useProcessingControls();
  const display = c.activeJob || c.viewedJob;
  return <div className="processing-tab">
    <div className="processing-header"><h2>Guided CV Workflow</h2></div>
    <section className="rewrite-controls-card"><h3>Stage 1: Job Analysis</h3>
      <p>Analyze the selected job posting and extract requirements.</p>
      <Button variant="primary" onClick={c.preview} disabled={!c.hasPosting || c.posting?.status === 'processing'}>
        {c.posting?.status === 'processing' ? 'Running...' : 'Run Job Analysis Only'}</Button>
      {c.posting && <section aria-label="Posting preview"><p role="status">Posting preview: <StatusBadge status={c.posting.status} /></p>
        {c.posting.error && <p role="alert">{c.posting.error}</p>}
        {c.posting.jobAnalysis && <PostingAnalysis analysis={c.posting.jobAnalysis} />}</section>}
    </section>
    <section className="rewrite-controls-card"><h3>Stage 2: CV Analysis + Personal Statement Selection</h3>
      <p>Run complete posting and CV analysis, statement optimization and configured initial outputs. Stage 1 is an optional preview, not a prerequisite.</p>
      <div className="processing-actions">{c.activeJob ? <Button variant="danger" onClick={c.cancel}>Cancel Running Analysis</Button> :
        <Button variant="primary" disabled={c.starting || !c.hasPosting} onClick={c.start}>{c.starting ? 'Initializing...' : 'Run CV Analysis'}</Button>}
        <Button disabled={!c.viewedJob?.result} onClick={c.showResults}>Open Analysis Results</Button></div>
    </section>
    {c.error && <p role="alert">{c.error}</p>}
    <WorkingCopyEditor controls={c} />
    <section className="rewrite-controls-card"><h3>Stage 4: CV PDF Rendering</h3>
      <p>Render new artifacts from existing analysis using current filtering and selected template.</p>
      <label>CV template<select aria-label="CV template" value={c.template} onChange={event => c.setTemplate(event.target.value)}>
        {Object.keys(c.registry.cv_templates).map(id => <option key={id} value={id}>{id}</option>)}</select></label>
      <Button variant="primary" onClick={() => c.render(false)} disabled={c.rendering || !c.viewedJob?.result}>
        {c.rendering ? 'Rendering...' : 'Render CV Artifacts'}</Button>
    </section>
    {display ? <JobStatusPanel job={display} /> : <p>Select a posting and source CV version to begin analysis, or load a result from History.</p>}
  </div>;
}
