/**
 * LaunchFree filing lifecycle state machine (orchestrator + portal worker).
 */

export type FilingStatus =
  | "draft"
  | "pending_payment"
  | "payment_complete"
  | "submitting"
  | "submitted"
  | "processing"
  | "confirmed"
  | "failed"
  | "requires_manual";

export interface StatusTransition {
  from: FilingStatus;
  to: FilingStatus;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

export interface FilingTracker {
  formationId: string;
  currentStatus: FilingStatus;
  history: StatusTransition[];
  confirmationNumber?: string;
  filingNumber?: string;
  errorMessage?: string;
  screenshots: string[];
  createdAt: Date;
  updatedAt: Date;
}

const TERMINAL: ReadonlySet<FilingStatus> = new Set(["confirmed"]);

/** Directed edges: valid single-step transitions */
const ALLOWED: Readonly<Record<FilingStatus, ReadonlySet<FilingStatus>>> = {
  draft: new Set([
    "pending_payment",
    "submitting",
    "failed",
    "requires_manual",
  ]),
  pending_payment: new Set(["payment_complete", "failed", "draft"]),
  payment_complete: new Set(["submitting", "failed", "requires_manual"]),
  submitting: new Set(["submitted", "failed", "requires_manual"]),
  submitted: new Set(["processing", "confirmed", "failed", "requires_manual"]),
  processing: new Set(["confirmed", "failed", "requires_manual"]),
  confirmed: new Set([]),
  failed: new Set(["draft", "pending_payment"]),
  requires_manual: new Set(["draft", "confirmed", "failed"]),
};

const ALL_STATUSES: ReadonlySet<FilingStatus> = new Set(
  Object.keys(ALLOWED) as FilingStatus[],
);

function isFilingStatus(value: string): value is FilingStatus {
  return ALL_STATUSES.has(value as FilingStatus);
}

export class StatusTracker {
  private readonly formationId: string;

  private currentStatus: FilingStatus;

  private history: StatusTransition[];

  private confirmationNumber?: string;

  private filingNumber?: string;

  private errorMessage?: string;

  private screenshots: string[];

  private readonly createdAt: Date;

  private updatedAt: Date;

  constructor(formationId: string, initial?: Partial<FilingTracker>) {
    this.formationId = formationId;
    const start = initial?.currentStatus ?? "draft";
    if (!isFilingStatus(start)) {
      throw new Error(`Invalid initial status: ${start}`);
    }
    this.currentStatus = start;
    this.history = initial?.history ? [...initial.history] : [];
    this.confirmationNumber = initial?.confirmationNumber;
    this.filingNumber = initial?.filingNumber;
    this.errorMessage = initial?.errorMessage;
    this.screenshots = initial?.screenshots ? [...initial.screenshots] : [];
    this.createdAt = initial?.createdAt ?? new Date();
    this.updatedAt = initial?.updatedAt ?? new Date();
  }

  getStatus(): FilingStatus {
    return this.currentStatus;
  }

  transition(to: FilingStatus, metadata?: Record<string, unknown>): void {
    if (!StatusTracker.canTransition(this.currentStatus, to)) {
      throw new Error(
        `Invalid filing status transition: ${this.currentStatus} -> ${to}`,
      );
    }
    const now = new Date();
    this.history.push({
      from: this.currentStatus,
      to,
      timestamp: now,
      metadata: metadata ? { ...metadata } : undefined,
    });
    this.currentStatus = to;
    this.updatedAt = now;
  }

  setConfirmationNumber(num: string): void {
    this.confirmationNumber = num;
    this.updatedAt = new Date();
  }

  setFilingNumber(num: string): void {
    this.filingNumber = num;
    this.updatedAt = new Date();
  }

  setError(message: string): void {
    this.errorMessage = message;
    this.updatedAt = new Date();
  }

  addScreenshot(path: string): void {
    this.screenshots.push(path);
    this.updatedAt = new Date();
  }

  toJSON(): FilingTracker {
    return {
      formationId: this.formationId,
      currentStatus: this.currentStatus,
      history: this.history.map((h) => ({
        ...h,
        metadata: h.metadata ? { ...h.metadata } : undefined,
      })),
      confirmationNumber: this.confirmationNumber,
      filingNumber: this.filingNumber,
      errorMessage: this.errorMessage,
      screenshots: [...this.screenshots],
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
    };
  }

  static canTransition(from: FilingStatus, to: FilingStatus): boolean {
    if (from === to) {
      return false;
    }
    if (TERMINAL.has(from)) {
      return false;
    }
    const next = ALLOWED[from];
    return next?.has(to) ?? false;
  }
}
