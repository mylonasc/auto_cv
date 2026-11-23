/** TRF-05: provider-lifetime layout-quality requests for the current draft.
 *
 * Like the PDF preview, staleness uses the reducer's {generation, edit} stamp
 * instead of serializing the whole draft on every render.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { StudioDraft, StudioPreviewReport } from '../types/api.generated';
import { apiService } from '../services/api';
import { sameStamp, type StudioStamp } from './useStudioPreview';

export function useStudioReport(draft: StudioDraft | null, stamp: StudioStamp) {
  const current = useRef(stamp);
  useLayoutEffect(() => { current.current = stamp; }, [stamp]);
  const active = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [report, setReport] = useState<(StudioPreviewReport & { stamp: StudioStamp }) | null>(null);
  useEffect(() => () => { active.current = false; }, []);
  async function check() {
    if (!draft || active.current) return;
    active.current = true;
    const captured = current.current;
    setBusy(true); setError('');
    try {
      const value = await apiService.previewReport(draft);
      if (!sameStamp(current.current, captured)) {
        setError('Draft changed during analysis. Check again to inspect your latest edits.');
        return;
      }
      setReport({ ...value, stamp: captured });
    } catch (e) {
      if (sameStamp(current.current, captured)) setError(e instanceof Error ? e.message : String(e));
    } finally {
      active.current = false; setBusy(false);
    }
  }
  return { check, busy, error, report, outdated: !!report && !sameStamp(report.stamp, stamp) };
}
