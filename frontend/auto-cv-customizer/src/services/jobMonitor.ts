import type { ProcessingState } from '../types/view';
import { isTerminal } from '../domain/workflow.ts';

interface Stream {
  addEventListener(type: string, listener: (event: MessageEvent) => void): void;
  close(): void;
  onerror: ((event: Event) => void) | null;
}

/** Native SSE reconnects; bounded-frequency HTTP polling reconciles missed terminal events. */
export function monitorJob(id: string, dependencies: {
  stream: () => Stream;
  fetch: () => Promise<ProcessingState>;
  decode: (value: unknown) => ProcessingState;
  snapshot: (job: ProcessingState) => void;
  error: (message: string | null) => void;
  schedule?: (callback: () => void) => () => void;
}) {
  let stopped = false;
  let fetching = false;
  let stopPolling: (() => void) | undefined;
  let stream: Stream | undefined;
  const stop = () => { stopped = true; stream?.close(); stopPolling?.(); };
  const accept = (job: ProcessingState) => {
    if (stopped || job.jobId !== id) return;
    if (!['queued', 'processing', 'succeeded', 'failed', 'cancelled'].includes(job.status)) throw new Error('Invalid job status');
    dependencies.snapshot(job);
    dependencies.error(null);
    if (isTerminal(job)) stop();
  };
  const reconcile = async () => {
    if (stopped || fetching) return;
    fetching = true;
    try { accept(await dependencies.fetch()); }
    catch { if (!stopped) dependencies.error('Connection interrupted; retrying job monitoring.'); }
    finally { fetching = false; }
  };
  const poll = () => {
    if (stopPolling || stopped) return;
    const schedule = dependencies.schedule || ((callback) => {
      const timer = setInterval(callback, 2000);
      return () => clearInterval(timer);
    });
    stopPolling = schedule(() => { void reconcile(); });
  };
  try {
    stream = dependencies.stream();
    const update = (event: MessageEvent) => {
      try { accept(dependencies.decode(JSON.parse(event.data))); }
      catch { dependencies.error('Invalid stream event; reconciling with server.'); poll(); void reconcile(); }
    };
    stream.addEventListener('job_update', update);
    stream.addEventListener('job_complete', update);
    stream.onerror = () => {
      if (stopped) return;
      dependencies.error('Connection interrupted; reconnecting and checking job status.');
      poll(); void reconcile();
    };
  } catch { poll(); }
  void reconcile();
  return stop;
}
