'use client';

import { useEffect } from 'react';

export function VariantHashFocus() {
  useEffect(() => {
    const focusHashTarget = () => {
      const match = /^#variant-[0-9a-f-]{36}$/i.exec(window.location.hash);
      if (!match) return;
      document.getElementById(match[0].slice(1))?.focus({ preventScroll: true });
    };
    focusHashTarget();
    window.addEventListener('hashchange', focusHashTarget);
    return () => window.removeEventListener('hashchange', focusHashTarget);
  }, []);

  return null;
}
