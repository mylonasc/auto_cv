import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useStudio } from '../../contexts/StudioContext';
import { useTemplates } from '../../hooks/useTemplates';
import { starterLabel, defaultStarter } from '../../domain/studio';
import { ContentEditor } from './ContentEditor';
import { SectionEditor } from './SectionEditor';
import { TemplateSourceEditor } from './TemplateSourceEditor';
import { StudioPreviewPane } from './StudioPreviewPane';
import { Button } from '../common/Primitives';
import './studio.css';

export default function StudioTab() {
  const c = useStudio();
  const dispatch = c.dispatch;
  const { registry } = useTemplates();
  const starters = useMemo(() => Object.keys(registry.cv_templates), [registry.cv_templates]);
  // Align the selection once the registry arrives; prefer the wide starter.
  useEffect(() => {
    if (starters.length && !starters.includes(c.starter)) c.setStarter(defaultStarter(undefined, starters));
  }, [starters]); // eslint-disable-line react-hooks/exhaustive-deps
  const [file, setFile] = useState('');
  // Load only when this feature is first opened, never at application startup.
  useEffect(() => { void c.refresh(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const draft = c.state.draft;
  const selected = draft && file in draft.package.files ? file : draft ? Object.keys(draft.package.files)[0] : '';
  // Stable callbacks read the latest draft through a ref so the memoized
  // editor/preview panes are not invalidated by every keystroke elsewhere.
  const draftRef = useRef(draft);
  useLayoutEffect(() => { draftRef.current = draft; }, [draft]);
  const previewRef = useRef(c.preview);
  const reportRef = useRef(c.report);
  useLayoutEffect(() => { previewRef.current = c.preview; reportRef.current = c.report; });
  const renameTemplate = useCallback((name: string) => {
    const current = draftRef.current;
    if (current) dispatch({ type: 'package', package: { ...current.package, name } });
  }, [dispatch]);
  const editTemplateFile = useCallback((name: string, value: string) => {
    const current = draftRef.current;
    if (current) dispatch({ type: 'package', package: { ...current.package, files: { ...current.package.files, [name]: value } } });
  }, [dispatch]);
  const requestPreview = useCallback(() => { void previewRef.current.preview(); }, []);
  const requestCheck = useCallback(() => { void reportRef.current.check(); }, []);
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
      <TemplateSourceEditor files={draft.package.files} assets={draft.package.assets} selected={selected} onSelectFile={setFile}
        templateName={draft.package.name} onRenameTemplate={renameTemplate} onEditFile={editTemplateFile} />
    </div><StudioPreviewPane previewBusy={c.preview.busy} previewOutdated={c.preview.outdated} previewError={c.preview.error}
      reportBusy={c.report.busy} reportError={c.report.error} report={c.report.report} reportOutdated={c.report.outdated} pdfUrl={c.preview.url}
      onPreview={requestPreview} onCheck={requestCheck} />
    </div></>}
  </div>;
}
