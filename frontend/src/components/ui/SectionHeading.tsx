import type { ReactNode } from 'react';
const tones = {
  light: {
    eyebrow: 'text-brand group-data-[surface=dark]/card:text-highlight',
    heading: '',
    description: 'text-ink-muted group-data-[surface=dark]/card:text-on-dark',
  },
  dark: {
    eyebrow: 'text-highlight',
    heading: 'text-on-dark',
    description: 'text-on-dark',
  },
};
type SectionHeadingProps = {
  level: 'h2' | 'h3';
  children: ReactNode;
  eyebrow?: string;
  description?: string;
  align?: 'normal' | 'center';
  tone?: 'light' | 'dark';
  id?: string;
};
export function SectionHeading({
  level: Heading,
  children,
  eyebrow,
  description,
  align = 'normal',
  tone = 'light',
  id,
}: SectionHeadingProps) {
  return (
    <div className={`grid gap-3 ${align === 'center' ? 'justify-items-center text-center' : ''}`}>
      {eyebrow && (
        <p className={`text-small font-bold tracking-widest uppercase ${tones[tone].eyebrow}`}>
          {eyebrow}
        </p>
      )}
      <Heading
        id={id}
        className={`text-section leading-[1.15] font-bold tracking-tight ${tones[tone].heading}`}
      >
        {children}
      </Heading>
      {description && (
        <p className={`max-w-[70ch] text-body ${tones[tone].description}`}>{description}</p>
      )}
    </div>
  );
}
