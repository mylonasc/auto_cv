/** Retain safe backend validation/template details rather than only Axios status. */
export function httpErrorMessage(status: number | undefined, body: unknown, fallback: string): string {
  const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object';
  const detail = object(body) ? body.detail : undefined;
  const text = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((item: unknown) => {
    if (!object(item) || typeof item.msg !== 'string') return '';
    const location = Array.isArray(item.loc) ? item.loc.filter(part => typeof part === 'string' || typeof part === 'number').join('.') : '';
    return `${location ? `${location}: ` : ''}${item.msg}`;
  }).filter(Boolean).join('; ') : '';
  const diagnostics = object(body) && typeof body.diagnostics === 'string' ? `\n${body.diagnostics.slice(0, 8192)}` : '';
  return `${status ? `HTTP ${status}: ` : ''}${text || fallback}${diagnostics}`;
}
