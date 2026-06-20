export interface PaginatedResponse<T> {
    data: T[];
    total: number;
    page: number;
    per_page: number;
}

export interface User {
    user_id: string;
    username: string;
    role: string;
    permissions?: Record<string, boolean>;
}

export interface AuthState {
    user: User | null;
    isAuthenticated: boolean;
    isLoading: boolean;
}

export interface LoginResponse {
    token: string;
    username: string;
    user_id: string;
    role: string;
    error?: string;
}

export interface VerifyTokenResponse {
    valid: boolean;
    username: string;
    user_id: string;
    role: string;
    permissions?: Record<string, boolean>;
}

export interface UserRecord {
    id: number;
    username: string;
    role: string;
    inspector_id?: number | null;
    is_active: boolean;
    created_at: string | null;
}

