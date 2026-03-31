import React, { createContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import api from '../services/api';
import type { AuthState, User, VerifyTokenResponse } from '../types';

interface AuthContextType extends AuthState {
    login: (token: string, username: string, userId: string, role?: string) => void;
    logout: () => void;
    checkAuth: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);

    const login = (token: string, username: string, userId: string, role: string = 'user') => {
        localStorage.setItem('authToken', token);
        localStorage.setItem('username', username);
        setUser({ username, user_id: userId, role });
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
                    role: response.data.role ?? 'user'
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

    useEffect(() => {
        checkAuth();
    }, [checkAuth]);

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, logout, checkAuth }}>
            {children}
        </AuthContext.Provider>
    );
};
