import { useEffect, useState } from 'react';
import { useStudio } from '../../contexts/StudioContext';
import { useTemplates } from '../../hooks/useTemplates';
import { starterLabel, defaultStarter } from '../../domain/studio';
import { ContentEditor } from './ContentEditor';
import { SectionEditor } from './SectionEditor';
import { Button } from '../common/Primitives';
import './studio.css';
import { PdfFrame } from '../common/PdfFrame';

export default function StudioTab() {
  const c = useStudio();
  const { registry } = useTemplates();
  const starters = Object.keys(registry.cv_templates);
  // Align the selection once the registry arrives; prefer the wide starter.
  useEffect(() => {
    if (starters.length && !starters.includes(c.starter)) c.setStarter(defaultStarter(undefined, starters));
  }, [starters]); // eslint-disable-line react-hooks/exhaustive-deps
  const [file, setFile] = useState('');
  // Load only when this feature is first opened, never at application startup.
  useEffect(() => { void c.refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const draft = c.state.draft;
  const selected = draft && file in draft.package.files ? file : draft ? Object.keys(draft.package.files)[0] : '';
  return <div className="studio"><h2>Template Studio</h2>
    <p>Trusted local LaTeX authoring. Drafts survive tab switches, not a page reload. Original CVs and built-in templates remain unchanged.</p>
    {c.error && <pre role="alert">{c.error}</pre>}{c.notice && <p role="status">{c.notice}</p>}
    <div className="studio-toolbar"><label>Source CV<select value={c.source} onChange={e => c.setSource(e.target.value)}><option value="master">master</option>{c.versions.filter(v => v.id !== 'master').map(v => <option key={v.id} value={v.id}>{v.name}</option>)}</select></label>
      <label>Starter template (legacy CVs)<select aria-label="Starter template" value={starters.includes(c.starter) ? c.starter : ''} onChange={e => c.setStarter(e.target.value)}>{starters.map(id => <option key={id} value={id}>{starterLabel(id)}</option>)}</select></label>
      <label>New template ID (legacy import)<input value={c.templateID} onChange={e => c.setTemplateID(e.target.value)} /></label>
      <Button disabled={c.busy} onClick={c.load}>Load / import draft</Button>
    </div>
    {draft && <><div className="studio-toolbar">
      <span>CV: {c.cvDirty ? 'unsaved' : 'saved'} · Template: {c.packageDirty ? 'unsaved' : 'saved'}</span>
      <Button disabled={c.busy || !c.packageDirty} onClick={c.saveTemplate}>Save template revision</Button>
      <Button disabled={c.busy} onClick={c.reloadTemplate}>Reload latest saved template</Button>
      <label>New CV version ID<input value={c.target} onChange={e => c.setTarget(e.target.value)} /></label>
      <Button disabled={c.busy || c.packageDirty} onClick={c.saveCV}>Save new CV version</Button>
    </div><div className="studio-columns"><div className="studio-editors">
      <ContentEditor cv={draft.cv} change={c.editCV} />
      {draft.cv.document && <SectionEditor document={draft.cv.document} change={document => c.editCV({ ...draft.cv, document })} />}
      <details><summary>Header LaTeX</summary><textarea aria-label="Header LaTeX" rows={12} value={draft.cv.document?.header_latex ?? ''} onChange={e => draft.cv.document && c.editCV({ ...draft.cv, document: { ...draft.cv.document, header_latex: e.target.value } })} /></details>
      <details><summary>All template sources (.tex / .cls / .sty)</summary>
        <label>Template name<input value={draft.package.name} onChange={e => c.dispatch({ type: 'package', package: { ...draft.package, name: e.target.value } })} /></label>
        <label>Source file<select aria-label="Source file" value={selected} onChange={e => setFile(e.target.value)}>{Object.keys(draft.package.files).map(name => <option key={name}>{name}</option>)}</select></label>
        <textarea aria-label="Template source" spellCheck={false} rows={22} value={draft.package.files[selected] ?? ''} onChange={e => c.dispatch({ type: 'package', package: { ...draft.package, files: { ...draft.package.files, [selected]: e.target.value } } })} />
        <small>Captured assets (read-only): {Object.keys(draft.package.assets).join(', ') || 'none'}. Required placeholders are validated on save.</small>
      </details>
    </div><aside className="studio-preview">
      <Button variant="primary" disabled={c.preview.busy} onClick={c.preview.preview}>{c.preview.busy ? 'Compiling preview…' : 'Preview PDF'}</Button>
      <Button disabled={c.report.busy} onClick={c.report.check}>{c.report.busy ? 'Checking layout…' : 'Check layout quality'}</Button>
      <p>No save, analysis or model call required. Unsaved CV and template edits are compiled together.</p>
      {c.preview.outdated && <p role="status">Preview outdated — draft has changed.</p>}
      {c.preview.error && <pre role="alert">{c.preview.error}</pre>}
      {c.report.error && <pre role="alert">{c.report.error}</pre>}
      {c.report.report && <div role="status">
        <p>Layout quality: {c.report.report.pages} pages, {c.report.report.words} words, {c.report.report.overfull_count} overfull warnings, {c.report.report.overlaps.length} overlaps, {c.report.report.outside_page.length} outside page, {c.report.report.missing_glyphs.length} missing glyphs.{c.report.outdated ? ' (outdated — draft has changed)' : ''}</p>
        {!!(c.report.report.overfulls.length || c.report.report.overlaps.length || c.report.report.outside_page.length || c.report.report.missing_glyphs.length) && <details><summary>Quality details</summary>
          {c.report.report.overfulls.map((item, at) => <p key={at}>Overfull {item.kind} +{item.amount_pt}pt, lines {item.start_line}–{item.end_line}: {item.excerpt}</p>)}
          {c.report.report.overlaps.map((item, at) => <p key={at}>Overlap p{item.page + 1}: “{item.first}” × “{item.second}” ({item.area}pt²)</p>)}
          {c.report.report.outside_page.map((item, at) => <p key={at}>Outside page p{item.page + 1} {item.edge}: “{item.text}” (+{item.amount_pt}pt)</p>)}
          {c.report.report.missing_glyphs.map((item, at) => <p key={at}>{item}</p>)}
          {Object.entries(c.report.report.omitted).map(([key, count]) => <p key={key}>…and {count} more {key} (bounded display).</p>)}
        </details>}
      </div>}
      {c.preview.url ? <><a href={c.preview.url} target="_blank" rel="noreferrer">Open PDF in new tab</a><PdfFrame url={c.preview.url} title="Studio PDF preview" /></> : <p>Click Preview PDF to compile this draft.</p>}
      <small>Diagnostics refer to captured source files or temp.tex (the assembled CV). Trusted local use only; this is not an untrusted-TeX sandbox.</small>
    </aside></div></>}
  </div>;
}
