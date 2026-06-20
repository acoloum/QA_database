export interface ExtrusionToleranceRow {
  測量項目: string;
  公差下限: string;
  公差上限: string;
  標準值: string;
}

export interface BuildExtrusionTolerancePayloadParams {
  material: string;
  spec: string;
  vendor: string;
  note: string;
  createdAt: string;
  rows: ExtrusionToleranceRow[];
}

export const createExtrusionToleranceRow = (): ExtrusionToleranceRow => ({
  測量項目: '外徑',
  公差下限: '',
  公差上限: '',
  標準值: '',
});

const parseOptionalNumber = (value: string) => {
  if (value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export const buildExtrusionTolerancePayload = ({
  material,
  spec,
  vendor,
  note,
  createdAt,
  rows,
}: BuildExtrusionTolerancePayloadParams) => ({
  材質: material.trim(),
  規格: spec.trim() || null,
  廠商: vendor.trim() || null,
  備註: note.trim() || null,
  建立日期: createdAt,
  details: rows.map(row => ({
    測量項目: row.測量項目,
    公差下限: parseOptionalNumber(row.公差下限),
    公差上限: parseOptionalNumber(row.公差上限),
    標準值: parseOptionalNumber(row.標準值),
    單位: 'mm',
  })),
});
