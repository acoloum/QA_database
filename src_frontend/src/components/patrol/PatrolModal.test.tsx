import { describe, expect, it } from 'vitest';

import appCss from '../../App.css?raw';

describe('PatrolModal NG 欄位樣式', () => {
  it('呼吸燈 keyframes 不使用瀏覽器會忽略的 important 宣告', () => {
    const keyframes = appCss.match(/@keyframes patrol-ng-breathing\s*\{[\s\S]*?\n\}/)?.[0] ?? '';

    expect(keyframes).toContain('@keyframes patrol-ng-breathing');
    expect(keyframes).toContain('box-shadow');
    expect(keyframes).not.toContain('!important');
  });
});
