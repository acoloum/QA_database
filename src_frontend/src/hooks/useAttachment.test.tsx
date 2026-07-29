import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import api from '../services/api';
import { useUploadAttachment } from './useAttachment';

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
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
