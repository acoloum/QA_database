import { useQuery } from '@tanstack/react-query';
import api from '../services/api';

// 角色選項介面
export interface RoleOption {
    code: string;
    name: string;
}

/**
 * 取得所有可用角色列表（需 user.manage 權限）
 */
export function useRoles() {
    return useQuery<RoleOption[]>({
        queryKey: ['roles'],
        queryFn: async () => {
            const res = await api.get<RoleOption[]>('/roles');
            return res.data;
        },
    });
}
