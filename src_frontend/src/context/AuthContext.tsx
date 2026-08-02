import React, { useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import api from '../services/api';
import type { User, VerifyTokenResponse } from '../types';
import { AuthContext } from './authContextDefinition';

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);

    const login = (
        token: string,
        username: string,
        userId: string,
        role: string = 'user',
        permissions: Record<string, boolean> = {}
    ) => {
        localStorage.setItem('authToken', token);
        localStorage.setItem('username', username);
        setUser({ username, user_id: userId, role, permissions });
        setIsAuthenticated(true);
    };

    const logout = () => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        setUser(null);
        setIsAuthenticated(false);
    };

    const checkAuth = useCallback(async () => {
        const token = localStorage.getItem('authToken');
        if (!token) {
            setIsLoading(false);
            return;
        }

        try {
            // 呼叫後端驗證 API
            const response = await api.get<VerifyTokenResponse>('/verify-token');
            if (response.data.valid) {
                setUser({
                    username: response.data.username,
                    user_id: response.data.user_id,
                    role: response.data.role ?? 'user',
                    permissions: response.data.permissions ?? {}
                });
                setIsAuthenticated(true);
            } else {
                logout();
            }
        } catch (error) {
            console.error('Token verification failed:', error);
            logout();
        } finally {
            setIsLoading(false);
        }
    }, []);

    // useCallback 確保引用穩定：hasPermission 傳入 memo 化子元件/action 時不因 Provider 重繪而失效
    const hasPermission = useCallback((perm: string): boolean => {
        if (!user) return false;
        if (user.role === 'admin') return true;
        return user.permissions?.[perm] === true;
    }, [user]);

    useEffect(() => {
        checkAuth();
    }, [checkAuth]);

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout, checkAuth, hasPermission }}>
            {children}
        </AuthContext.Provider>
    );
};
