import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

export interface RoleOption {
    code: string;
    name: string;
    permissions: Record<string, boolean>;
}

export function useRoles() {
    return useQuery<RoleOption[]>({
        queryKey: ['roles'],
        queryFn: async () => {
            const res = await api.get<RoleOption[]>('/roles');
            return res.data;
        },
    });
}
