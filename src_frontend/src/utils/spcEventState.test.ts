import { describe, expect, it } from 'vitest';
import type { SpcEventSummary, SpcStudyResult } from '../types';
import { replaceEvent, replaceEventOcap } from './spcEventState';

const event = {
  id: 81,
  status: 'investigating',
  ocap: null,
} as SpcEventSummary;

const version = {
  monitoring_limit: { events: [event] },
  limit_versions: [{ events: [event] }],
} as SpcStudyResult;

describe('SPC 事件狀態工具', () => {
  it('以 OCAP 回應同步監控界限與版本界限且不修改原物件', () => {
    const ocap = { id: 3, event_id: 81, status: 'closed' } as never;

    const updated = replaceEventOcap(version, 81, ocap);

    expect(updated.monitoring_limit?.events[0].status).toBe('closed');
    expect(updated.limit_versions?.[0].events[0].ocap).toBe(ocap);
    expect(version.monitoring_limit?.events[0]).toBe(event);
  });

  it('以輕量事件回應取代兩處相同事件', () => {
    const serverEvent = { ...event, status: 'closed' } as SpcEventSummary;

    const updated = replaceEvent(version, serverEvent);

    expect(updated.monitoring_limit?.events[0]).toBe(serverEvent);
    expect(updated.limit_versions?.[0].events[0]).toBe(serverEvent);
  });
});
