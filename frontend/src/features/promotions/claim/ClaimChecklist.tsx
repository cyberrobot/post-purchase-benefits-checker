'use client';

import { useState } from 'react';
import type { PromotionDetails } from '@/lib/api/promotion-details.contract';
import { requirementLabels } from './requirements';

type Requirements = PromotionDetails['variants'][number]['requirements'];

export function ClaimChecklist({ requirements }: { requirements: Requirements }) {
  const [marked, setMarked] = useState<Set<string>>(() => new Set());

  if (!requirements.length) {
    return (
      <p>
        No claim requirements are recorded for this variant. Review the official terms before
        proceeding.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p>Tick each item when you have it ready or have completed the action.</p>
      <ul className="space-y-3">
        {requirements.map((item) => {
          const id = 'requirement-' + item.requirement_id;
          const descriptionId = id + '-description';
          return (
            <li key={item.requirement_id}>
              <label
                htmlFor={id}
                className="flex min-h-11 cursor-pointer items-start gap-3 rounded-control border border-border p-3"
              >
                <input
                  type="checkbox"
                  id={id}
                  aria-labelledby={id + '-label'}
                  aria-describedby={item.description ? descriptionId : undefined}
                  checked={marked.has(item.requirement_id)}
                  onChange={(event) => {
                    const checked = event.currentTarget.checked;
                    setMarked((previous) => {
                      const next = new Set(previous);
                      if (checked) next.add(item.requirement_id);
                      else next.delete(item.requirement_id);
                      return next;
                    });
                  }}
                  className="mt-1 size-5 shrink-0 accent-brand"
                />
                <span className="min-w-0">
                  <strong id={id + '-label'}>{requirementLabels[item.requirement_type]}</strong>
                  {item.description && (
                    <span id={descriptionId} className="block">
                      {item.description}
                    </span>
                  )}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      <div role="status" aria-atomic="true" className="font-semibold">
        <p>
          {marked.size} of {requirements.length} items marked ready.
        </p>
        {marked.size === requirements.length && <p>All recorded items marked ready.</p>}
      </div>
      <p className="text-small text-ink-muted">Checklist progress is not saved.</p>
    </div>
  );
}
