import api from './api';
import type {
  MechanicalTestDetail,
  MechanicalTestListItem,
  MechanicalTestPayload,
  SpcChartData,
} from '../types';

export interface MechanicalStatsParams {
  item: string;
  position: string;
  vendor_id?: string | number;
  material?: string;
  product_size?: string;
  start_date?: string;
  end_date?: string;
}

export interface MechanicalListResponse {
  success: boolean;
  data: MechanicalTestListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface MechanicalVendorOption {
  id: number;
  name: string;
}

export interface MechanicalOptions {
  materials: string[];
  product_sizes: string[];
}

export interface MechanicalImportError {
  工作表: string;
  欄位: number;
  錯誤: string;
}

export interface MechanicalImportResult {
  success: boolean;
  message: string;
  created: number;
  skipped: number;
  errors: MechanicalImportError[];
}

export const mechanicalApi = {
  list: (params: Record<string, string | number | undefined>) =>
    api.get<MechanicalListResponse>('/mechanical/tests', { params }).then((r) => r.data),

  getDetail: (id: number) =>
    api.get<MechanicalTestDetail>(`/mechanical/tests/${id}`).then((r) => r.data),

  create: (payload: MechanicalTestPayload) =>
    api.post<{ success: boolean; id: number }>('/mechanical/tests', payload).then((r) => r.data),

  update: (id: number, payload: MechanicalTestPayload) =>
    api.put<{ success: boolean }>(`/mechanical/tests/${id}`, payload).then((r) => r.data),

  remove: (id: number) =>
    api.delete<{ success: boolean }>(`/mechanical/tests/${id}`).then((r) => r.data),

  getSpec: (material: string, product_size: string, vendor_id?: number) =>
    api
      .get<{ success: boolean; limits: Record<string, number> }>('/mechanical/spec', {
        params: { material, product_size, vendor_id },
      })
      .then((r) => r.data.limits),

  getVendors: () =>
    api.get<MechanicalVendorOption[]>('/vendors').then((r) => r.data),

  getOptions: (vendor_id: number) =>
    api.get<MechanicalOptions>('/mechanical/options', { params: { vendor_id } })
      .then((r) => ({ materials: r.data.materials, product_sizes: r.data.product_sizes })),

  stats: (params: MechanicalStatsParams) =>
    api.get<SpcChartData>('/mechanical/stats', { params }).then((r) => r.data),

  importExcel: (file: File, material: string, vendorId?: number) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('material', material);
    if (vendorId) formData.append('vendor_id', String(vendorId));
    return api
      .post<MechanicalImportResult>('/mechanical/tests/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
};
