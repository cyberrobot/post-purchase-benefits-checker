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
      <Link className="block p-3 text-ink wrap-anywhere" href={href} onClick={() => close(false)}>
        {label}
      </Link>
    </li>
  ));
  return (
    <>
      <nav aria-label="Primary" className="hidden md:block">
        <ul className="m-0 flex list-none flex-wrap gap-3 p-0">{links}</ul>
      </nav>
      <details
        ref={disclosure}
        className="w-full md:hidden"
        onToggle={(event) => setOpen(event.currentTarget.open)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') close(true);
        }}
      >
        <summary
          className="min-h-11 cursor-pointer p-2 font-semibold"
          ref={summary}
          aria-expanded={hydrated ? open : undefined}
          aria-controls={id}
        >
          Menu <span aria-hidden="true">⌄</span>
        </summary>
        <nav id={id} aria-label="Mobile primary">
          <ul className="m-0 flex list-none flex-wrap gap-3 p-0">{links}</ul>
        </nav>
      </details>
    </>
  );
}
