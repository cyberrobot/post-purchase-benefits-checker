import type { ReactNode } from 'react';
type AccordionItemProps = {
  title: string;
  children: ReactNode;
  open?: boolean;
  className?: string;
};
export function AccordionItem({ title, children, open, className = '' }: AccordionItemProps) {
  return (
    <details
      className={`group rounded-card border border-border bg-surface text-ink ${className}`}
      open={open}
    >
      <summary className="accordion-summary flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 p-6 font-semibold wrap-anywhere">
        {title}
        <svg
          className="size-6 shrink-0 text-brand group-open:rotate-180"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>
      <div className="px-6 pb-6 wrap-anywhere">{children}</div>
    </details>
  );
}
