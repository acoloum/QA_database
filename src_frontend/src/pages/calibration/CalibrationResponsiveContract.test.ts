import { describe, expect, it } from 'vitest';

import calibrationCss from './calibration.css?raw';

const mobileCss = calibrationCss.slice(
  calibrationCss.indexOf('@media (max-width: 640px) {'),
  calibrationCss.indexOf('@media (prefers-reduced-motion: reduce)'),
);

describe('校正詳情行動版 CSS contract', () => {
  it('在 640px 以下以單欄讀值卡片呈現且長內容不溢出', () => {
    expect(mobileCss).toMatch(
      /\.cal-detail-readings\s*\{[^}]*grid-template-columns:\s*1fr;/,
    );
    expect(mobileCss).toMatch(
      /\.cal-detail-reading-card\s*\{[^}]*min-width:\s*0;[^}]*overflow-wrap:\s*anywhere;/,
    );
    expect(mobileCss).toMatch(
      /\.cal-detail-reading-card\s*\{[^}]*border-left:\s*4px solid var\(--cal-blue\);/,
    );
  });
});
