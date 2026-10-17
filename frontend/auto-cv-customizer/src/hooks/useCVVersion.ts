import { useCallback, useEffect, useRef, useState } from 'react';
import type { CVData } from '../types/cv';
import type { CVVersionInfo } from '../services/api';
import api from '../services/api';

/** Shared source-version access, independent of tabs/context and result drafts. */
export function useCVVersion(versionId: string, versionsChanged: (versions: CVVersionInfo[]) => void) {
  const [data, setData] = useState<CVData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const refreshVersions = useCallback(async () => {
    versionsChanged(await api.listCVVersions());
  }, [versionsChanged]);
  const load = useCallback(async (id: string) => {
    const request = ++generation.current;
    setIsLoading(true); setData(null); setError(null);
    try {
      const value = await api.getCVVersion(id);
      if (request === generation.current) setData(value);
      return value;
    } catch (failure) {
      if (request === generation.current) setError(String(failure));
      throw failure;
    } finally { if (request === generation.current) setIsLoading(false); }
  }, []);
  useEffect(() => {
    void refreshVersions().catch(failure => setError(String(failure)));
    void load(versionId).catch(() => {});
    return () => { generation.current += 1; };
  }, [versionId, load, refreshVersions]);
  return { data, setData, isLoading, error, load, refreshVersions,
    // Capture the selected identity before awaiting; never save to a newer selection.
    save: async (value: CVData) => {
      const request = generation.current;
      const saved = await api.updateCVVersion(versionId, value);
      if (request === generation.current) setData(saved);
      return saved;
    },
    create: async (id: string, value: CVData) => {
      const saved = await api.createCVVersion(id, value);
      await refreshVersions(); return saved;
    },
    remove: async (id: string) => { await api.deleteCVVersion(id); await refreshVersions(); },
  };
}
