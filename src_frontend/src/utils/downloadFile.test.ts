import { describe, expect, it, vi } from 'vitest';

import { downloadBlob, fetchAndDownload } from './downloadFile';

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

describe('fetchAndDownload', () => {
  it('下載受保護端點並委派 downloadBlob', async () => {
    const click = vi.fn();
    const remove = vi.fn();
    const anchor = {
      href: '',
      download: '',
      click,
      remove,
    } as unknown as HTMLAnchorElement;
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:attachment');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    vi.spyOn(document, 'createElement').mockReturnValue(anchor);
    vi.spyOn(document.body, 'appendChild').mockImplementation(node => node);
    const blob = new Blob(['file']);
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({ blob: () => Promise.resolve(blob) } as Response);

    await fetchAndDownload('/api/attachments/1/download', '檢驗報告.pdf', 'token-1');

    expect(fetchSpy).toHaveBeenCalledWith('/api/attachments/1/download', {
      headers: { Authorization: 'Bearer token-1' },
    });
    expect(anchor.download).toBe('檢驗報告.pdf');
    expect(click).toHaveBeenCalledTimes(1);
  });
});
