import { useContext } from 'react';
import { AuthContext } from './AuthContext';

/**
 * Hook to access authentication context.
 * Must be used within an AuthProvider.
 * 
 * @returns Auth context with user, isAuthenticated, isLoading, login, logout, and checkAuth
 * @throws Error if used outside of AuthProvider
 */
export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
