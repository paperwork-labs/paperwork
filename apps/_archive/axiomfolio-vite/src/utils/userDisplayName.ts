/**
 * Display name for nav and header — trim-only, no title-casing.
 * Title-casing mangled legitimate names ("McDonald", "de la Rosa"); users
 * control exact spelling in Settings > Profile.
 */
export function formatUserDisplayName(
  user: { full_name?: string | null; username?: string } | null,
): string {
  if (!user) return 'Guest';
  const raw = (user.full_name?.trim() || user.username?.trim() || 'Guest').trim();
  return raw || 'Guest';
}
