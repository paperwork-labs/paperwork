import OpenAI from "openai";
import { STATE_CODES } from "../src/types/common";

const openaiApiKey = process.env.OPENAI_API_KEY;
if (!openaiApiKey) {
  throw new Error("Missing OPENAI_API_KEY environment variable. Please set it before running the extraction script.");
}

export const openai = new OpenAI({ apiKey: openaiApiKey });

export async function fetchPageContent(url: string, timeoutMs: number = 15000): Promise<string> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      headers: { "User-Agent": "PaperworkLabs-DataBot/1.0 (hello@paperworklabs.com)" },
      signal: controller.signal,
    });
  } catch (error: any) {
    if (error && error.name === "AbortError") {
      throw new Error(`Request to ${url} timed out after ${timeoutMs}ms`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) throw new Error(`Failed to fetch ${url}: ${response.status}`);
  const html = await response.text();
  // Strip HTML tags, keep text content (reduce token usage)
  return html
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, "")
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 15000); // Cap at ~15k chars to control token cost
}

export async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export { STATE_CODES };
