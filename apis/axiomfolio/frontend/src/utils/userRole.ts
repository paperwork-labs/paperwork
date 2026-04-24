/**
 * Platform admin (operator) access — matches backend UserRole.OWNER and legacy JWT "admin".
 */
export function isPlatformAdminRole(role: string | undefined | null): boolean {
  return role === 'owner' || role === 'admin';
}
