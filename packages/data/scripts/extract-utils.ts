import OpenAI from "openai";
import { STATE_CODES } from "../src/types/common";

export const openai = new OpenAI();

export async function fetchPageContent(url: string): Promise<string> {
  const response = await fetch(url, {
    headers: { "User-Agent": "PaperworkLabs-DataBot/1.0 (hello@paperworklabs.com)" },
  });
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
