import { useState } from 'react';
import type { WorkingCopySection } from '../../types/view';
import type { ProcessingControls } from '../../hooks/useProcessingControls';
import { Button } from '../common/Primitives';

function Evidence({ explanation, evidence }: { explanation: string | null; evidence: string | null }) {
  return <div className="workcpy-analysis-panel">
    {explanation && <p><strong>Explanation:</strong> {explanation}</p>}
    {evidence && <p><strong>Posting Evidence:</strong> {evidence}</p>}
    {!explanation && !evidence && <p>No analysis data available.</p>}
  </div>;
}

function SectionEditor({ section, index, controls: c }: { section: WorkingCopySection; index: number; controls: ProcessingControls }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (key: string) => setExpanded(previous => {
    const next = new Set(previous); if (next.has(key)) next.delete(key); else next.add(key); return next;
  });
  return <div className="workcpy-section-card">
    <div className="workcpy-section-header"><span>{section.company} — {section.position}</span>
      <span>{section.duration} · Score: {section.sectionScore ?? 'N/A'}/10</span>
      <Button onClick={() => toggle('role')}>{expanded.has('role') ? 'Hide Analysis' : 'Show Analysis'}</Button></div>
    {expanded.has('role') && <Evidence explanation={section.sectionExplanation} evidence={section.sectionPostingEvidence} />}
    <div className="workcpy-filter-row">
      {([['Min score:', 'minRelevanceScore'], ['Min items:', 'minItemsKeep'], ['Max items:', 'maxItemsKeep']] as const).map(([label, field]) =>
        <label key={field}>{label}<input type="number" min={0} max={field === 'minRelevanceScore' ? 10 : 20}
          value={section.filterConfig[field]} onChange={event => c.filter(index, { [field]: Number(event.target.value) })} /></label>)}
      <Button onClick={() => c.applyFilter(index)}>Apply Filter</Button>
    </div>
    <ul className="workcpy-items-list">{section.items.map((item, at) => <li key={item.id} className={`workcpy-item-row ${item.kept ? '' : 'removed'}`}>
      <input type="checkbox" aria-label={`Keep bullet ${at + 1}`} checked={item.kept} onChange={() => c.item(index, at, { kept: !item.kept })} />
      <textarea aria-label={`Bullet ${at + 1}`} className="workcpy-item-text" value={item.text}
        onChange={event => c.item(index, at, { text: event.target.value })} rows={Math.max(2, Math.ceil(item.text.length / 60))} />
      <span className="workcpy-item-score">{item.relevanceScore ?? 'N/A'}{item.relevanceScore !== null && item.scoredText !== item.text && ' (stale)'}</span>
      <div className="workcpy-item-actions"><Button disabled={c.rescoring || c.draft?.saving} onClick={() => c.rescore(index, [at])}>Rescore</Button>
        <Button onClick={() => toggle(item.id)}>{expanded.has(item.id) ? 'Hide' : 'Analysis'}</Button></div>
      {expanded.has(item.id) && <Evidence explanation={item.explanation} evidence={item.postingEvidence} />}
    </li>)}</ul>
    <Button disabled={c.rescoring || c.draft?.saving} onClick={() => c.rescore(index)}>Rescore All Items in Section</Button>
  </div>;
}

export function WorkingCopyEditor({ controls: c }: { controls: ProcessingControls }) {
  const copy = c.draft?.value;
  return <section className="rewrite-controls-card">
    <h3>Stage 3: Edit & Review CV (Working Copy)</h3>
    <p>Result working copy for job: {c.id || 'none selected'}. Source CVs are edited separately in CV Data Editor.</p>
    {c.draft && <><p role="status">{c.draft.saving ? 'Saving…' : c.dirty ? 'Unsaved changes' : 'All changes saved'}</p>
      <Button disabled={c.draft.saving} onClick={c.reset}>Reset to saved working copy</Button></>}
    {!c.viewedJob?.result ? <p>Run CV analysis (Stage 2) first to create an editable working copy.</p> :
      c.loading ? <p>Loading working copy...</p> : !copy ? <Button onClick={c.retry}>Retry loading working copy</Button> : <>
        <label>Personal Statement<textarea className="workcpy-statement-textarea" aria-label="Working copy personal statement"
          value={copy.personalStatement} onChange={event => c.statement(event.target.value)} /></label>
        {copy.sections.map((section, index) => <SectionEditor key={`${copy.jobId}:${section.id}`} section={section} index={index} controls={c} />)}
        <div className="workcpy-editor-actions"><Button variant="primary" disabled={c.draft?.saving || c.rescoring} onClick={c.save}>
          {c.draft?.saving ? 'Saving...' : 'Save Working Copy'}</Button>
          <Button variant="success" disabled={c.rendering || c.draft?.saving || c.rescoring} onClick={() => c.render(true)}>
            {c.rendering ? 'Rendering...' : 'Render CV from Working Copy'}</Button>
          <Button onClick={c.showResults}>Inspect Scores & Explanations</Button></div>
      </>}
  </section>;
}
