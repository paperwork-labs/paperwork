/** Circle + delegated access scaffolding — WS-76 PR-28 */

export type CircleMember = {
  user_id: string;
  display_name: string;
  role: "owner" | "member";
  avatar_url?: string;
};

export type Circle = {
  id: string;
  type: "household" | "family" | "partners";
  name: string;
  members: CircleMember[];
  created_by: string;
  created_at: string;
};

export type DelegatedShare = {
  id: string;
  owner_id: string;
  delegate_id: string;
  delegate_name: string;
  scope: string[];
  expires_at: string | null;
  watermark: boolean;
  created_at: string;
};

export type CirclesSeedFile = {
  circles: Circle[];
  delegated_shares: DelegatedShare[];
};
