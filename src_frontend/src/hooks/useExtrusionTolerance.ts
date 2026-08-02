import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import { compactParams } from '../utils/queryParams';
import toast from 'react-hot-toast';
import { extrusionToleranceKeys } from './queryKeys';

// ---- 型別定義 ----

export interface ExtrusionToleranceItem {
    識別碼: number;
    材質: string;
    規格: string;
    廠商: string;
    備註: string;
    建立日期: string;
}

export interface ExtrusionToleranceDetailItem {
    識別碼?: number;
    測量項目: string;
    測量位置: string;
    公差下限: number | null;
    公差上限: number | null;
    標準值: number | null;
    單位: string;
    特性重要度?: string;
}

export interface ExtrusionToleranceDetailResponse {
    success: boolean;
    main: ExtrusionToleranceItem;
    details: ExtrusionToleranceDetailItem[];
}

export interface ExtrusionToleranceCheckResult {
    found: boolean;
    tolerance_id?: number;
    material?: string;
    spec?: string;
    tolerances?: {
        項目: string;
        位置: string;
        尺寸下限: number | null;
        尺寸上限: number | null;
        公差下限: number | null;
        公差上限: number | null;
        標準值: number | null;
        單位: string;
    }[];
    priority_name?: string;
}

// ---- Hooks ----

export const useExtrusionToleranceList = (params: {
    page: number;
    page_size: number;
    material?: string;
    spec?: string;
    vendor?: string;
}) =>
    useQuery({
        queryKey: extrusionToleranceKeys.list(params),
        queryFn: async () => {
            const res = await api.get('/extrusion-tolerance/search', {
                params: {
                    page: params.page,
                    page_size: params.page_size,
                    ...compactParams({
                        material: params.material,
                        spec: params.spec,
                        vendor: params.vendor,
                    }),
                },
            });
            return res.data;
        },
        placeholderData: (prev) => prev,
    });

export const useExtrusionToleranceDetail = (id: number | null) =>
    useQuery({
        queryKey: extrusionToleranceKeys.detail(id),
        queryFn: async () => {
            if (!id) return null;
            const res = await api.get(`/extrusion-tolerance/${id}`);
            return res.data as ExtrusionToleranceDetailResponse;
        },
        enabled: !!id,
    });

export const useExtrusionToleranceOptions = () =>
    useQuery({
        queryKey: extrusionToleranceKeys.options,
        queryFn: async () => {
            const res = await api.get('/extrusion-tolerance/options');
            return res.data as { materials: string[]; specs: string[]; vendors: string[] };
        },
        staleTime: 5 * 60 * 1000,
    });

export const useAddExtrusionTolerance = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: object) => {
            const res = await api.post('/extrusion-tolerance/add', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('新增成功');
            qc.invalidateQueries({ queryKey: extrusionToleranceKeys.root });
            qc.invalidateQueries({ queryKey: extrusionToleranceKeys.options });
        },
        onError: () => {
            toast.error('新增失敗，請稍後再試');
        },
    });
};

export const useUpdateExtrusionTolerance = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: object }) => {
            const res = await api.post(`/extrusion-tolerance/update/${id}`, data);
            return res.data;
        },
        onSuccess: (_d, vars) => {
            toast.success('更新成功');
            qc.invalidateQueries({ queryKey: extrusionToleranceKeys.root });
            qc.invalidateQueries({ queryKey: extrusionToleranceKeys.detail(vars.id) });
        },
        onError: () => {
            toast.error('更新失敗，請稍後再試');
        },
    });
};

export const useDeleteExtrusionTolerance = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.post(`/extrusion-tolerance/delete/${id}`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('刪除成功');
            qc.invalidateQueries({ queryKey: extrusionToleranceKeys.root });
        },
        onError: () => {
            toast.error('刪除失敗，請稍後再試');
        },
    });
};

export const useExtrusionToleranceCheck = (material: string, spec: string, vendorId?: number) =>
    useQuery({
        queryKey: extrusionToleranceKeys.check(material, spec, vendorId),
        queryFn: async () => {
            const res = await api.get('/extrusion-tolerance/check', {
                // material/spec 一律送出（後端以空值代表未指定），vendor_id 有給才帶
                params: { material, spec, ...(vendorId !== undefined ? { vendor_id: vendorId } : {}) },
            });
            return res.data as { success: boolean } & ExtrusionToleranceCheckResult;
        },
        enabled: !!material,
        staleTime: 60 * 1000,
    });
