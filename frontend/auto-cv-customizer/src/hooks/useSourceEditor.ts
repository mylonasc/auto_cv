import { useCallback, useEffect, useState } from 'react';
import { useAppState } from '../contexts/AppStateContext';
import { useCVVersion } from './useCVVersion';
import { useTemplates } from './useTemplates';
import { addBullet, removeBullet, editText, editSection, parseCVJSON } from '../domain/cvEditing';
import type { TextTarget } from '../domain/cvEditing';
import type { CVData, ExperienceSection } from '../types/cv';
import type { CVVersionInfo } from '../services/api';

/** Source editing commands, including explicit JSON/visual synchronization. */
export function useSourceEditor() {
  const { state, dispatch } = useAppState();
  const versionsChanged = useCallback((versions: CVVersionInfo[]) => dispatch({ type: 'SET_CV_VERSIONS', payload: versions }), [dispatch]);
  const source = useCVVersion(state.currentCVVersionId || 'master', versionsChanged);
  const templates = useTemplates();
  const [target, setTarget] = useState<TextTarget | null>(null);
  const [text, setText] = useState('');
  const [jsonMode, setJsonMode] = useState(false);
  const [json, setJson] = useState('');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const id = state.currentCVVersionId || 'master';
  useEffect(() => { setTarget(null); setDirty(false); setJsonMode(false); setError(null); setNotice(null); }, [id]);
  useEffect(() => { if (source.data) setJson(JSON.stringify(source.data, null, 4)); }, [source.data]);
  const update = (change: (data: CVData) => CVData) => {
    if (saving) return;
    source.setData(previous => previous && change(previous));
    setDirty(true); setError(null); setNotice(null);
  };
  const run = async (command: () => Promise<void>) => {
    if (saving) return;
    setSaving(true); setError(null); setNotice(null);
    try { await command(); } catch (failure) { setError(String(failure)); }
    finally { setSaving(false); }
  };
  const value = () => jsonMode ? parseCVJSON(json) : source.data;
  const select = (next: TextTarget, content: string) => { setTarget(next); setText(content); };
  return { data: source.data, loading: source.isLoading, saving, dirty, target, text, setText,
    jsonMode, json, error: error || source.error || templates.error, notice,
    id, versions: state.cvVersions, registry: templates.registry,
    select, cancelEdit: () => setTarget(null),
    changeJson: (content: string) => { setJson(content); setDirty(true); setError(null); },
    toggleMode: () => {
      if (saving) return;
      try {
        if (jsonMode) source.setData(parseCVJSON(json));
        else if (source.data) setJson(JSON.stringify(source.data, null, 4));
        setTarget(null); setError(null); setJsonMode(!jsonMode);
      } catch (failure) { setError(String(failure)); }
    },
    chooseVersion: (next: string) => {
      if (!saving && (!dirty || window.confirm('You have unsaved changes. Discard them?')))
        dispatch({ type: 'SET_CURRENT_CV_VERSION', payload: next });
    },
    save: () => run(async () => { const data = value(); if (!data) return;
      await source.save(data); setDirty(false); setNotice('Version saved successfully!'); }),
    create: (name: string) => run(async () => {
      const data = value(), next = name.trim().toLowerCase().replace(/\s+/g, '_');
      if (!data || !next) throw new Error('Enter a version name.');
      await source.create(next, data); dispatch({ type: 'SET_CURRENT_CV_VERSION', payload: next });
    }),
    remove: (next: string) => run(async () => {
      if (next === 'master' || !window.confirm(`Are you sure you want to delete version "${next}"?`)) return;
      await source.remove(next); if (id === next) dispatch({ type: 'SET_CURRENT_CV_VERSION', payload: 'master' });
    }),
    apply: () => { if (!target || saving) return; update(data => editText(data, target, text)); setTarget(null); },
    section: (index: number, patch: Partial<ExperienceSection>) => update(data => editSection(data, index, patch)),
    addSection: () => { setTarget(null); update(data => ({ ...data, experience_sections: [
      { company: 'New Company', position: 'Position', duration: 'Duration', text_items: ['New experience bullet...'] }, ...data.experience_sections] })); },
    removeSection: (index: number) => { if (window.confirm('Delete this entire section?')) {
      setTarget(null); update(data => ({ ...data, experience_sections: data.experience_sections.filter((_, at) => at !== index) })); } },
    addBullet: (index: number) => { setTarget(null); update(data => addBullet(data, index)); },
    removeBullet: (section: number, index: number) => { setTarget(null); update(data => removeBullet(data, section, index)); },
    addAlternative: () => { setTarget(null); update(data => ({ ...data, alternative_statements: ['New alternative personal statement...', ...data.alternative_statements] })); },
    removeAlternative: (index: number) => { setTarget(null); update(data => ({ ...data, alternative_statements: data.alternative_statements.filter((_, at) => at !== index) })); },
    template: (kind: 'cv_template' | 'motivation_letter_template', patch: Record<string, string | null>) =>
      update(data => ({ ...data, [kind]: { ...data[kind], ...patch } })),
    runAnalysis: () => dispatch({ type: 'SET_UI_STATE', payload: { activeTab: 'jobInput' } }),
  };
}
export type SourceEditorControls = ReturnType<typeof useSourceEditor>;
