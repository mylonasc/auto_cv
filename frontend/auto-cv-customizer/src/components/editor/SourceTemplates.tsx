import type { SourceEditorControls } from '../../hooks/useSourceEditor';

export function SourceTemplates({ controls: c }: { controls: SourceEditorControls }) {
  const data = c.data;
  if (!data) return null;
  return <section className="editor-section-block"><div className="panel-header"><h3>Template Selection</h3></div>
    {(['cv_template', 'motivation_letter_template'] as const).map(kind => {
      const registry = kind === 'cv_template' ? c.registry.cv_templates : c.registry.motivation_letter_templates;
      return <div className="section-group" key={kind}><div className="subtitle-row">
        <select className="inline-input" aria-label={kind === 'cv_template' ? 'Source CV template' : 'Motivation template'}
          value={data[kind].template_id} onChange={event => c.template(kind, { template_id: event.target.value, template_path: registry[event.target.value] || null })}>
          {Object.keys(registry).map(id => <option key={id} value={id}>{id}</option>)}</select>
        <input className="inline-input-right" placeholder={kind === 'cv_template' ? 'CV template path' : 'Motivation template path'}
          value={data[kind].template_path || ''} onChange={event => c.template(kind, { template_path: event.target.value || null })} /></div>
        {kind === 'cv_template' && <input className="inline-input" placeholder="Experience section title"
          value={data.cv_template.experience_section_title} onChange={event => c.template(kind, { experience_section_title: event.target.value })} />}
      </div>;
    })}
  </section>;
}
