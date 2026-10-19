'use client';
import Link from 'next/link';
import { useEffect, useId, useRef, useState } from 'react';
export type NavigationItem = { href: `/${string}` | `#${string}`; label: string };
export function SiteNavigation({ items }: { items: readonly NavigationItem[] }) {
  const id = useId();
  const disclosure = useRef<HTMLDetailsElement>(null);
  const summary = useRef<HTMLElement>(null);
  const [open, setOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    setOpen(disclosure.current?.open ?? false);
    setHydrated(true);
  }, []);
  function close(restoreFocus: boolean) {
    if (disclosure.current) disclosure.current.open = false;
    setOpen(false);
    if (restoreFocus) summary.current?.focus();
  }
  const links = items.map(({ href, label }) => (
    <li key={href}>
      <Link href={href} onClick={() => close(false)}>
        {label}
      </Link>
    </li>
  ));
  return (
    <>
      <nav aria-label="Primary" className="desktop-navigation">
        <ul>{links}</ul>
      </nav>
      <details
        ref={disclosure}
        className="mobile-navigation"
        onToggle={(event) => setOpen(event.currentTarget.open)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') close(true);
        }}
      >
        <summary ref={summary} aria-expanded={hydrated ? open : undefined} aria-controls={id}>
          Menu <span aria-hidden="true">⌄</span>
        </summary>
        <nav id={id} aria-label="Mobile primary">
          <ul>{links}</ul>
        </nav>
      </details>
    </>
  );
}
