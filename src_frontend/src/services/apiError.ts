import type { AxiosResponse } from 'axios';

export interface ApiErrorOptions {
  message: string;
  status?: number;
  code?: string;
  details?: Record<string, unknown>;
  field?: string;
  response?: AxiosResponse;
}

/** 保留後端穩定錯誤欄位，同時維持既有 Error 與 response 相容性。 */
export class ApiError extends Error {
  readonly status?: number;
  readonly code?: string;
  readonly details?: Record<string, unknown>;
  readonly field?: string;
  readonly response?: AxiosResponse;
  _toasted?: boolean;

  constructor({ message, status, code, details, field, response }: ApiErrorOptions) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.field = field;
    this.response = response;
  }
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
  const responseMessage = (
    error as { response?: { data?: { error?: string } } }
  )?.response?.data?.error;
  return responseMessage || fallback;
}

export function apiErrorNeedsToast(error: unknown): boolean {
  return !(error as { _toasted?: boolean } | null)?._toasted;
}
