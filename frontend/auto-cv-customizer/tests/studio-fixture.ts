import type { StudioDraft } from '../src/types/api.generated';
export function studioDraft(): StudioDraft {
  return {
    cv: { schema_version: 1, content_format: 'latex', candidate: { candidate_id: 'charilaos_mylonas', full_name: 'Synthetic', profile: {} },
      personal_statement: 'Original', alternative_statements: [], experience_sections: [],
      cv_template: { template_id: 'my-template', template_path: null, revision: 'a'.repeat(64), experience_section_title: 'Experience' },
      motivation_letter_template: { template_id: 'default_motivation_letter', template_path: null },
      document: { format_version: 1, header_latex: 'Header', sections: [
        { id: 'statement', kind: 'statement', title: 'Statement', enabled: true, page_break_before: false },
        { id: 'raw', kind: 'latex', title: 'Legacy publications', latex: 'Preserved raw publications', enabled: true, page_break_before: false },
      ] } },
    package: { format_version: 1, template_id: 'my-template', name: 'My template', entrypoint: 'main.tex',
      fragments: { statement: 'statement.tex', experience: 'experience.tex', section: 'section.tex', role: 'role.tex', bullet: 'bullet.tex', comment: 'comment.tex', entries: 'entries.tex', entry: 'entry.tex', publications: 'publications.tex', publication: 'publication.tex' },
      files: { 'main.tex': '<header><sections>', 'resume.cls': 'original class', 'statement.tex': '<title><statement>' }, assets: {}, imported_from: null, imported_hashes: {} },
  };
}
