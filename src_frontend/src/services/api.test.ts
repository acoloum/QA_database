import { beforeEach, describe, expect, it, vi } from 'vitest';
import toast from 'react-hot-toast';

import api from './api';

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn() },
}));

type ToastedError = Error & {
  _toasted?: boolean;
  response?: { status: number; data: Record<string, unknown> };
};

type ResponseInterceptorManager = {
  handlers: Array<{
    rejected: (error: ToastedError) => Promise<never>;
  }>;
};

const responseErrorHandler = (
  api.interceptors.response as unknown as ResponseInterceptorManager
).handlers[0].rejected;

const genericErrors: Array<[string, ToastedError]> = [
  ['網路錯誤', Object.assign(new Error('Network Error'), {})],
  [
    '無標準 error payload 的伺服器錯誤',
    Object.assign(new Error('Bad Gateway'), { response: { status: 502, data: {} } }),
  ],
];

describe('API 回應攔截器', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each(genericErrors)('%s 顯示 toast 後會標記原錯誤，避免 caller 重複顯示', async (_label, error) => {
    await expect(responseErrorHandler(error)).rejects.toBe(error);

    expect(toast.error).toHaveBeenCalledWith(error.message);
    expect(error._toasted).toBe(true);
  });
});
