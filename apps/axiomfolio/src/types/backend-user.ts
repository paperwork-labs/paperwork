/** Shape returned by GET /api/v1/auth/me (AxiomFolio backend). */
export type BackendUserUiPreferences = {
  color_mode_preference?: string;
  table_density?: string;
  coverage_histogram_window_days?: number;
  color_palette?: string;
  [key: string]: unknown;
};

export type BackendUser = {
  id: number;
  username: string;
  email: string;
  full_name?: string | null;
  is_verified?: boolean | null;
  is_active: boolean;
  role?: string | null;
  timezone?: string | null;
  currency_preference?: string | null;
  notification_preferences?: unknown;
  ui_preferences?: BackendUserUiPreferences | null;
  has_password?: boolean;
  avatar_url?: string | null;
  is_approved?: boolean;
  created_at?: string;
};
