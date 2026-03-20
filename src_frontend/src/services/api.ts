import axios from 'axios';
import toast from 'react-hot-toast';

// 建立 axios 實例
const api = axios.create({
    baseURL: '/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

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

        // 1. 處理 401 Token 失效
        if (response && response.status === 401) {
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
                toast.error('登入已過期，請重新登入');
            }
            return Promise.reject(error);
        }

        // 2. 處理後端回傳的標準錯誤格式
        if (response && response.data && response.data.error) {
            // 後端可能回 { error: "訊息" } 或 { error: { message: "訊息", field: "欄位" } }
            const rawError = response.data.error;
            const errorMsg = typeof rawError === 'string'
                ? rawError
                : (rawError.message || '發生未知錯誤');
            const field = rawError && typeof rawError === 'object' ? rawError.field : undefined;

            // 4xx 驗證錯誤（如「使用者名稱已存在」）→ 不顯示 toast，讓 caller 自行處理
            // 5xx server error 或沒有 response 的錯誤 → 顯示 toast
            const isServerError = !response || response.status >= 500;

            const err = new Error(errorMsg) as Error & { field?: string; _toasted?: boolean };
            err.field = field;

            if (isServerError || !response) {
                toast.error(errorMsg);
                err._toasted = true;
            }
            // 4xx 驗證錯誤不放 toast，_toasted 保持 undefined

            return Promise.reject(err);
        }

        // 3. 處理網路或其他錯誤（沒有 error.data 的情況）
        const genericMsg = error.message || '網路連線異常';
        toast.error(genericMsg);
        return Promise.reject(error);
    }
);

export default api;
