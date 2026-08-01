import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import toast from 'react-hot-toast';

import { getAdminErrorMessage } from '../hooks/useAdmin';
import { getPyrometryErrorMessage } from '../hooks/usePyrometry';
import { getReworkErrorMessage } from '../components/rework/reworkError';
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

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

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
    [409, 'MSA_EQUIPMENT_STATUS_CONFLICT', '狀態已變更', { expected_status: 'active', field: 'status' }, 'status'],
    [422, 'MSA_IMPORT_RESOLUTION_INVALID', '逐列處置無效', { row_id: 71, field: 'resolutions' }, 'resolutions'],
  ] as const)('將 %i 穩定錯誤轉為可判定 ApiError', async (status, code, message, details, field) => {
    const adapter: AxiosAdapter = async (config) => {
      const response: AxiosResponse = {
        data: { error: { code, message, details } },
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

  it('structured 後端錯誤保留頂層欄位，並讓既有非 MSA helper 讀到字串 error', async () => {
    const sourceData = {
      success: false,
      error: {
        code: 'MSA_IMPORT_RESOLUTION_INVALID', message: '逐列處置無效',
        details: { row_id: 71, field: 'resolutions' },
      },
    };
    const adapter: AxiosAdapter = async (config) => {
      const response: AxiosResponse = {
        data: sourceData, status: 422, statusText: '受控錯誤', headers: {}, config,
      };
      throw new AxiosError('逐列處置無效', undefined, config, {}, response);
    };
    api.defaults.adapter = adapter;

    let caught: unknown;
    try {
      await api.post('/compatibility-error', {});
    } catch (error) {
      caught = error;
    }

    expect(caught).toMatchObject({
      name: ApiError.name, status: 422, code: 'MSA_IMPORT_RESOLUTION_INVALID',
      details: { row_id: 71, field: 'resolutions' }, field: 'resolutions', message: '逐列處置無效',
    });
    expect(getAdminErrorMessage(caught)).toBe('逐列處置無效');
    expect(getPyrometryErrorMessage(caught, '爐溫測試儲存失敗')).toBe('逐列處置無效');
    expect(getReworkErrorMessage(caught, '重工失敗')).toBe('逐列處置無效');
    expect((caught as { response?: { data?: { error?: unknown; success?: boolean } } }).response?.data).toEqual({
      success: false, error: '逐列處置無效',
    });
    expect(sourceData.error).toEqual({
      code: 'MSA_IMPORT_RESOLUTION_INVALID', message: '逐列處置無效',
      details: { row_id: 71, field: 'resolutions' },
    });
  });

  it('403 穩定錯誤建立 ApiError 且保留 authToken', async () => {
    localStorage.setItem('authToken', 'keep-on-forbidden');
    const adapter: AxiosAdapter = async (config) => {
      const response: AxiosResponse = {
        data: { error: { code: 'PERMISSION_DENIED', message: '權限不足' } },
        status: 403,
        statusText: 'Forbidden',
        headers: {},
        config,
      };
      throw new AxiosError('權限不足', undefined, config, {}, response);
    };
    api.defaults.adapter = adapter;

    await expect(api.get('/forbidden')).rejects.toMatchObject({
      name: ApiError.name,
      status: 403,
      code: 'PERMISSION_DENIED',
      message: '權限不足',
    });
    expect(localStorage.getItem('authToken')).toBe('keep-on-forbidden');
  });

  it('401 穩定錯誤清除登入狀態後仍建立可判定 ApiError', async () => {
    window.history.replaceState({}, '', '/login');
    localStorage.setItem('authToken', 'expired-token');
    localStorage.setItem('username', 'expired-user');
    const adapter: AxiosAdapter = async (config) => {
      const response: AxiosResponse = {
        data: { error: { code: 'AUTH_ERROR', message: '登入已過期' } },
        status: 401,
        statusText: 'Unauthorized',
        headers: {},
        config,
      };
      throw new AxiosError('登入已過期', undefined, config, {}, response);
    };
    api.defaults.adapter = adapter;

    await expect(api.get('/expired')).rejects.toMatchObject({
      name: ApiError.name,
      status: 401,
      code: 'AUTH_ERROR',
      message: '登入已過期',
    });
    expect(localStorage.getItem('authToken')).toBeNull();
    expect(localStorage.getItem('username')).toBeNull();
  });

  it('legacy 字串 error 過渡分支仍建立 ApiError', async () => {
    const adapter: AxiosAdapter = async (config) => {
      const response: AxiosResponse = {
        data: { error: '舊版驗證訊息' },
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config,
      };
      throw new AxiosError('舊版驗證訊息', undefined, config, {}, response);
    };
    api.defaults.adapter = adapter;

    await expect(api.get('/legacy-error')).rejects.toMatchObject({
      name: ApiError.name,
      status: 400,
      message: '舊版驗證訊息',
    });
  });
});
