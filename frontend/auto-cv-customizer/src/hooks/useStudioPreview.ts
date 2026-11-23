/** TRF-04: provider-lifetime PDF requests and object URL ownership.
 *
 * Staleness is tracked with the reducer's {generation, edit} stamp instead of
 * serializing the whole draft on every render: edits only ever bump the
 * counters, so a mismatch reliably means "newer content exists". The server
 * still validates the effective input and returns its identity header.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { StudioDraft } from '../types/api.generated';
import { apiService } from '../services/api';

export interface StudioStamp { generation: number; edit: number }
export const sameStamp = (a: StudioStamp, b: StudioStamp) => a.generation === b.generation && a.edit === b.edit;

export function useStudioPreview(draft: StudioDraft | null, stamp: StudioStamp) {
  const current = useRef(stamp);
  useLayoutEffect(() => { current.current = stamp; }, [stamp]);
  const active = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ blob: Blob; identity: string; stamp: StudioStamp } | null>(null);
  const [url, setURL] = useState<string | null>(null);
  useEffect(() => {
    if (!result) return;
    const objectURL = URL.createObjectURL(result.blob);
    setURL(objectURL);
    return () => URL.revokeObjectURL(objectURL);
  }, [result]);
  useEffect(() => () => { active.current?.abort(); active.current = null; }, []);
  async function preview() {
    if (!draft || active.current) return;
    const controller = new AbortController();
    active.current = controller;
    const captured = current.current;
    setBusy(true); setError('');
    try {
      const response = await apiService.previewStudio(draft, controller.signal);
      if (controller.signal.aborted) return;
      if (!sameStamp(current.current, captured)) {
        setError('Draft changed during compilation. Preview again to see your latest edits.');
        return;
      }
      setResult({ ...response, stamp: captured });
    } catch (e) {
      if (!controller.signal.aborted && sameStamp(current.current, captured)) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (active.current === controller) { active.current = null; setBusy(false); }
    }
  }
  return { preview, busy, error, url, outdated: !!result && !sameStamp(result.stamp, stamp), identity: result?.identity };
}
