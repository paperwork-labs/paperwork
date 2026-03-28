/**
 * Base Portal Handler
 *
 * Abstract base class for Tier 2 portal automation handlers.
 * Uses Playwright for browser automation with multi-selector fallback strategy.
 */

import type { Browser, BrowserContext, Page } from "playwright";
import type {
  FilingHandler,
  FilingResult,
  FormationRequest,
  PortalConfig,
  PortalStep,
} from "../../types.js";
import { FilingTier, FormationStatus } from "../../types.js";

export abstract class BasePortalHandler implements FilingHandler {
  readonly tier = FilingTier.PORTAL;
  abstract readonly supportedStates: string[];
  protected abstract readonly config: PortalConfig;

  private browser: Browser | null = null;
  private context: BrowserContext | null = null;

  abstract canHandle(stateCode: string): boolean;

  protected abstract mapFormationToFields(
    request: FormationRequest
  ): Record<string, string>;

  async submit(request: FormationRequest): Promise<FilingResult> {
    const screenshots: string[] = [];
    let page: Page | null = null;

    try {
      page = await this.initBrowser();
      const fieldValues = this.mapFormationToFields(request);

      await page.goto(this.config.portalUrl, { waitUntil: "networkidle" });
      screenshots.push(await this.captureScreenshot(page, "initial"));

      for (const step of this.config.steps) {
        await this.executeStep(page, step, fieldValues);
        if (step.screenshotAfter) {
          screenshots.push(await this.captureScreenshot(page, step.name));
        }
      }

      const confirmationResult = await this.extractConfirmation(page);

      return {
        success: true,
        formationId: request.id,
        status: FormationStatus.SUBMITTED,
        tier: this.tier,
        filingNumber: confirmationResult.filingNumber,
        confirmationNumber: confirmationResult.confirmationNumber,
        filedAt: new Date().toISOString(),
        screenshots,
        documents: [],
        retryCount: 0,
      };
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);

      if (page) {
        try {
          screenshots.push(await this.captureScreenshot(page, "error"));
        } catch {
          // Ignore screenshot errors during error handling
        }
      }

      return {
        success: false,
        formationId: request.id,
        status: FormationStatus.FAILED,
        tier: this.tier,
        errorCode: this.categorizeError(errorMessage),
        errorMessage,
        screenshots,
        documents: [],
        retryCount: 0,
      };
    } finally {
      await this.cleanup();
    }
  }

  async checkStatus(formationId: string): Promise<FilingResult> {
    return {
      success: false,
      formationId,
      status: FormationStatus.SUBMITTED,
      tier: this.tier,
      errorCode: "STATUS_CHECK_NOT_IMPLEMENTED",
      errorMessage:
        "Status checking not yet implemented for this state portal",
      screenshots: [],
      documents: [],
      retryCount: 0,
    };
  }

  protected async initBrowser(): Promise<Page> {
    const { chromium } = await import("playwright");

    this.browser = await chromium.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    });

    this.context = await this.browser.newContext({
      viewport: { width: 1280, height: 720 },
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    });

    return this.context.newPage();
  }

  protected async cleanup(): Promise<void> {
    if (this.context) {
      await this.context.close().catch(() => {});
      this.context = null;
    }
    if (this.browser) {
      await this.browser.close().catch(() => {});
      this.browser = null;
    }
  }

  protected async executeStep(
    page: Page,
    step: PortalStep,
    fieldValues: Record<string, string>
  ): Promise<void> {
    if (step.url) {
      await page.goto(step.url, { waitUntil: "networkidle" });
    }

    for (const field of step.fields) {
      const value =
        fieldValues[field.fieldId] ?? field.value ?? field.valueMapping?.[fieldValues[field.fieldId] ?? ""];

      if (value == null) continue;

      const element = await this.findElement(page, field.selector, field.fallbackSelectors);

      if (!element) {
        throw new Error(`Could not find field: ${field.fieldId} (${field.selector})`);
      }

      switch (field.inputType) {
        case "text":
          await element.fill(value);
          break;
        case "select":
          await element.selectOption(value);
          break;
        case "checkbox":
          if (value === "true" || value === "1") {
            await element.check();
          }
          break;
        case "radio":
          await element.check();
          break;
        case "date":
          await element.fill(value);
          break;
        case "file":
          await element.setInputFiles(value);
          break;
      }
    }

    if (step.submitButton) {
      const submitBtn = await this.findElement(page, step.submitButton);
      if (submitBtn) {
        await submitBtn.click();
        if (step.waitForNavigation) {
          await page.waitForLoadState("networkidle");
        }
      }
    }
  }

  protected async findElement(
    page: Page,
    primarySelector: string,
    fallbacks?: string[]
  ): Promise<ReturnType<Page["locator"]> | null> {
    const selectors = [primarySelector, ...(fallbacks ?? [])];

    for (const selector of selectors) {
      try {
        const locator = page.locator(selector);
        const count = await locator.count();
        if (count > 0) {
          return locator.first();
        }
      } catch {
        continue;
      }
    }

    return null;
  }

  protected async captureScreenshot(page: Page, stepName: string): Promise<string> {
    const buffer = await page.screenshot({ fullPage: true });
    const timestamp = Date.now();
    const filename = `${this.config.stateCode}-${stepName}-${timestamp}.png`;
    return `data:image/png;base64,${buffer.toString("base64")}`;
  }

  protected async extractConfirmation(
    page: Page
  ): Promise<{ filingNumber?: string; confirmationNumber?: string }> {
    const result: { filingNumber?: string; confirmationNumber?: string } = {};

    try {
      const confirmationEl = await this.findElement(
        page,
        this.config.confirmationPageSelector
      );
      if (confirmationEl) {
        result.confirmationNumber = await confirmationEl.textContent() ?? undefined;
      }

      if (this.config.filingNumberSelector) {
        const filingEl = await this.findElement(
          page,
          this.config.filingNumberSelector
        );
        if (filingEl) {
          result.filingNumber = await filingEl.textContent() ?? undefined;
        }
      }
    } catch {
      // Continue without confirmation numbers
    }

    return result;
  }

  protected categorizeError(message: string): string {
    const lowerMsg = message.toLowerCase();

    if (lowerMsg.includes("timeout")) return "TIMEOUT";
    if (lowerMsg.includes("network") || lowerMsg.includes("connection"))
      return "NETWORK_ERROR";
    if (lowerMsg.includes("rate") || lowerMsg.includes("throttl"))
      return "RATE_LIMITED";
    if (lowerMsg.includes("session") || lowerMsg.includes("login"))
      return "SESSION_EXPIRED";
    if (lowerMsg.includes("not found") || lowerMsg.includes("selector"))
      return "SELECTOR_CHANGED";
    if (lowerMsg.includes("payment") || lowerMsg.includes("card"))
      return "PAYMENT_FAILED";

    return "UNKNOWN_ERROR";
  }
}
