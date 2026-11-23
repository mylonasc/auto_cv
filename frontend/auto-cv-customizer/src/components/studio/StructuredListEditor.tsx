import type { DocumentComposition } from '../../types/api.generated';
import { move } from '../../domain/studio';
import { Button } from '../common/Primitives';

type Section = DocumentComposition['sections'][number];
export type StructuredKind = 'education' | 'skills' | 'item_groups';
const id = () => crypto.randomUUID();

const LIST_KEY: Record<StructuredKind, 'entries' | 'groups'> = {
  education: 'entries', skills: 'groups', item_groups: 'groups',
};

function blank(kind: StructuredKind): Record<string, unknown> {
  if (kind === 'education') return { id: id(), institution: 'New institution', dates: '', degree: '', details: [], enabled: true };
  if (kind === 'skills') return { id: id(), name: 'New skill', items: '', rating: null, enabled: true };
  return { id: id(), title: 'New group', items: [], enabled: true };
}

type Item = { id: string; enabled: boolean } & Record<string, unknown>;
const ITEM_NOUNS: Record<StructuredKind, string> = { education: 'education entry', skills: 'skill', item_groups: 'group' };

function fieldHint(kind: StructuredKind, key: string, value: unknown): string | null {
  if (Array.isArray(value)) return key === 'details' || key === 'items' ? 'One per line.' : 'One per line.';
  if (key === 'rating') return 'Empty means unrated (no dots); 0–6 shows that many filled dots.';
  if (kind === 'education' && key === 'degree') return 'Authorship markup such as \\textsc is preserved in LaTeX mode.';
  return null;
}

/** Generic editor for education/skills/item-group lists; ListEditor keeps projects/publications. */
export function StructuredListEditor({ section, change }: { section: Section & { kind: StructuredKind }; change: (s: Section) => void }) {
  const key = LIST_KEY[section.kind];
  const list = (section as unknown as Record<string, Item[]>)[key] ?? [];
  function update(value: Item[]) { change({ ...section, [key]: value } as Section); }
  function setItem(item: Item, field: string, fieldValue: unknown) {
    update(list.map(candidate => candidate.id === item.id ? { ...candidate, [field]: fieldValue } : candidate));
  }
  return <div>{list.map((entry, at) => <fieldset key={entry.id}><legend>{ITEM_NOUNS[section.kind]} {at + 1}</legend>
    <label><input type="checkbox" checked={entry.enabled} onChange={e => setItem(entry, 'enabled', e.target.checked)} />Include {ITEM_NOUNS[section.kind]}</label>
    {Object.entries(entry).filter(([field]) => !['id', 'enabled'].includes(field)).map(([field, value]) => <label key={field}>{field}
      {field === 'rating'
        ? <input aria-label={`${field} ${ITEM_NOUNS[section.kind]} ${at + 1}`} type="number" min={0} max={6} value={typeof value === 'number' ? value : ''} onChange={e => setItem(entry, field, e.target.value === '' ? null : Math.max(0, Math.min(6, Math.floor(Number(e.target.value)))))} />
        : <textarea aria-label={`${field} ${ITEM_NOUNS[section.kind]} ${at + 1}`} value={Array.isArray(value) ? (value as unknown[]).join('\n') : String(value ?? '')} onChange={e => setItem(entry, field, Array.isArray(value) ? e.target.value.split('\n') : e.target.value)} />}
      {fieldHint(section.kind, field, value) && <small>{fieldHint(section.kind, field, value)}</small>}</label>)}
    <Button disabled={at === 0} onClick={() => update(move(list, at, -1))}>{ITEM_NOUNS[section.kind]} up</Button>
    <Button disabled={at === list.length - 1} onClick={() => update(move(list, at, 1))}>{ITEM_NOUNS[section.kind]} down</Button>
    <Button onClick={() => update([...list, { ...entry, id: id() }])}>Duplicate {ITEM_NOUNS[section.kind]}</Button>
    <Button onClick={() => update(list.filter(item => item.id !== entry.id))}>Delete {ITEM_NOUNS[section.kind]}</Button>
  </fieldset>)}<Button onClick={() => update([...list, blank(section.kind) as Item])}>Add {ITEM_NOUNS[section.kind]}</Button></div>;
}
