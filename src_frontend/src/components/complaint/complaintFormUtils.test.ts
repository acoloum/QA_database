import { describe, expect, it } from 'vitest';

import {
  addDays,
  buildComplaintPayload,
  getDefaultReplyDeadlines,
} from './complaintFormUtils';

describe('complaintFormUtils', () => {
  it('計算初步與最終回覆期限', () => {
    expect(addDays('2026-06-20', 3)).toBe('2026-06-23');
    expect(getDefaultReplyDeadlines('2026-06-20', 'quality')).toEqual({
      initialReplyDeadline: '2026-06-23',
      finalReplyDeadline: '2026-07-04',
    });
    expect(getDefaultReplyDeadlines('2026-06-20', 'warranty').finalReplyDeadline).toBe('2026-07-20');
  });

  it('建立新增客訴 payload 並把空字串轉為 undefined', () => {
    const payload = buildComplaintPayload({
      isEdit: false,
      customer: '  客戶A  ',
      complaintDate: '2026-06-20',
      material: '',
      spec: '  T6 ',
      extrusionNos: ['EX-1'],
      description: '  尺寸不良  ',
      severity: 'Major',
      defectCategory: '',
      complaintType: 'quality',
      deviceSerial: '',
      usageEnv: '',
      failureHours: '',
      initialReplyDeadline: '2026-06-23',
      finalReplyDeadline: '2026-07-04',
      status: '待處理',
      initialReply: '草稿',
      finalReply: '結論',
    });

    expect(payload).toEqual({
      customer: '客戶A',
      complaint_date: '2026-06-20',
      material: undefined,
      spec: 'T6',
      extrusion_nos: ['EX-1'],
      description: '尺寸不良',
      severity: 'Major',
      defect_category: undefined,
      complaint_type: 'quality',
      device_serial: undefined,
      usage_env: undefined,
      failure_hours: undefined,
      initial_reply_deadline: '2026-06-23',
      final_reply_deadline: '2026-07-04',
      status: undefined,
      initial_reply: undefined,
      final_reply: undefined,
    });
  });

  it('編輯 payload 會包含狀態與回覆內容', () => {
    const payload = buildComplaintPayload({
      isEdit: true,
      customer: '客戶A',
      complaintDate: '2026-06-20',
      material: '6061',
      spec: 'T6',
      extrusionNos: [],
      description: '現場故障',
      severity: '',
      defectCategory: '尺寸不良',
      complaintType: 'field_failure',
      deviceSerial: ' SN-1 ',
      usageEnv: '戶外',
      failureHours: '12',
      initialReplyDeadline: '',
      finalReplyDeadline: '',
      status: '處理中',
      initialReply: ' 已回覆 ',
      finalReply: '',
    });

    expect(payload.status).toBe('處理中');
    expect(payload.initial_reply).toBe('已回覆');
    expect(payload.final_reply).toBeUndefined();
    expect(payload.failure_hours).toBe(12);
    expect(payload.device_serial).toBe('SN-1');
  });
});
