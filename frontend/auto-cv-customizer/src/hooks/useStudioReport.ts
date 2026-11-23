/** TRF-05: provider-lifetime layout-quality requests for the current draft. */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { StudioDraft, StudioPreviewReport } from '../types/api.generated';
import { apiService } from '../services/api';

export function useStudioReport(draft: StudioDraft | null, revision: number) {
  const input = JSON.stringify(draft);
  const current = useRef({ input, revision });
  useLayoutEffect(() => { current.current = { input, revision }; }, [input, revision]);
  const active = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState<(StudioPreviewReport & { input: string }) | null>(null);
  useEffect(() => () => { active.current = false; }, []);
  async function check() {
    if (!draft || active.current) return;
    active.current = true;
    const captured = { input, revision };
    setBusy(true); setError('');
    try {
      const value = await apiService.previewReport(draft);
      if (current.current.input !== captured.input || current.current.revision !== captured.revision) {
        setError('Draft changed during analysis. Check again to inspect your latest edits.');
        return;
      }
      setReport({ ...value, input: captured.input });
    } catch (e) {
      if (current.current.input === captured.input && current.current.revision === captured.revision) setError(e instanceof Error ? e.message : String(e));
    } finally {
      active.current = false; setBusy(false);
    }
  }
  return { check, busy, error, report, outdated: !!report && report.input !== input };
}
