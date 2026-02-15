import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import type { LoginResponse } from '../types';

const LoginPage = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        try {
            const res = await api.post<LoginResponse>('/login', { username, password });
            if (res.data.token) {
                login(res.data.token, res.data.username, res.data.user_id);
                navigate('/', { replace: true });
            } else {
                setError(res.data.error || '登入失敗');
            }
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.error || '連線錯誤，請稍後再試');
        }
    };

    return (
        <div className="login-container">
            <div className="text-center mb-4">
                <i className="fa-solid fa-user-shield fa-3x" style={{ color: '#6a11cb' }}></i>
            </div>
            <h2 className="login-title">品保管理系統</h2>
            <form onSubmit={handleSubmit}>
                <div className="mb-3">
                    <label htmlFor="username" className="form-label">使用者名稱</label>
                    <input
                        type="text"
                        className="form-control"
                        id="username"
                        required
                        placeholder="請輸入使用者名稱"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                    />
                </div>
                <div className="mb-3">
                    <label htmlFor="password" className="form-label">密碼</label>
                    <input
                        type="password"
                        className="form-control"
                        id="password"
                        required
                        placeholder="請輸入密碼"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                    />
                </div>
                <button type="submit" className="btn btn-login">
                    <i className="fa-solid fa-right-to-bracket me-2"></i>登入
                </button>
            </form>
            {error && (
                <p className="text-danger mt-3 text-center small">{error}</p>
            )}
        </div>
    );
};

export default LoginPage;
