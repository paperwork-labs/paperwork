export enum AuthProvider {
  Local = "local",
  Google = "google",
  Apple = "apple",
}

export enum UserRole {
  User = "user",
  Admin = "admin",
}

export enum AdvisorTier {
  Free = "free",
  Premium = "premium",
}

export enum FilingStatusType {
  Single = "single",
  MarriedJoint = "married_joint",
  MarriedSeparate = "married_separate",
  HeadOfHousehold = "head_of_household",
}

export enum FilingStatus {
  Draft = "draft",
  DocumentsUploaded = "documents_uploaded",
  DataConfirmed = "data_confirmed",
  Calculated = "calculated",
  Review = "review",
  Submitted = "submitted",
  Accepted = "accepted",
  Rejected = "rejected",
}

export enum DocumentType {
  W2 = "w2",
  DriversLicense = "drivers_license",
  Misc1099 = "1099_misc",
  Nec1099 = "1099_nec",
}

export enum ExtractionStatus {
  Pending = "pending",
  Processing = "processing",
  Completed = "completed",
  Failed = "failed",
}

export enum IrsStatus {
  Submitted = "submitted",
  Accepted = "accepted",
  Rejected = "rejected",
}

export interface Attribution {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  referral_code?: string;
  landing_page?: string;
}

export interface User {
  id: string;
  email: string;
  full_name?: string;
  referral_code: string;
  auth_provider: AuthProvider;
  email_verified: boolean;
  role: UserRole;
  advisor_tier: AdvisorTier;
  attribution?: Attribution;
  created_at: string;
  updated_at: string;
}

export interface Filing {
  id: string;
  user_id: string;
  tax_year: number;
  filing_status_type?: FilingStatusType;
  status: FilingStatus;
  created_at: string;
  updated_at: string;
  submitted_at?: string;
}

export interface Document {
  id: string;
  filing_id: string;
  document_type: DocumentType;
  extraction_status: ExtractionStatus;
  extraction_data?: Record<string, unknown>;
  confidence_scores?: Record<string, number>;
  created_at: string;
  processed_at?: string;
}

export interface TaxProfile {
  id: string;
  filing_id: string;
  full_name?: string;
  address?: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  date_of_birth?: string;
  total_wages: number;
  total_federal_withheld: number;
  total_state_withheld: number;
  state?: string;
  created_at: string;
}

export interface TaxCalculation {
  id: string;
  filing_id: string;
  adjusted_gross_income: number;
  standard_deduction: number;
  taxable_income: number;
  federal_tax: number;
  state_tax: number;
  total_withheld: number;
  refund_amount: number;
  owed_amount: number;
  ai_insights?: Record<string, unknown>;
  calculated_at: string;
}

export interface Submission {
  id: string;
  filing_id: string;
  transmitter_partner: string;
  submission_id_external?: string;
  irs_status: IrsStatus;
  rejection_codes?: Record<string, string>[];
  submitted_at: string;
  status_updated_at?: string;
}

export interface WaitlistEntry {
  id: string;
  email: string;
  source: string;
  attribution?: Attribution;
  created_at: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error?: string;
}
