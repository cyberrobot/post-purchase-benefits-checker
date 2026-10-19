import type { ReactNode } from 'react';
type AccordionItemProps = {
  title: string;
  children: ReactNode;
  open?: boolean;
  className?: string;
};
export function AccordionItem({ title, children, open, className = '' }: AccordionItemProps) {
  return (
    <details className={`accordion ${className}`} open={open}>
      <summary>
        {title}
        <svg
          className="disclosure-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </summary>
      <div className="accordion-content">{children}</div>
    </details>
  );
}
