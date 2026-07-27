import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import toast from 'react-hot-toast';

import api, { ApiError } from './api';

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

describe('API 實際 Axios 傳輸與穩定錯誤契約', () => {
  const originalAdapter = api.defaults.adapter;

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
  });

  it('讓 Axios 依 body 自動轉換 JSON 與 FormData，且不把 FormData 標為 JSON', async () => {
    const requests: InternalAxiosRequestConfig[] = [];
    const adapter: AxiosAdapter = async (config) => {
      requests.push(config);
      return {
        data: { data: {} }, status: 200, statusText: 'OK', headers: {}, config,
      };
    };
    api.defaults.adapter = adapter;
    const formData = new FormData();
    formData.append('file', new File(['設備編號,名稱'], 'equipment.csv', { type: 'text/csv' }));

    await api.post('/contract-json', { status: 'active' });
    await api.post('/contract-form', formData);

    expect(requests[0]?.data).toBe('{"status":"active"}');
    expect(AxiosHeaders.from(requests[0]?.headers).getContentType()).toContain('application/json');
    expect(requests[1]?.data).toBe(formData);
    expect(AxiosHeaders.from(requests[1]?.headers).getContentType()).not.toContain('application/json');
  });

  it.each([
    [409, 'MSA_EQUIPMENT_STATUS_CONFLICT', '狀態已變更', { expected_status: 'active' }, 'status'],
    [422, 'MSA_IMPORT_RESOLUTION_INVALID', '逐列處置無效', { row_id: 71 }, 'resolutions'],
  ] as const)('將 %i 穩定錯誤轉為可判定 ApiError', async (status, code, message, details, field) => {
    const adapter: AxiosAdapter = async (config) => {
      const response: AxiosResponse = {
        data: { error: { code, message, details, field } },
        status,
        statusText: '受控錯誤',
        headers: {},
        config,
      };
      throw new AxiosError(message, undefined, config, {}, response);
    };
    api.defaults.adapter = adapter;

    await expect(api.post('/stable-error', {})).rejects.toMatchObject({
      name: ApiError.name,
      message,
      status,
      code,
      details,
      field,
    });
  });
});
