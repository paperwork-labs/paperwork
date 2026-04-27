/**
 * Session flag: set after register when account needs admin approval;
 * the login page reads and clears it to show a one-time banner.
 */
export const REGISTERED_PENDING_APPROVAL_KEY = "qm.auth.registeredPendingApproval";
