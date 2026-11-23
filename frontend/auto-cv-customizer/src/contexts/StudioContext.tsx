import { createContext, useContext, useEffect, useLayoutEffect, useReducer, useRef, useState, type ReactNode } from 'react';
import { apiService } from '../services/api';
import { initialStudio, studioReducer } from '../domain/studio';
import type { CVData, StudioDraft } from '../types/api.generated';
import type { CVVersionInfo } from '../services/api';
import { useStudioPreview } from '../hooks/useStudioPreview';
import { useStudioReport } from '../hooks/useStudioReport';

function useStudioController() {
  const [state, dispatch] = useReducer(studioReducer, initialStudio);
  const current = useRef(state);
  useLayoutEffect(() => { current.current = state; }, [state]);
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [versions, setVersions] = useState<CVVersionInfo[]>([]);
  const [source, setSource] = useState('master');
  const [target, setTarget] = useState('studio');
  const [templateID, setTemplateID] = useState('my-template');
  const cvDirty = !!state.draft && state.cvDirty;
  const packageDirty = !!state.draft && state.packageDirty;
  const preview = useStudioPreview(state.draft, { generation: state.generation, edit: state.edit });
  const report = useStudioReport(state.draft, { generation: state.generation, edit: state.edit });
  const [starter, setStarter] = useState('template2');
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => { if (cvDirty || packageDirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [cvDirty, packageDirty]);
  async function run(operation: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError(''); setNotice('');
    try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { lock.current = false; setBusy(false); }
  }
  const refresh = () => run(async () => setVersions(await apiService.listCVVersions()));
  const load = () => {
    if ((cvDirty || packageDirty) && !window.confirm('Discard the current Studio drafts and load another CV?')) return;
    return run(async () => {
      const edit = current.current.edit;
      const cv = await apiService.getCVVersion(source);
      let draft: StudioDraft;
      if (cv.document && cv.cv_template.revision) {
        const saved = await apiService.getStudioTemplate(cv.cv_template.template_id, cv.cv_template.revision);
        draft = { cv, package: saved.package };
      } else draft = await apiService.importStudio({ cv, template_id: templateID, name: templateID, source_template: starter });
      dispatch({ type: 'load', draft, saved: !!cv.document, edit });
    });
  };
  const saveTemplate = () => run(async () => {
    const captured = current.current;
    if (!captured.draft) return;
    const value = await apiService.saveStudioTemplate({ package: captured.draft.package, expected_revision: captured.expected });
    dispatch({ type: 'templateSaved', value, generation: captured.generation });
    setNotice('Template revision saved. Save a new CV version separately to pin it.');
  });
  const reloadTemplate = () => {
    if (!window.confirm('Discard template edits and load its latest saved revision? CV content is retained.')) return;
    return run(async () => {
      const captured = current.current;
      if (!captured.draft) return;
      const value = await apiService.getStudioTemplate(captured.draft.package.template_id);
      dispatch({ type: 'templateReload', value, generation: captured.generation, edit: captured.edit });
    });
  };
  const saveCV = () => run(async () => {
    const captured = current.current;
    if (!captured.draft || !captured.packageBaseline || captured.packageDirty) throw new Error('Save the template draft first.');
    if (!target.trim() || target === 'master' || target === source) throw new Error('Choose a new CV version ID; Studio never overwrites the selected original.');
    const cv = await apiService.createCVVersion(target, captured.draft.cv);
    dispatch({ type: 'cvSaved', cv, generation: captured.generation });
    setNotice(`Created CV version ${target}. Select it in Job Description when ready; it is not activated automatically.`);
    setVersions(await apiService.listCVVersions());
  });
  return { state, dispatch, busy, error, notice, preview, report, starter, setStarter, versions, source, setSource, target, setTarget, templateID, setTemplateID,
    cvDirty, packageDirty, refresh, load, saveTemplate, reloadTemplate, saveCV,
    editCV: (cv: CVData) => dispatch({ type: 'cv', cv }) };
}
const StudioContext = createContext<ReturnType<typeof useStudioController> | null>(null);
export function StudioProvider({ children }: { children: ReactNode }) {
  return <StudioContext.Provider value={useStudioController()}>{children}</StudioContext.Provider>;
}
export function useStudio() {
  const context = useContext(StudioContext);
  if (!context) throw new Error('StudioProvider missing');
  return context;
}
