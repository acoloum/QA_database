import axios from 'axios';

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

// 回應攔截器：處理 401 Token 失效
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Token 失效，清除並重導至登入頁
            // 注意：這裡不能直接使用 useNavigate，因為不在 React Component 中
            // 可以透過 window.location 或者 event bus 處理
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

export default api;
