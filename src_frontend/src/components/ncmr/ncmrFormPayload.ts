import type { NCMR, NCMRCreateInput, NCMRUpdateInput } from '../../types';
import { formatLocalDate } from '../../utils/dateUtils';

export interface NcmrFormValues {
  date: string;
  createDate: string;
  source: string;
  vendor: string;
  material: string;
  productInfo: string;
  batch: string;
  defectQty: string;
  desc: string;
  category: string;
  reason: string;
  inspector: string;
  result: string;
}

export const getTodayText = () => formatLocalDate();

const toText = (value: string | number | null | undefined) => value == null ? '' : String(value);

export const buildNcmrFormState = (
  detail: Partial<NCMR> | null | undefined,
  today = getTodayText(),
): NcmrFormValues => ({
  date: toText(detail?.日期 || detail?.發現日期 || today),
  createDate: toText(detail?.建立日期 || today),
  source: toText(detail?.來源 || '進料'),
  vendor: toText(detail?.廠商),
  material: toText(detail?.材質),
  productInfo: toText(detail?.產品資訊),
  batch: toText(detail?.批號),
  defectQty: detail?.不合格數量 == null ? '' : String(Math.floor(Number(detail.不合格數量))),
  desc: toText(detail?.不良描述),
  category: toText(detail?.不良原因大類),
  reason: toText(detail?.不良原因細項),
  inspector: toText(detail?.發現人員姓名),
  result: toText(detail?.判定結果),
});

export function buildNcmrFormPayload(values: NcmrFormValues): NCMRCreateInput;
export function buildNcmrFormPayload(values: NcmrFormValues, editId: number): NCMRUpdateInput;
export function buildNcmrFormPayload(
  values: NcmrFormValues,
  editId?: number,
): NCMRCreateInput | NCMRUpdateInput {
  const payload: NCMRCreateInput = {
    日期: values.date,
    建立日期: values.createDate,
    來源: values.source,
    廠商: values.vendor,
    材質: values.material,
    產品資訊: values.productInfo,
    批號: values.batch,
    不合格數量: values.defectQty,
    不良描述: values.desc,
    不良原因大類: values.category,
    不良原因細項: values.reason,
    發現人員姓名: values.inspector,
    判定結果: values.result,
  };
  return editId == null ? payload : { ...payload, 識別碼: editId };
}
