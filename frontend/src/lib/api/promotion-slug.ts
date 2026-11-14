import { z } from 'zod';

const slug = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function isPromotionSlugComponent(value: string) {
  return value.length <= 255 && slug.test(value) && !/\s/.test(value);
}

export function parsePublicSlug(value: string): [string, string] | undefined {
  if (value.length > 512) return;
  const parts = value.split('--');
  if (parts.length === 2 && parts.every(isPromotionSlugComponent)) return [parts[0], parts[1]];
}

export const publicSlugSchema = z.string().refine((value) => Boolean(parsePublicSlug(value)));
