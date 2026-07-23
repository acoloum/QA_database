import api from './api';
import type {
  MechanicalTestDetail,
  MechanicalTestListItem,
  MechanicalTestPayload,
} from '../types';

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
};
