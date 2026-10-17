import { useState } from 'react';
import type { SourceEditorControls } from '../../hooks/useSourceEditor';
import { Button } from '../common/Primitives';

export function SourceVersionList({ controls: c }: { controls: SourceEditorControls }) {
  const [showNew, setShowNew] = useState(false);
  const [name, setName] = useState('');
  return <aside className="editor-sidebar"><div className="sidebar-header"><h3>CV Versions</h3>
    <Button title="New Version" disabled={c.saving} onClick={() => setShowNew(!showNew)}>➕</Button></div>
    {showNew && <div className="new-version-input"><input placeholder="Version name..." value={name} onChange={event => setName(event.target.value)} />
      <Button variant="primary" disabled={c.saving} onClick={() => c.create(name)}>Create</Button></div>}
    <div className="version-list">{c.versions.map(version => <div key={version.id} className={`version-item ${c.id === version.id ? 'active' : ''}`}>
      <Button disabled={c.saving} onClick={() => c.chooseVersion(version.id)}><span className="version-name">{version.name}</span>
        <span className="version-date">{new Date(version.last_modified * 1000).toLocaleDateString()}</span></Button>
      {version.id !== 'master' && <Button disabled={c.saving} aria-label={`Delete version ${version.name}`} onClick={() => c.remove(version.id)}>✕</Button>}
    </div>)}</div>
  </aside>;
}
