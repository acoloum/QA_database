import { describe, expect, it, vi } from 'vitest';

import { downloadBlob } from './downloadFile';

describe('downloadBlob', () => {
  it('建立下載連結並釋放 blob URL', () => {
    const click = vi.fn();
    const remove = vi.fn();
    const anchor = {
      href: '',
      download: '',
      click,
      remove,
    } as unknown as HTMLAnchorElement;
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:qc-report');
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const createElement = vi.spyOn(document, 'createElement').mockReturnValue(anchor);
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation(node => node);

    downloadBlob(new Blob(['report']), '品質報告.xlsx');

    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(createElement).toHaveBeenCalledWith('a');
    expect(anchor.href).toBe('blob:qc-report');
    expect(anchor.download).toBe('品質報告.xlsx');
    expect(appendChild).toHaveBeenCalledWith(anchor);
    expect(click).toHaveBeenCalledTimes(1);
    expect(remove).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:qc-report');
  });
});
