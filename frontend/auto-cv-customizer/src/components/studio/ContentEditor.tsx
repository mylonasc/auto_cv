import type { CVData } from '../../types/api.generated';
import { move } from '../../domain/studio';
import { Button } from '../common/Primitives';

export function ContentEditor({ cv, change }: { cv: CVData; change: (cv: CVData) => void }) {
  return <details><summary>Statement and experience content</summary>
    <label>Content format <select value={cv.content_format} onChange={e => change({ ...cv, content_format: e.target.value as CVData['content_format'] })}>
      <option value="latex">Authored LaTeX (preserve existing)</option><option value="plain_text">Plain text (escape TeX characters)</option></select></label>
    <label>Personal statement<textarea value={cv.personal_statement} onChange={e => change({ ...cv, personal_statement: e.target.value })} /></label>
    {cv.experience_sections.map((role, at) => <fieldset key={at}><legend>Experience {at + 1}</legend>
      {(['company', 'position', 'duration'] as const).map(key => <label key={key}>{key}<input value={role[key]} onChange={e => change({ ...cv, experience_sections: cv.experience_sections.map((r, i) => i === at ? { ...r, [key]: e.target.value } : r) })} /></label>)}
      {role.text_items.map((text, index) => <label key={index}>Bullet {index + 1}<textarea value={text} onChange={e => change({ ...cv, experience_sections: cv.experience_sections.map((r, i) => i === at ? { ...r, text_items: r.text_items.map((t, j) => j === index ? e.target.value : t) } : r) })} />
        <Button onClick={() => change({ ...cv, experience_sections: cv.experience_sections.map((r, i) => i === at ? { ...r, text_items: r.text_items.filter((_, j) => j !== index) } : r) })}>Delete bullet</Button></label>)}
      <Button onClick={() => change({ ...cv, experience_sections: cv.experience_sections.map((r, i) => i === at ? { ...r, text_items: [...r.text_items, 'New bullet'] } : r) })}>Add bullet</Button>
      <Button disabled={at === 0} onClick={() => change({ ...cv, experience_sections: move(cv.experience_sections, at, -1) })}>Role up</Button>
      <Button disabled={at === cv.experience_sections.length - 1} onClick={() => change({ ...cv, experience_sections: move(cv.experience_sections, at, 1) })}>Role down</Button>
      <Button onClick={() => change({ ...cv, experience_sections: cv.experience_sections.filter((_, i) => i !== at) })}>Delete role</Button>
    </fieldset>)}
    <Button onClick={() => change({ ...cv, experience_sections: [...cv.experience_sections, { company: 'Company', position: 'Role', duration: '', text_items: [] }] })}>Add experience role</Button>
  </details>;
}
