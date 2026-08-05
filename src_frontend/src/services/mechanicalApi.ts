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
  /** 逐欄錯誤為欄位索引；工作表層級錯誤（材質無法判定）為 null */
  欄位: number | null;
  錯誤: string;
}

/** 各工作表（產品尺寸）實際套用的材質及其來源 */
export interface MechanicalImportMaterialSource {
  工作表: string;
  產品尺寸: string;
  材質: string;
  來源: '公差檔' | '預設值';
  候選: string[];
  筆數: number;
}

/** 規格界限；下限與上限分開回傳，一個項目只會出現在受管制的那一邊。 */
export interface MechanicalSpecResponse {
  success: boolean;
  limits: Record<string, number>;
  upper_limits: Record<string, number>;
}

/** 表單使用的界限查表：lower[項目] / upper[項目]，查無該項即為 undefined。 */
export interface MechanicalSpecLimits {
  lower: Record<string, number>;
  upper: Record<string, number>;
}

export interface MechanicalImportResult {
  success: boolean;
  message: string;
  created: number;
  skipped: number;
  errors: MechanicalImportError[];
  material_sources: MechanicalImportMaterialSource[];
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
      .get<MechanicalSpecResponse>('/mechanical/spec', {
        params: { material, product_size, vendor_id },
      })
      .then((r) => ({
        lower: r.data.limits ?? {},
        upper: r.data.upper_limits ?? {},
      })),

  getVendors: () =>
    api.get<MechanicalVendorOption[]>('/vendors').then((r) => r.data),

  getOptions: (vendor_id: number) =>
    api.get<MechanicalOptions>('/mechanical/options', { params: { vendor_id } })
      .then((r) => ({ materials: r.data.materials, product_sizes: r.data.product_sizes })),

  stats: (params: MechanicalStatsParams) =>
    api.get<SpcChartData>('/mechanical/stats', { params }).then((r) => r.data),

  /** material 為後援預設材質（僅在公差檔查無該產品尺寸時套用），可留空 */
  importExcel: (file: File, material: string, vendorId?: number) => {
    const formData = new FormData();
    formData.append('file', file);
    if (material) formData.append('material', material);
    if (vendorId) formData.append('vendor_id', String(vendorId));
    return api
      .post<MechanicalImportResult>('/mechanical/tests/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
};
