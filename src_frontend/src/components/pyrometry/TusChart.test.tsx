import { describe, expect, it } from 'vitest';
import { channelLineColor, EXCLUDED_COLOR } from './TusChart';

describe('channelLineColor', () => {
  it('returns grey for excluded channels', () => {
    expect(channelLineColor(0, true)).toBe(EXCLUDED_COLOR);
  });
  it('returns a palette colour for normal channels', () => {
    expect(channelLineColor(0, false)).not.toBe(EXCLUDED_COLOR);
  });
});
