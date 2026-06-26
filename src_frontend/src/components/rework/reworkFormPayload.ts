import type { ReworkCostDetail, ReworkExecutionDetail, ReworkInspectionDetail } from '../../types';

export type ReworkExecutionPayload = Omit<Partial<ReworkExecutionDetail>, '重工單號'> & { 重工單號?: string };
export type ReworkInspectionPayload = Omit<Partial<ReworkInspectionDetail>, '重工單號'> & { 重工單號?: string };
export type ReworkCostPayload = Omit<Partial<ReworkCostDetail>, '重工單號'> & { 重工單號?: string };

export interface ReworkApprovalPayload {
  rework_id: number;
  action: string;
  opinion: string;
  審核人員姓名: string;
}

export interface ReworkApplicationPayload {
  NCMR_ID: number | null;
  申請人員姓名: string;
  部門: string;
  緊急程度: string;
  產品資訊: string;
  批號: string;
  重工數量: number;
  申請原因: string;
  預計完成日期: string;
}

export interface ReworkApplicationFormValues {
  ncmrId: string;
  applicant: string;
  department: string;
  urgency: string;
  productInfo: string;
  batchNo: string;
  quantity: string;
  reason: string;
  expectedDate: string;
}

export interface ReworkApplicationUpdatePayload {
  申請人員姓名: string;
  部門: string;
  緊急程度: '普通' | '重要' | '緊急';
  廠商: string;
  材質: string;
  產品資訊: string;
  批號: string;
  重工數量?: number;
  申請原因: string;
  預計完成日期: string;
}

export interface ReworkApplicationUpdateFormValues {
  applicant: string;
  department: string;
  urgency: '普通' | '重要' | '緊急';
  vendor: string;
  material: string;
  spec: string;
  batchNo: string;
  reworkQty: string;
  reason: string;
  expectedDate: string;
}

export interface ReworkExecutionFormValues {
  reworkNumber?: string;
  responsiblePerson: string;
  department: string;
  collaborators: string;
  startTime: string;
  expectedEndTime: string;
  actualEndTime: string;
  equipment: string;
  method: string;
  sopNo: string;
  consumables: string;
  completedQty: string;
  defectQty: string;
  status: string;
  abnormalStatus: string;
}

export interface ReworkInspectionFormValues {
  reworkNumber?: string;
  inspector: string;
  inspectionItem: string;
  inspectionResult: string;
  defectQty: string;
  inspectionDate: string;
  remark: string;
}

export interface ReworkCostFormValues {
  reworkNumber?: string;
  costType: string;
  costItem: string;
  unitCost: string;
  quantity: string;
  currency: string;
  recorder: string;
  remark: string;
}

export const formatDateTimeLocal = (dateStr: string) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const parseReworkCostNumber = (value: string, fallback = 0) => {
  if (value.trim() === '') return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export const calculateReworkTotalCost = (unitCost: string, quantity: string) =>
  parseReworkCostNumber(unitCost, 0) * parseReworkCostNumber(quantity, 0);

const parseIntegerOrNull = (value: string) => {
  if (value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : null;
};

export const buildReworkApplicationPayload = ({
  ncmrId,
  applicant,
  department,
  urgency,
  productInfo,
  batchNo,
  quantity,
  reason,
  expectedDate,
}: ReworkApplicationFormValues): ReworkApplicationPayload => ({
  NCMR_ID: parseIntegerOrNull(ncmrId),
  申請人員姓名: applicant,
  部門: department,
  緊急程度: urgency,
  產品資訊: productInfo,
  批號: batchNo,
  重工數量: parseReworkCostNumber(quantity, 0),
  申請原因: reason,
  預計完成日期: expectedDate,
});

export const buildReworkApplicationUpdatePayload = ({
  applicant,
  department,
  urgency,
  vendor,
  material,
  spec,
  batchNo,
  reworkQty,
  reason,
  expectedDate,
}: ReworkApplicationUpdateFormValues): ReworkApplicationUpdatePayload => {
  const payload: ReworkApplicationUpdatePayload = {
    申請人員姓名: applicant,
    部門: department,
    緊急程度: urgency,
    廠商: vendor,
    材質: material,
    產品資訊: spec,
    批號: batchNo,
    申請原因: reason,
    預計完成日期: expectedDate,
  };
  if (reworkQty.trim() !== '') {
    payload.重工數量 = parseReworkCostNumber(reworkQty, 0);
  }
  return payload;
};

export const buildReworkExecutionPayload = ({
  reworkNumber,
  responsiblePerson,
  department,
  collaborators,
  startTime,
  expectedEndTime,
  actualEndTime,
  equipment,
  method,
  sopNo,
  consumables,
  completedQty,
  defectQty,
  status,
  abnormalStatus,
}: ReworkExecutionFormValues): ReworkExecutionPayload => ({
  ...(reworkNumber ? { 重工單號: reworkNumber } : {}),
  ...(responsiblePerson ? { 負責人員姓名: responsiblePerson } : {}),
  ...(department ? { 執行部門: department } : {}),
  ...(collaborators ? { 協同人員: collaborators } : {}),
  ...(startTime ? { 開始時間: startTime } : {}),
  ...(expectedEndTime ? { 預計完成時間: expectedEndTime } : {}),
  ...(actualEndTime ? { 實際完成時間: actualEndTime } : {}),
  ...(equipment ? { 使用設備: equipment } : {}),
  ...(method ? { 重工方式: method } : {}),
  ...(sopNo ? { SOP編號: sopNo } : {}),
  ...(consumables ? { 耗材記錄: consumables } : {}),
  完成數量: parseReworkCostNumber(completedQty, 0),
  不良數量: parseReworkCostNumber(defectQty, 0),
  ...(status ? { 執行狀況: status } : {}),
  ...(abnormalStatus ? { 異常狀況: abnormalStatus } : {}),
});

export const buildReworkInspectionPayload = ({
  reworkNumber,
  inspector,
  inspectionItem,
  inspectionResult,
  defectQty,
  inspectionDate,
  remark,
}: ReworkInspectionFormValues): ReworkInspectionPayload => ({
  ...(reworkNumber ? { 重工單號: reworkNumber } : {}),
  ...(inspector ? { 檢驗人員姓名: inspector } : {}),
  ...(inspectionItem ? { 檢驗項目: inspectionItem } : {}),
  ...(inspectionResult ? { 檢驗結果: inspectionResult } : {}),
  不良數量: parseReworkCostNumber(defectQty, 0),
  ...(inspectionDate ? { 檢驗日期: inspectionDate } : {}),
  ...(remark ? { 檢驗備註: remark } : {}),
});

export const buildReworkCostPayload = ({
  reworkNumber,
  costType,
  costItem,
  unitCost,
  quantity,
  currency,
  recorder,
  remark,
}: ReworkCostFormValues): ReworkCostPayload => {
  const qty = parseReworkCostNumber(quantity, 1);
  const uCost = parseReworkCostNumber(unitCost, 0);
  const totalCost = uCost * qty;
  return {
    ...(reworkNumber ? { 重工單號: reworkNumber } : {}),
    ...(costType ? { 成本類型: costType } : {}),
    ...(costItem ? { 成本項目: costItem } : {}),
    單位成本: uCost,
    數量: qty,
    總成本: totalCost,
    ...(currency ? { 成本幣別: currency } : {}),
    ...(recorder ? { 記錄人員姓名: recorder } : {}),
    ...(remark ? { 備註: remark } : {}),
  };
};
