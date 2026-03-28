/**
 * Filing Engine Orchestrator
 *
 * Central dispatch for LLC formation submissions. Routes to appropriate handler
 * based on state's filing tier (API, Portal, or Mail).
 *
 * Per TASKS.md P3.4a:
 * - Receives formation ID, determines tier, dispatches to correct handler
 * - Status transitions: pending -> submitting -> submitted -> confirmed/failed
 * - Screenshot capture at each portal step
 * - Retry logic (max 3 retries with exponential backoff)
 */

import type {
  FilingHandler,
  FilingOrchestrator,
  FilingResult,
  FilingTier,
  FormationRequest,
} from "./types.js";
import { FormationStatus, getFilingTier } from "./types.js";

const MAX_RETRIES = 3;
const BASE_RETRY_DELAY_MS = 1000;

export class StateFilingOrchestrator implements FilingOrchestrator {
  private handlers: Map<FilingTier, FilingHandler[]> = new Map();
  private stateHandlerCache: Map<string, FilingHandler> = new Map();

  constructor() {
    this.handlers.set("api", []);
    this.handlers.set("portal", []);
    this.handlers.set("mail", []);
  }

  registerHandler(handler: FilingHandler): void {
    const tierHandlers = this.handlers.get(handler.tier) ?? [];
    tierHandlers.push(handler);
    this.handlers.set(handler.tier, tierHandlers);

    for (const state of handler.supportedStates) {
      this.stateHandlerCache.set(state, handler);
    }
  }

  getHandlerForState(stateCode: string): FilingHandler | null {
    const cached = this.stateHandlerCache.get(stateCode);
    if (cached) return cached;

    const tier = getFilingTier(stateCode);
    const handlers = this.handlers.get(tier) ?? [];

    for (const handler of handlers) {
      if (handler.canHandle(stateCode)) {
        this.stateHandlerCache.set(stateCode, handler);
        return handler;
      }
    }

    return null;
  }

  async dispatch(request: FormationRequest): Promise<FilingResult> {
    const handler = this.getHandlerForState(request.stateCode);

    if (!handler) {
      return this.createFailureResult(
        request.id,
        request.stateCode,
        "NO_HANDLER",
        `No filing handler available for state ${request.stateCode}`
      );
    }

    let lastError: Error | null = null;
    let retryCount = 0;

    while (retryCount < MAX_RETRIES) {
      try {
        const result = await handler.submit(request);

        if (result.success || result.status === FormationStatus.MANUAL_QUEUE) {
          return { ...result, retryCount };
        }

        if (this.isRetryableError(result.errorCode)) {
          retryCount++;
          if (retryCount < MAX_RETRIES) {
            await this.delay(this.getRetryDelay(retryCount));
            continue;
          }
        }

        return { ...result, retryCount };
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));
        retryCount++;

        if (retryCount < MAX_RETRIES) {
          await this.delay(this.getRetryDelay(retryCount));
        }
      }
    }

    return this.createFailureResult(
      request.id,
      request.stateCode,
      "MAX_RETRIES_EXCEEDED",
      lastError?.message ?? "Maximum retry attempts exceeded",
      { retryCount, lastError: lastError?.stack }
    );
  }

  async checkStatus(
    formationId: string,
    stateCode: string
  ): Promise<FilingResult> {
    const handler = this.getHandlerForState(stateCode);

    if (!handler) {
      return this.createFailureResult(
        formationId,
        stateCode,
        "NO_HANDLER",
        `No filing handler available for state ${stateCode}`
      );
    }

    return handler.checkStatus(formationId);
  }

  private createFailureResult(
    formationId: string,
    stateCode: string,
    errorCode: string,
    errorMessage: string,
    errorDetails?: Record<string, unknown>
  ): FilingResult {
    return {
      success: false,
      formationId,
      status: FormationStatus.FAILED,
      tier: getFilingTier(stateCode),
      errorCode,
      errorMessage,
      errorDetails,
      retryCount: 0,
      screenshots: [],
      documents: [],
    };
  }

  private isRetryableError(errorCode?: string): boolean {
    const retryableCodes = [
      "TIMEOUT",
      "NETWORK_ERROR",
      "PORTAL_UNAVAILABLE",
      "RATE_LIMITED",
      "SESSION_EXPIRED",
    ];
    return errorCode != null && retryableCodes.includes(errorCode);
  }

  private getRetryDelay(attempt: number): number {
    return BASE_RETRY_DELAY_MS * Math.pow(2, attempt - 1);
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

export function createOrchestrator(): FilingOrchestrator {
  return new StateFilingOrchestrator();
}
