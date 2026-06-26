import type { ComplaintStatus, ComplaintType, CustomerComplaint } from '../../types';
import { addLocalDays } from '../../utils/dateUtils';

const DEFAULT_REPLY_DAYS: Record<ComplaintType, number> = {
  quality: 14,
  warranty: 30,
  field_failure: 30,
};

export const addDays = (base: string, days: number) => {
  return addLocalDays(base, days);
};

export const getDefaultReplyDeadlines = (complaintDate: string, complaintType: ComplaintType) => ({
  initialReplyDeadline: addDays(complaintDate, 3),
  finalReplyDeadline: addDays(complaintDate, DEFAULT_REPLY_DAYS[complaintType]),
});

interface BuildComplaintPayloadParams {
  isEdit: boolean;
  customer: string;
  complaintDate: string;
  material: string;
  spec: string;
  extrusionNos: string[];
  description: string;
  severity: string;
  defectCategory: string;
  complaintType: ComplaintType;
  deviceSerial: string;
  usageEnv: string;
  failureHours: string;
  initialReplyDeadline: string;
  finalReplyDeadline: string;
  status: string;
  initialReply: string;
  finalReply: string;
}

const trimmedOrUndefined = (value: string) => value.trim() || undefined;

const numberOrUndefined = (value: string) => {
  if (value.trim() === '') return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

export const buildComplaintPayload = ({
  isEdit,
  customer,
  complaintDate,
  material,
  spec,
  extrusionNos,
  description,
  severity,
  defectCategory,
  complaintType,
  deviceSerial,
  usageEnv,
  failureHours,
  initialReplyDeadline,
  finalReplyDeadline,
  status,
  initialReply,
  finalReply,
}: BuildComplaintPayloadParams): Partial<CustomerComplaint> => ({
  customer: customer.trim(),
  complaint_date: complaintDate,
  material: trimmedOrUndefined(material),
  spec: trimmedOrUndefined(spec),
  extrusion_nos: extrusionNos,
  description: description.trim(),
  severity: severity || undefined,
  defect_category: defectCategory || undefined,
  complaint_type: complaintType,
  device_serial: trimmedOrUndefined(deviceSerial),
  usage_env: trimmedOrUndefined(usageEnv),
  failure_hours: numberOrUndefined(failureHours),
  initial_reply_deadline: initialReplyDeadline || undefined,
  final_reply_deadline: finalReplyDeadline || undefined,
  status: isEdit ? (status as ComplaintStatus) : undefined,
  initial_reply: isEdit ? trimmedOrUndefined(initialReply) : undefined,
  final_reply: isEdit ? trimmedOrUndefined(finalReply) : undefined,
});
