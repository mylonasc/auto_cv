import { useEffect, useState } from 'react';
import api from '../services/api';
import type { TemplateRegistryResponse } from '../services/api';

export function useTemplates() {
  const [registry, setRegistry] = useState<TemplateRegistryResponse>({ cv_templates: {}, motivation_letter_templates: {} });
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let disposed = false;
    void api.getTemplateRegistry().then(value => { if (!disposed) setRegistry(value); })
      .catch(failure => { if (!disposed) setError(String(failure)); });
    return () => { disposed = true; };
  }, []);
  return { registry, error };
}
