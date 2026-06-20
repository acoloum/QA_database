import { describe, expect, it } from 'vitest';

import { createCapaDraft } from './capaDraft';
import type { CAPADetail } from '../../types';

const baseCapa = {
  id: 1,
  no: 'CAPA-001',
  source_type: 'ncmr',
  source_id: 10,
  source_info: {
    defect: '外徑NG',
    source: '進料',
    vendor: '測試供應商',
    defect_detail: '超出上限',
    defect_qty: '2',
    total_qty: '10',
  },
  rigor: '完整8D',
  status: '進行中',
  progress: { total_steps: 9, completed_steps: 0, percent: 0, step_status: {} },
} as CAPADetail;

describe('createCapaDraft', () => {
  it('從 CAPA 明細建立 D0-D8 草稿並合併 D7 預設項目', () => {
    const draft = createCapaDraft({
      ...baseCapa,
      D0_symptom: '客訴尺寸異常',
      D2_what: null,
      D2_where: null,
      D2_who: null,
      D2_how: null,
      D7_actions: [{ type: 'pfmea', checked: true, assignee_id: 5, due_date: '2026-06-30' }],
      D8_confirmation: '已確認有效',
    });

    expect(draft.d0Symptom).toBe('客訴尺寸異常');
    expect(draft.d2What).toBe('外徑NG');
    expect(draft.d2Where).toBe('進料');
    expect(draft.d2Who).toBe('測試供應商');
    expect(draft.d2How).toBe('超出上限');
    expect(draft.d2HowMany).toBe('2 / 10 支');
    expect(draft.d7Actions).toHaveLength(7);
    expect(draft.d7Actions[0]).toMatchObject({ type: 'pfmea', checked: true, assignee_id: 5 });
    expect(draft.d8Confirm).toBe('已確認有效');
    expect(draft.activeTab).toBe('d0');
  });

  it('簡化 5D 時以第一個有效步驟作為預設 tab', () => {
    const draft = createCapaDraft({ ...baseCapa, rigor: '簡化5D' });

    expect(draft.d0Rigor).toBe('簡化5D');
    expect(draft.activeTab).toBe('d2');
  });
});
