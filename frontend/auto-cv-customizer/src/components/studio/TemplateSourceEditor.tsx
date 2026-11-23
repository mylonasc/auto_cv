import React from 'react';

/** All managed text sources. Memoized so content edits elsewhere in Studio do
 * not re-render the (potentially large) source textarea or the file list. */
function TemplateSourceEditorView({ files, assets, selected, onSelectFile, templateName, onRenameTemplate, onEditFile }: {
  files: Record<string, string>;
  assets: Record<string, unknown>;
  selected: string;
  onSelectFile: (name: string) => void;
  templateName: string;
  onRenameTemplate: (name: string) => void;
  onEditFile: (name: string, value: string) => void;
}) {
  return <details><summary>All template sources (.tex / .cls / .sty)</summary>
    <label>Template name<input value={templateName} onChange={e => onRenameTemplate(e.target.value)} /></label>
    <label>Source file<select aria-label="Source file" value={selected} onChange={e => onSelectFile(e.target.value)}>{Object.keys(files).map(name => <option key={name}>{name}</option>)}</select></label>
    <textarea aria-label="Template source" spellCheck={false} rows={22} value={files[selected] ?? ''} onChange={e => onEditFile(selected, e.target.value)} />
    <small>Captured assets (read-only): {Object.keys(assets).join(', ') || 'none'}. Required placeholders are validated on save.</small>
  </details>;
}

export const TemplateSourceEditor = React.memo(TemplateSourceEditorView);
