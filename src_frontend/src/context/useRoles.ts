import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import { masterDataKeys } from '../hooks/queryKeys';

export interface RoleOption {
    code: string;
    name: string;
    permissions: Record<string, boolean>;
}

export function useRoles() {
    return useQuery<RoleOption[]>({
        queryKey: masterDataKeys.roles,
        queryFn: async () => {
            const res = await api.get<RoleOption[]>('/roles');
            return res.data;
        },
    });
}
