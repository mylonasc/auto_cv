import type { SourceEditorControls } from '../../hooks/useSourceEditor';
import { Button } from '../common/Primitives';

export function SourceContent({ controls: c }: { controls: SourceEditorControls }) {
  const data = c.data;
  if (!data) return null;
  return <>
    <section className="editor-section-block"><div className="panel-header"><h3>Personal Statements</h3></div>
      <div className="personal-statement-group"><div className="group-label">Master Statement</div>
        <div className={`item-edit-card ${c.target?.type === 'personal' ? 'selected' : ''}`}>
          <Button aria-label="Edit master statement" onClick={() => c.select({ type: 'personal' }, data.personal_statement)}><span className="item-text-review">{data.personal_statement.substring(0, 100)}...</span></Button></div>
        <div className="group-label-row"><span>Alternative Statements (for AI rewriting)</span><Button onClick={c.addAlternative}>+ Add Alternative</Button></div>
        <div className="alternatives-list">{data.alternative_statements.map((text, index) => <div className="item-edit-card" key={index}>
          <Button aria-label={`Edit alternative ${index + 1}`} onClick={() => c.select({ type: 'alternative', itemIdx: index }, text)}><span className="item-text-review">{text.substring(0, 80)}...</span></Button>
          <Button aria-label={`Delete alternative ${index + 1}`} onClick={() => c.removeAlternative(index)}>✕</Button></div>)}</div>
      </div>
    </section>
    <section className="editor-section-block"><div className="panel-header"><h3>Experience Sections</h3><Button onClick={c.addSection}>+ Add Section</Button></div>
      {data.experience_sections.map((section, index) => <div className="section-group" key={index}><div className="section-title">
        <div className="title-row"><input className="inline-input-bold" aria-label={`Company ${index + 1}`} value={section.company} onChange={event => c.section(index, { company: event.target.value })} />
          <Button aria-label={`Delete section ${index + 1}`} onClick={() => c.removeSection(index)}>✕</Button></div>
        <div className="subtitle-row"><input className="inline-input" aria-label={`Position ${index + 1}`} value={section.position} onChange={event => c.section(index, { position: event.target.value })} />
          <input className="inline-input-right" aria-label={`Duration ${index + 1}`} value={section.duration} onChange={event => c.section(index, { duration: event.target.value })} /></div></div>
        <div className="items-list">{section.text_items.map((text, at) => <div className="item-edit-card" key={at}>
          <Button aria-label={`Edit source bullet ${at + 1} in section ${index + 1}`} onClick={() => c.select({ type: 'experience', sectionIdx: index, itemIdx: at }, text)}><span className="item-text-review">{text.substring(0, 100)}...</span></Button>
          <Button aria-label={`Delete bullet ${at + 1}`} onClick={() => c.removeBullet(index, at)}>✕</Button></div>)}
          <Button onClick={() => c.addBullet(index)}>+ Add Bullet</Button></div>
      </div>)}
    </section>
  </>;
}

export function SourceTextEditor({ controls: c }: { controls: SourceEditorControls }) {
  return <div className="edit-panel">{c.target ? <><div className="edit-header"><h3>
    {c.target.type === 'personal' ? 'Edit Master Personal Statement' : c.target.type === 'alternative' ? 'Edit Alternative Statement' : 'Edit Experience Item'}
  </h3></div><textarea className="edit-textarea" aria-label="Selected source text" value={c.text} onChange={event => c.setText(event.target.value)} rows={12} />
    <div className="edit-actions"><Button onClick={c.cancelEdit}>Cancel</Button><Button variant="primary" disabled={c.saving} onClick={c.apply}>Apply Edit</Button></div></> :
    <div className="no-selection"><p>Select an item from the left to edit it.</p><p>Remember to click Save Version to persist your changes to the server.</p></div>}</div>;
}
