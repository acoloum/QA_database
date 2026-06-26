import type { ActionTask } from '../types';

type TaskListEnvelope = {
  data?: unknown;
};

export const normalizeTaskListResponse = (value: unknown): ActionTask[] => {
  if (Array.isArray(value)) return value as ActionTask[];
  if (value && typeof value === 'object') {
    const data = (value as TaskListEnvelope).data;
    return Array.isArray(data) ? data as ActionTask[] : [];
  }
  return [];
};
