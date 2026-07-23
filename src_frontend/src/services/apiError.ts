export type ApiError = Error & { _toasted?: boolean };

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
