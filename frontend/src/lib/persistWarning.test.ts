import { describe, it, expect } from 'vitest';
import { persistWarning } from './persistWarning';

describe('persistWarning', () => {
  it('returns null when persisted', () => {
    expect(persistWarning({ persisted: true }, 'en')).toBeNull();
  });
  it('returns null when flag absent (older backend)', () => {
    expect(persistWarning({}, 'en')).toBeNull();
  });
  it('warns in English when not persisted', () => {
    const m = persistWarning({ persisted: false, persist_error: 'OperationalError: x' }, 'en');
    expect(m).toMatch(/not saved|database/i);
  });
  it('warns in Malay when not persisted', () => {
    const m = persistWarning({ persisted: false }, 'bm');
    expect(m).toMatch(/tidak disimpan|pangkalan data/i);
  });
});
