import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { fetchAttachmentBlob, useUploadAttachment } from './useAttachment';

vi.mock('../services/api', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}));
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>
    {children}
  </QueryClientProvider>
);

describe('附件上傳 hook', () => {
  beforeEach(() => vi.clearAllMocks());

  it('校正證書 FormData 保留 purpose cert', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { id: 88 } });
    const { result } = renderHook(() => useUploadAttachment(), { wrapper });
    const file = new File(['pdf'], 'certificate.pdf', {
      type: 'application/pdf',
    });

    await act(async () => {
      await result.current.mutateAsync({
        file,
        entity_type: 'equipment_calibration',
        entity_id: 41,
        purpose: 'cert',
      });
    });

    const form = vi.mocked(api.post).mock.calls[0][1] as FormData;
    expect(form.get('file')).toBe(file);
    expect(form.get('entity_type')).toBe('equipment_calibration');
    expect(form.get('entity_id')).toBe('41');
    expect(form.get('purpose')).toBe('cert');
  });
});

describe('附件下載', () => {
  beforeEach(() => vi.clearAllMocks());

  it('經共用 api 以 blob 取得檔案並傳遞中止訊號', async () => {
    const blob = new Blob(['file']);
    vi.mocked(api.get).mockResolvedValue({ data: blob });
    const controller = new AbortController();

    await expect(fetchAttachmentBlob(7, controller.signal)).resolves.toBe(blob);
    expect(api.get).toHaveBeenCalledWith('/attachments/7/download', {
      responseType: 'blob',
      signal: controller.signal,
    });
  });

  it('錯誤回應時 reject，不會把錯誤內容當成檔案', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Request failed with status code 404'));
    await expect(fetchAttachmentBlob(7)).rejects.toThrow('404');
  });
});
