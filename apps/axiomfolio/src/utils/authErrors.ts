/**
 * Normalize FastAPI / Axios error `detail` to a single string for display or checks.
 */
export function axiosErrorDetailMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: string }) => (typeof item?.msg === 'string' ? item.msg : JSON.stringify(item)))
      .join('; ');
  }
  if (detail != null && typeof detail === 'object') {
    return JSON.stringify(detail);
  }
  const msg = (err as { message?: string })?.message;
  return typeof msg === 'string' ? msg : '';
}

/**
 * Login blocked until an admin approves the account (matches backend 403 + message).
 */
export function isPendingApprovalLoginError(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status;
  if (status !== 403) return false;
  const lower = axiosErrorDetailMessage(err).toLowerCase();
  return lower.includes('pending') || lower.includes('approval');
}

/**
 * Password login blocked until the user verifies their email (403 + detail about verification).
 */
export function isUnverifiedEmailLoginError(err: unknown): boolean {
  const status = (err as { response?: { status?: number } })?.response?.status;
  if (status !== 403) return false;
  const lower = axiosErrorDetailMessage(err).toLowerCase();
  return lower.includes('verify') || lower.includes('email');
}
