interface ApiErrorLike {
  response?: {
    data?: {
      error?: string;
      message?: string;
    };
  };
}

export const getReworkErrorMessage = (error: unknown, fallback: string) => {
  const apiError = error as ApiErrorLike;
  return apiError.response?.data?.error || apiError.response?.data?.message || fallback;
};
