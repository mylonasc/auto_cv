import type { SourceEditorControls } from '../../hooks/useSourceEditor';

export function SourceTemplates({ controls: c }: { controls: SourceEditorControls }) {
  const data = c.data;
  if (!data) return null;
  return <section className="editor-section-block"><div className="panel-header"><h3>Template Selection</h3></div>
    {(['cv_template', 'motivation_letter_template'] as const).map(kind => {
      const registry = kind === 'cv_template' ? c.registry.cv_templates : c.registry.motivation_letter_templates;
      return <div className="section-group" key={kind}><div className="subtitle-row">
        <select className="inline-input" aria-label={kind === 'cv_template' ? 'Source CV template' : 'Motivation template'}
          value={data[kind].template_id} onChange={event => c.template(kind, { template_id: event.target.value, template_path: null })}>
          {!(data[kind].template_id in registry) && <option value={data[kind].template_id}>{data[kind].template_id} (custom or unavailable)</option>}
          {Object.keys(registry).map(id => <option key={id} value={id}>{id}</option>)}</select>
        <input className="inline-input-right" placeholder={kind === 'cv_template' ? 'CV template path' : 'Motivation template path'}
          value={data[kind].template_path || ''} onChange={event => c.template(kind, { template_path: event.target.value || null })} /></div>
        {kind === 'cv_template' && <input className="inline-input" placeholder="Experience section title"
          value={data.cv_template.experience_section_title} onChange={event => c.template(kind, { experience_section_title: event.target.value })} />}
      </div>;
    })}
    <label>CV text format<select aria-label="CV text format" value={data.content_format} onChange={event => c.contentFormat(event.target.value as 'latex' | 'plain_text')}>
      <option value="latex">Authored LaTeX (legacy)</option><option value="plain_text">Plain text (escaped for LaTeX)</option></select></label>
    <p>Choose the format of the existing statements and experience. Switching does not convert their text. Template markup is unchanged.</p>
  </section>;
}
