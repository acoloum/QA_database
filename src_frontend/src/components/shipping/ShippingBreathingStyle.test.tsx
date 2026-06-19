import { describe, expect, it } from 'vitest';

import appCss from '../../App.css?raw';
import shippingModalSource from './ShippingModal.tsx?raw';

describe('ShippingModal NG 欄位樣式', () => {
  it('使用純 CSS 呼吸燈，不再用 DOM interval 切換 class', () => {
    const keyframes = appCss.match(/@keyframes shipping-ng-breathing\s*\{[\s\S]*?\n\}/)?.[0] ?? '';

    expect(keyframes).toContain('@keyframes shipping-ng-breathing');
    expect(keyframes).toContain('box-shadow');
    expect(keyframes).not.toContain('!important');
    expect(appCss).not.toContain('breathing-active');
    expect(shippingModalSource).not.toContain('document.querySelectorAll');
    expect(shippingModalSource).not.toContain('setInterval');
  });
});
