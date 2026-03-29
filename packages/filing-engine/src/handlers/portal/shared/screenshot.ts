/**
 * Step screenshots for portal run audit trails (no PII in filenames — caller supplies step labels).
 */

import { mkdir } from "node:fs/promises";
import path from "node:path";

import type { Page } from "playwright";

export interface ScreenshotResult {
  path: string;
  timestamp: Date;
  step: string;
}

function sanitizeStepSegment(step: string): string {
  const cleaned = step
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned.length > 0 ? cleaned : "step";
}

function buildFilename(step: string, timestamp: Date): string {
  const iso = timestamp.toISOString().replace(/[:.]/g, "-");
  return `${iso}_${sanitizeStepSegment(step)}.png`;
}

async function ensureDir(dir: string): Promise<void> {
  try {
    await mkdir(dir, { recursive: true });
  } catch (cause) {
    const msg = cause instanceof Error ? cause.message : String(cause);
    throw new Error(`captureStep: could not create output directory ${JSON.stringify(dir)}: ${msg}`);
  }
}

export async function captureStep(
  page: Page,
  step: string,
  outputDir: string
): Promise<ScreenshotResult> {
  const timestamp = new Date();
  const fileName = buildFilename(step, timestamp);
  const filePath = path.join(outputDir, fileName);

  await ensureDir(outputDir);

  try {
    await page.screenshot({ path: filePath, fullPage: false });
  } catch (cause) {
    const msg = cause instanceof Error ? cause.message : String(cause);
    throw new Error(
      `captureStep: screenshot failed for step ${JSON.stringify(step)} at ${filePath}: ${msg}`
    );
  }

  return { path: filePath, timestamp, step };
}

export async function captureFullPage(
  page: Page,
  step: string,
  outputDir: string
): Promise<ScreenshotResult> {
  const timestamp = new Date();
  const fileName = buildFilename(step, timestamp).replace(/\.png$/, "_full.png");
  const filePath = path.join(outputDir, fileName);

  await ensureDir(outputDir);

  try {
    await page.screenshot({ path: filePath, fullPage: true });
  } catch (cause) {
    const msg = cause instanceof Error ? cause.message : String(cause);
    throw new Error(
      `captureFullPage: screenshot failed for step ${JSON.stringify(step)} at ${filePath}: ${msg}`
    );
  }

  return { path: filePath, timestamp, step };
}
