/**
 * Dashboard formation list/detail — server-side data layer.
 * Replace mock implementation with LaunchFree API + session when available.
 */

export type FormationDashboardStatus =
  | "draft"
  | "pending"
  | "submitted"
  | "confirmed"
  | "failed";

export interface FormationStatusEvent {
  status: FormationDashboardStatus;
  timestamp: string;
  description: string;
}

export interface FormationSummary {
  id: string;
  llcName: string;
  stateCode: string;
  status: FormationDashboardStatus;
  createdAt: string;
}

export interface FormationDetail extends FormationSummary {
  businessPurpose?: string;
  managementType?: "member" | "manager";
  principalCity?: string;
  filingConfirmationNumber?: string | null;
  /** Presigned or app URL for articles PDF; null until available */
  articlesPdfUrl?: string | null;
  statusHistory: FormationStatusEvent[];
}

const MOCK_FORMATIONS: FormationDetail[] = [
  {
    id: "fmt_demo_confirmed",
    llcName: "Riverlight Studio LLC",
    stateCode: "CA",
    status: "confirmed",
    createdAt: "2026-01-12T18:22:00.000Z",
    businessPurpose: "Creative services",
    managementType: "member",
    principalCity: "Los Angeles",
    filingConfirmationNumber: "2026011288421",
    articlesPdfUrl: null,
    statusHistory: [
      {
        status: "draft",
        timestamp: "2026-01-12T17:00:00.000Z",
        description: "Formation questionnaire started",
      },
      {
        status: "pending",
        timestamp: "2026-01-12T17:45:00.000Z",
        description: "Documents generated; filing queued",
      },
      {
        status: "submitted",
        timestamp: "2026-01-12T18:05:00.000Z",
        description: "Filed with California Secretary of State",
      },
      {
        status: "confirmed",
        timestamp: "2026-01-12T18:22:00.000Z",
        description: "Filing accepted; your LLC is active",
      },
    ],
  },
  {
    id: "fmt_demo_pending",
    llcName: "Northwind Goods LLC",
    stateCode: "DE",
    status: "pending",
    createdAt: "2026-03-20T14:10:00.000Z",
    businessPurpose: "E-commerce retail",
    managementType: "manager",
    principalCity: "Wilmington",
    filingConfirmationNumber: null,
    articlesPdfUrl: null,
    statusHistory: [
      {
        status: "draft",
        timestamp: "2026-03-20T14:00:00.000Z",
        description: "Formation questionnaire started",
      },
      {
        status: "pending",
        timestamp: "2026-03-20T14:10:00.000Z",
        description: "Payment received; preparing state submission",
      },
    ],
  },
  {
    id: "fmt_demo_draft",
    llcName: "Summit Labs LLC",
    stateCode: "TX",
    status: "draft",
    createdAt: "2026-03-27T09:00:00.000Z",
    businessPurpose: "Software development",
    managementType: "member",
    principalCity: "Austin",
    filingConfirmationNumber: null,
    articlesPdfUrl: null,
    statusHistory: [
      {
        status: "draft",
        timestamp: "2026-03-27T09:00:00.000Z",
        description: "Saved as draft — finish your application to file",
      },
    ],
  },
];

export async function getUserFormations(): Promise<FormationSummary[]> {
  // TODO: session user id → GET /api/v1/formations
  return MOCK_FORMATIONS.map(
    ({
      id,
      llcName,
      stateCode,
      status,
      createdAt,
    }): FormationSummary => ({
      id,
      llcName,
      stateCode,
      status,
      createdAt,
    })
  );
}

export async function getFormationById(
  formationId: string
): Promise<FormationDetail | null> {
  const found = MOCK_FORMATIONS.find((f) => f.id === formationId);
  return found ?? null;
}

export function getNextStepsGuidance(
  status: FormationDashboardStatus
): { title: string; body: string } {
  switch (status) {
    case "draft":
      return {
        title: "Finish your application",
        body: "Complete the formation wizard so we can generate your articles and file with the state.",
      };
    case "pending":
      return {
        title: "We are processing your filing",
        body: "Our team is preparing or submitting your documents. You will see updates here as the state moves your filing forward.",
      };
    case "submitted":
      return {
        title: "Waiting on the state",
        body: "Your filing has been submitted. Confirmation from the Secretary of State can take from a few hours to several business days.",
      };
    case "confirmed":
      return {
        title: "Your LLC is official",
        body: "Keep your confirmation number for your records. Next, consider an EIN, operating agreement, and any state annual reports.",
      };
    case "failed":
      return {
        title: "Filing needs attention",
        body: "Something blocked this submission. Check your email for details or contact support — we will help you correct and resubmit.",
      };
  }
}
