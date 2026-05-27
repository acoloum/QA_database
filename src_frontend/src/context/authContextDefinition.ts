import { createContext } from 'react';
import type { AuthState } from '../types';

export interface AuthContextType extends AuthState {
    login: (token: string, username: string, userId: string, role?: string) => void;
    logout: () => void;
    checkAuth: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
