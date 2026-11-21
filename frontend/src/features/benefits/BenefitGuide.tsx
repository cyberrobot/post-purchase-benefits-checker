'use client';

import { Fragment, useEffect, useId, useState } from 'react';
import { Container } from '@/components/ui/Container';

const benefits = [
  {
    name: 'Cashback',
    summary: 'Money back on a purchase',
    title: 'Money returned after purchase',
    description: 'Cashback is a benefit that may return some of the purchase price after a claim.',
    check: 'Check the products, retailers and purchase dates in the promotion terms.',
    timing: 'Check when claims open and close, and when a successful claim might be paid.',
    evidence: 'You may need a receipt or invoice and product details.',
  },
  {
    name: 'Extended warranty',
    summary: 'Additional cover for your product',
    title: 'Additional cover for your product',
    description: 'An extended warranty can provide cover beyond the original warranty.',
    check: 'Check what is covered, any exclusions and whether registration is required.',
    timing: 'Check the registration deadline and when the additional cover starts and ends.',
    evidence: 'You may need proof of purchase and the product serial number.',
  },
  {
    name: 'Free gift',
    summary: 'An additional item with a purchase',
    title: 'An additional item with your purchase',
    description: 'A free gift is an extra item that may be offered with a qualifying purchase.',
    check: 'Check which purchases qualify, what the gift is and how to claim it.',
    timing: 'Check the claim deadline and any stated delivery or collection arrangements.',
    evidence: 'You may need proof of purchase and details of the product.',
  },
];

export function BenefitGuide() {
  const [open, setOpen] = useState<number | null>(0);
  const [lastSelected, setLastSelected] = useState(0);
  const id = useId();

  useEffect(() => {
    function restoreDesktopSelection() {
      if (window.innerWidth >= 768) setOpen((current) => current ?? lastSelected);
    }
    window.addEventListener('resize', restoreDesktopSelection);
    restoreDesktopSelection();
    return () => window.removeEventListener('resize', restoreDesktopSelection);
  }, [lastSelected]);

  return (
    <section aria-label="Types of benefits" className="mt-20 md:mt-40">
      <Container>
        <div className="mx-auto mb-10 max-w-3xl text-center">
          <p className="font-bold tracking-widest text-brand uppercase">Types of benefits</p>
          <h2 className="mt-3 text-section leading-tight font-bold tracking-tight">
            Understand the kinds of post-purchase benefits you might find
          </h2>
          <p className="mt-4 text-body text-ink-muted">
            Explore how each benefit type works and what to look for after buying.
          </p>
        </div>
        <div className="grid min-w-0 gap-3 rounded-feature bg-navy p-4 text-on-dark md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:grid-rows-[repeat(3,auto)] md:gap-x-6 md:p-8">
          {benefits.map((benefit, index) => (
            <Fragment key={benefit.name}>
              <button
                type="button"
                aria-expanded={open === index}
                aria-controls={`${id}-panel-${index}`}
                onClick={() => {
                  setLastSelected(index);
                  setOpen(open === index && window.innerWidth < 768 ? null : index);
                }}
                className={`min-w-0 cursor-pointer rounded-card p-5 text-left md:col-start-1 ${
                  open === index ? 'bg-brand' : 'bg-navy-panel'
                }`}
              >
                <span className="block text-lg font-bold">
                  0{index + 1}. {benefit.name}
                </span>
                <span className="mt-1 block text-sm">{benefit.summary}</span>
              </button>
              <div
                id={`${id}-panel-${index}`}
                hidden={open !== index}
                className="min-w-0 rounded-card border border-white/10 bg-navy-panel p-5 md:col-start-2 md:row-span-3 md:row-start-1 md:p-8"
              >
                <p className="font-semibold text-indigo-200">Benefit guide · {benefit.name}</p>
                <h3 className="mt-4 text-card font-bold">{benefit.title}</h3>
                <p className="mt-4">{benefit.description}</p>
                <dl className="mt-6">
                  {[
                    ['What to check', benefit.check],
                    ['Possible timing', benefit.timing],
                    ['Possible evidence', benefit.evidence],
                  ].map(([label, text]) => (
                    <div
                      key={label}
                      className="border-t border-white/15 py-4 sm:grid sm:grid-cols-3 sm:gap-4"
                    >
                      <dt className="font-semibold">{label}</dt>
                      <dd className="mt-1 sm:col-span-2 sm:mt-0">{text}</dd>
                    </div>
                  ))}
                </dl>
                <p className="border-t border-white/15 pt-4 text-sm">
                  Requirements vary by promotion. Official terms are authoritative.
                </p>
              </div>
            </Fragment>
          ))}
        </div>
      </Container>
    </section>
  );
}
