/** TRF-04: provider-lifetime PDF requests and object URL ownership. */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { StudioDraft } from '../types/api.generated';
import { apiService } from '../services/api';

export function useStudioPreview(draft: StudioDraft | null, revision: number) {
  const input = JSON.stringify(draft);
  const current = useRef({ input, revision });
  useLayoutEffect(() => { current.current = { input, revision }; }, [input, revision]);
  const active = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ blob: Blob; input: string; identity: string } | null>(null);
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
    const captured = { input, revision };
    setBusy(true); setError('');
    try {
      const response = await apiService.previewStudio(draft, controller.signal);
      if (controller.signal.aborted) return;
      if (current.current.input !== captured.input || current.current.revision !== captured.revision) {
        setError('Draft changed during compilation. Preview again to see your latest edits.');
        return;
      }
      setResult({ ...response, input: captured.input });
    } catch (e) {
      if (!controller.signal.aborted && current.current.input === captured.input && current.current.revision === captured.revision) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (active.current === controller) { active.current = null; setBusy(false); }
    }
  }
  return { preview, busy, error, url, outdated: !!result && result.input !== input, identity: result?.identity };
}
