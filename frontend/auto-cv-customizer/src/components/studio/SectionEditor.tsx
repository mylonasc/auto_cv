import type { DocumentComposition, EntryListSection, PublicationListSection } from '../../types/api.generated';
import { duplicateSection, move } from '../../domain/studio';
import { Button } from '../common/Primitives';
import { StructuredListEditor, type StructuredKind } from './StructuredListEditor';
type Section = DocumentComposition['sections'][number];
const id = () => crypto.randomUUID();

function ListEditor({ section, change }: { section: EntryListSection | PublicationListSection; change: (s: Section) => void }) {
  function entries(value: typeof section.entries) { change({ ...section, entries: value } as Section); }
  return <div>{section.entries.map((entry, at) => <fieldset key={entry.id}><legend>Entry {at + 1}</legend>
    <label><input type="checkbox" checked={entry.enabled} onChange={e => entries(section.entries.map(item => item.id === entry.id ? { ...item, enabled: e.target.checked } : item) as typeof section.entries)} />Include entry</label>
    {Object.entries(entry).filter(([key]) => !['id', 'enabled'].includes(key)).map(([key, value]) => <label key={key}>{key}
      <textarea aria-label={`${key} entry ${at + 1}`} value={Array.isArray(value) ? value.join('\n') : String(value)} onChange={e => entries(section.entries.map(item => item.id === entry.id ? { ...item, [key]: Array.isArray(value) ? e.target.value.split('\n') : e.target.value } : item) as typeof section.entries)} />
      {Array.isArray(value) && <small>One {key === 'technologies' ? 'technology' : 'bullet'} per line.</small>}</label>)}
    <Button disabled={at === 0} onClick={() => entries(move<(typeof section.entries)[number]>(section.entries, at, -1) as typeof section.entries)}>Entry up</Button>
    <Button disabled={at === section.entries.length - 1} onClick={() => entries(move<(typeof section.entries)[number]>(section.entries, at, 1) as typeof section.entries)}>Entry down</Button>
    <Button onClick={() => entries([...section.entries, { ...entry, id: id() }] as typeof section.entries)}>Duplicate entry</Button>
    <Button onClick={() => entries(section.entries.filter(item => item.id !== entry.id) as typeof section.entries)}>Delete entry</Button>
  </fieldset>)}<Button onClick={() => entries([...section.entries, section.kind === 'entries' ? { id: id(), name: 'New project', description: '', technologies: [], url: '', bullets: [], enabled: true } : { id: id(), title: 'New publication', authors: '', venue: '', year: '', url: '', enabled: true }] as typeof section.entries)}>Add entry</Button></div>;
}

export function SectionEditor({ document, change }: { document: DocumentComposition; change: (d: DocumentComposition) => void }) {
  const sections = (value: Section[]) => change({ ...document, sections: value });
  const replace = (section: Section) => sections(document.sections.map(item => item.id === section.id ? section : item));
  const KIND_LABELS: Record<Section['kind'], string> = { statement: 'statement', experience: 'experience', entries: 'entries', publications: 'publications', education: 'education', skills: 'skills', item_groups: 'item groups', latex: 'raw LaTeX' };
  function add(kind: Section['kind']) {
    const base = { id: id(), title: kind === 'entries' ? 'Personal projects' : kind === 'publications' ? 'Publications' : kind === 'education' ? 'Education' : kind === 'skills' ? 'Technical Strengths' : kind === 'item_groups' ? 'Other Information' : kind, enabled: true, page_break_before: false };
    sections([...document.sections, (kind === 'latex' ? { ...base, kind, latex: '' } : kind === 'entries' || kind === 'publications' || kind === 'education' ? { ...base, kind, entries: [] } : { ...base, kind, groups: [] }) as Section]);
  }
  return <section><h3>Section outline</h3>
    {document.sections.map((section, at) => <details key={section.id} data-testid="studio-section"><summary>{at + 1}. {section.title}{!section.enabled && ' (hidden)'}</summary>
      <label>Section title<input value={section.title} onChange={e => replace({ ...section, title: e.target.value })} /></label>
      <label><input type="checkbox" checked={section.enabled} onChange={e => replace({ ...section, enabled: e.target.checked })} />Include section</label>
      <label><input type="checkbox" checked={section.page_break_before} onChange={e => replace({ ...section, page_break_before: e.target.checked })} />Page break before</label>
      <Button disabled={at === 0} onClick={() => sections(move(document.sections, at, -1))}>Section up</Button>
      <Button disabled={at === document.sections.length - 1} onClick={() => sections(move(document.sections, at, 1))}>Section down</Button>
      <Button disabled={section.kind === 'statement' || section.kind === 'experience'} onClick={() => sections([...document.sections, duplicateSection(section, id)])}>Duplicate section</Button>
      <Button onClick={() => sections(document.sections.filter(item => item.id !== section.id))}>Delete section</Button>
      {section.kind === 'latex' && <label>Raw section LaTeX<textarea rows={12} value={section.latex} onChange={e => replace({ ...section, latex: e.target.value })} /><small>The raw source owns its printed heading and any original page breaks.</small></label>}
      {(section.kind === 'entries' || section.kind === 'publications') && <ListEditor section={section} change={replace} />}
      {(section.kind === 'education' || section.kind === 'skills' || section.kind === 'item_groups') && <StructuredListEditor section={section as Section & { kind: StructuredKind }} change={replace} />}
    </details>)}
    {(['statement', 'experience', 'entries', 'publications', 'education', 'skills', 'item_groups', 'latex'] as const).map(kind => <Button key={kind} disabled={(kind === 'statement' || kind === 'experience') && document.sections.some(s => s.kind === kind)} onClick={() => add(kind)}>Add {KIND_LABELS[kind]}</Button>)}
  </section>;
}
