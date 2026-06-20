import type { ReworkCostDetail, ReworkExecutionDetail, ReworkInspectionDetail } from '../../types';

type ReworkExecutionPayload = Omit<Partial<ReworkExecutionDetail>, '重工單號'> & { 重工單號?: string };
type ReworkInspectionPayload = Omit<Partial<ReworkInspectionDetail>, '重工單號'> & { 重工單號?: string };
type ReworkCostPayload = Omit<Partial<ReworkCostDetail>, '重工單號'> & { 重工單號?: string };

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
  完成數量: parseFloat(completedQty) || 0,
  不良數量: parseFloat(defectQty) || 0,
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
  不良數量: parseInt(defectQty) || 0,
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
