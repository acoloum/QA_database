import { useQuery } from '@tanstack/react-query';

import api from '../services/api';
import type { Inspector } from '../types';

export interface UseInspectorsOptions {
    group?: string;
    enabled?: boolean;
}

export const useInspectors = (options: UseInspectorsOptions = {}) => {
    const { group, enabled = true } = options;

    return useQuery({
        queryKey: ['inspectors', group ?? 'all'],
        queryFn: async () => {
            const res = await api.get<Inspector[]>('/inspectors', { params: group ? { group } : undefined });
            return res.data;
        },
        enabled,
        staleTime: 60 * 60 * 1000,
    });
};
