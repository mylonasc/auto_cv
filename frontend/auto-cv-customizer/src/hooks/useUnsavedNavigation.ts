import { useEffect, useLayoutEffect } from 'react';
import { useAppState } from '../contexts/AppStateContext';

/** One guard covers tabs, version changes and page unload for either source editor. */
export function useUnsavedNavigation(unsaved: boolean, saving: boolean) {
  const { guardNavigation } = useAppState();
  useLayoutEffect(() => guardNavigation(() => {
    if (saving) { window.alert('Wait for the source CV save to finish before navigating.'); return false; }
    return !unsaved || window.confirm('You have unsaved source CV changes. Discard them and use the saved version?');
  }), [guardNavigation, unsaved, saving]);
  useEffect(() => {
    if (!unsaved && !saving) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [unsaved, saving]);
}
