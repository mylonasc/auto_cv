export function PdfFrame({ url, title = 'PDF Preview', className = 'pdf-preview-frame' }: { url: string; title?: string; className?: string }) {
  return <iframe title={title} src={url} className={className} />;
}
