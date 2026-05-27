import { createContext } from 'react';
import type { AuthState } from '../types';

export interface AuthContextType extends AuthState {
    login: (token: string, username: string, userId: string, role?: string, permissions?: Record<string, boolean>) => void;
    logout: () => void;
    checkAuth: () => Promise<void>;
    hasPermission: (perm: string) => boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
