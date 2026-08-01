import axios from 'axios';
import toast from 'react-hot-toast';
import { ApiError } from './apiError';

export { ApiError } from './apiError';

// 建立 axios 實例
const api = axios.create({
    baseURL: '/api',
});

type StableErrorDetails = Record<string, unknown>;

const isRecord = (value: unknown): value is Record<string, unknown> => (
    typeof value === 'object' && value !== null && !Array.isArray(value)
);

const cloneCompatibleResponse = (
    response: ApiError['response'],
    message: string,
): ApiError['response'] => {
    if (!response || !isRecord(response.data)) return response;
    return {
        ...response,
        data: { ...response.data, error: message },
    };
};

const readStableError = (rawError: unknown, status?: number, response?: unknown): ApiError | null => {
    const apiResponse = response as ApiError['response'];
    if (typeof rawError === 'string') {
        return new ApiError({ message: rawError, status, response: apiResponse });
    }
    if (!isRecord(rawError)) return null;

    if (typeof rawError.message !== 'string' || typeof rawError.code !== 'string') return null;
    const message = rawError.message;
    const code = rawError.code;
    const details = isRecord(rawError.details) ? rawError.details as StableErrorDetails : undefined;
    const detailField = typeof details?.field === 'string' ? details.field : undefined;
    return new ApiError({
        message, status, code, details, field: detailField,
        response: cloneCompatibleResponse(apiResponse, message),
    });
};

// 請求攔截器：自動帶入 Token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('authToken');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// 回應攔截器：處理錯誤
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const { response } = error;

        // 1. 只有 401 代表登入失效；403 仍保留 token 供 caller 顯示權限錯誤。
        if (response && response.status === 401) {
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
                toast.error('登入已過期，請重新登入');
            }
        }

        // 2. 正式 envelope 與 legacy 字串過渡分支
        if (response && response.data && response.data.error) {
            // 後端可能回 { error: "訊息" } 或穩定 { error: { code, message, details } }。
            const rawError = response.data.error;
            const err = readStableError(rawError, response.status, response);
            if (err === null) return Promise.reject(error);

            // 4xx 驗證錯誤（如「使用者名稱已存在」）→ 不顯示 toast，讓 caller 自行處理
            // 5xx server error 或沒有 response 的錯誤 → 顯示 toast
            const isServerError = !response || response.status >= 500;

            if (isServerError || !response) {
                toast.error(err.message);
                err._toasted = true;
            }
            // 4xx 驗證錯誤不放 toast，_toasted 保持 undefined

            return Promise.reject(err);
        }

        // 3. 處理網路或其他錯誤（沒有 error.data 的情況）
        const genericMsg = error.message || '網路連線異常';
        toast.error(genericMsg);
        const toastedError = error as Error & { _toasted?: boolean };
        toastedError._toasted = true;
        return Promise.reject(toastedError);
    }
);

export default api;
