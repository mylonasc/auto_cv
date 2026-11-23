import React from 'react';
import { Button } from '../common/Primitives';
import { PdfFrame } from '../common/PdfFrame';
import type { StudioPreviewReport } from '../../types/api.generated';

/** PDF preview pane. Memoized so editor keystrokes do not reconcile the pane
 * (or disturb the iframe); only preview/report state changes re-render it. */
function StudioPreviewPaneView({ previewBusy, previewOutdated, previewError, reportBusy, reportError, report, reportOutdated, pdfUrl, onPreview, onCheck }: {
  previewBusy: boolean;
  previewOutdated: boolean;
  previewError: string;
  reportBusy: boolean;
  reportError: string;
  report: StudioPreviewReport | null;
  reportOutdated: boolean;
  pdfUrl: string | null;
  onPreview: () => void;
  onCheck: () => void;
}) {
  return <aside className="studio-preview">
    <Button variant="primary" disabled={previewBusy} onClick={onPreview}>{previewBusy ? 'Compiling preview…' : 'Preview PDF'}</Button>
    <Button disabled={reportBusy} onClick={onCheck}>{reportBusy ? 'Checking layout…' : 'Check layout quality'}</Button>
    <p>No save, analysis or model call required. Unsaved CV and template edits are compiled together.</p>
    {previewOutdated && <p role="status">Preview outdated — draft has changed.</p>}
    {previewError && <pre role="alert">{previewError}</pre>}
    {reportError && <pre role="alert">{reportError}</pre>}
    {report && <div role="status">
      <p>Layout quality: {report.pages} pages, {report.words} words, {report.overfull_count} overfull warnings, {report.overlaps.length} overlaps, {report.outside_page.length} outside page, {report.missing_glyphs.length} missing glyphs.{reportOutdated ? ' (outdated — draft has changed)' : ''}</p>
      {!!(report.overfulls.length || report.overlaps.length || report.outside_page.length || report.missing_glyphs.length) && <details><summary>Quality details</summary>
        {report.overfulls.map((item, at) => <p key={at}>Overfull {item.kind} +{item.amount_pt}pt, lines {item.start_line}–{item.end_line}: {item.excerpt}</p>)}
        {report.overlaps.map((item, at) => <p key={at}>Overlap p{item.page + 1}: “{item.first}” × “{item.second}” ({item.area}pt²)</p>)}
        {report.outside_page.map((item, at) => <p key={at}>Outside page p{item.page + 1} {item.edge}: “{item.text}” (+{item.amount_pt}pt)</p>)}
        {report.missing_glyphs.map((item, at) => <p key={at}>{item}</p>)}
        {Object.entries(report.omitted).map(([key, count]) => <p key={key}>…and {count} more {key} (bounded display).</p>)}
      </details>}
    </div>}
    {pdfUrl ? <><a href={pdfUrl} target="_blank" rel="noreferrer">Open PDF in new tab</a><PdfFrame url={pdfUrl} title="Studio PDF preview" /></> : <p>Click Preview PDF to compile this draft.</p>}
    <small>Diagnostics refer to captured source files or temp.tex (the assembled CV). Trusted local use only; this is not an untrusted-TeX sandbox.</small>
  </aside>;
}

export const StudioPreviewPane = React.memo(StudioPreviewPaneView);
