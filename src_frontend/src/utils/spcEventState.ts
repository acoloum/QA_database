import type {
  SpcEventSummary, SpcLimitVersionSummary, SpcOcapRecord, SpcStudyResult,
} from '../types';

const replaceLimitEvent = (
  limit: SpcLimitVersionSummary,
  eventId: number,
  replacer: (event: SpcEventSummary) => SpcEventSummary,
): SpcLimitVersionSummary => ({
  ...limit,
  events: limit.events.map(event => event.id === eventId ? replacer(event) : event),
});

export const replaceEventOcap = (
  version: SpcStudyResult,
  eventId: number,
  ocap: SpcOcapRecord,
): SpcStudyResult => {
  const update = (event: SpcEventSummary): SpcEventSummary => ({
    ...event,
    status: ocap.status === 'closed' ? 'closed' : 'investigating',
    ocap,
  });
  return {
    ...version,
    monitoring_limit: version.monitoring_limit
      ? replaceLimitEvent(version.monitoring_limit, eventId, update)
      : version.monitoring_limit,
    limit_versions: version.limit_versions?.map(limit =>
      replaceLimitEvent(limit, eventId, update)),
  };
};

export const replaceEvent = (
  version: SpcStudyResult,
  event: SpcEventSummary,
): SpcStudyResult => ({
  ...version,
  monitoring_limit: version.monitoring_limit
    ? replaceLimitEvent(version.monitoring_limit, event.id, () => event)
    : version.monitoring_limit,
  limit_versions: version.limit_versions?.map(limit =>
    replaceLimitEvent(limit, event.id, () => event)),
});
