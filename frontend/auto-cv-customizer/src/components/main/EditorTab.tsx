import { useSourceEditor } from '../../hooks/useSourceEditor';
import { Button } from '../common/Primitives';
import { SourceVersionList } from '../editor/SourceVersionList';
import { SourceTemplates } from '../editor/SourceTemplates';
import { SourceContent, SourceTextEditor } from '../editor/SourceContent';
import './EditorTab.css';

export default function EditorTab() {
  const c = useSourceEditor();
  if (c.loading) return <div className="editor-tab"><p>Loading CV data...</p></div>;
  return <div className="editor-tab"><SourceVersionList controls={c} /><div className="editor-main">
    <header className="editor-header"><div className="header-title"><h2>Editing: {c.versions.find(version => version.id === c.id)?.name || c.id}</h2>
      <p>Source CV version — saving here changes inputs for future analyses, not a result working copy.</p>
      {c.dirty && <span className="dirty-indicator">• Unsaved Changes</span>}</div>
      <div className="editor-actions"><Button variant={c.jsonMode ? 'primary' : 'secondary'} disabled={c.saving} onClick={c.toggleMode}>
        {c.jsonMode ? 'Visual Mode' : '{ } JSON Mode'}</Button>
        <Button variant="success" disabled={!c.dirty || c.saving} onClick={c.save}>{c.saving ? 'Saving...' : '💾 Save Version'}</Button>
        <Button onClick={c.runAnalysis}>🔄 Run Analysis</Button></div></header>
    {c.error && <p role="alert">{c.error}</p>}{c.notice && <p role="status">{c.notice}</p>}
    <fieldset disabled={c.saving} className="source-editor-fields">
      {c.jsonMode ? <div className="json-editor-container"><textarea className="json-textarea" aria-label="Source CV JSON"
        value={c.json} onChange={event => c.changeJson(event.target.value)} spellCheck={false} /></div> :
        <div className="editor-content"><div className="sections-panel"><SourceTemplates controls={c} /><SourceContent controls={c} /></div><SourceTextEditor controls={c} /></div>}
    </fieldset>
  </div></div>;
}
