import { render, screen, cleanup } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi, afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
import { metadata as disclaimerMetadata } from "../disclaimer/page";
import DisclaimerPage from "../disclaimer/page";
import { metadata as privacyMetadata } from "../privacy/page";
import PrivacyPolicyPage from "../privacy/page";
import { metadata as termsMetadata } from "../terms/page";
import TermsOfServicePage from "../terms/page";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("legal pages metadata", () => {
  it("terms page exports metadata", () => {
    expect(termsMetadata.title).toBe("Terms of Service");
    expect(typeof termsMetadata.description).toBe("string");
    expect((termsMetadata.description as string).length).toBeGreaterThan(20);
  });

  it("privacy page exports metadata", () => {
    expect(privacyMetadata.title).toBe("Privacy Policy");
    expect(typeof privacyMetadata.description).toBe("string");
    expect((privacyMetadata.description as string).length).toBeGreaterThan(20);
  });

  it("disclaimer page exports metadata", () => {
    expect(disclaimerMetadata.title).toBe("Disclaimer");
    expect(typeof disclaimerMetadata.description).toBe("string");
    expect((disclaimerMetadata.description as string).length).toBeGreaterThan(20);
  });
});

describe("Terms of Service content", () => {
  it("includes UPL-related disclaimer language (not a law firm, no attorney-client relationship)", () => {
    render(<TermsOfServicePage />);
    const article = screen.getByRole("article");
    expect(article.textContent).toMatch(/not a law firm/i);
    expect(article.textContent).toMatch(/attorney-client relationship/i);
    expect(article.textContent).toMatch(/legal advice/i);
  });

  it('shows a "Last updated" line with a date', () => {
    render(<TermsOfServicePage />);
    const article = screen.getByRole("article");
    expect(article.textContent).toMatch(/Last updated:/i);
    expect(article.textContent).toMatch(/March.*2026/i);
  });
});

describe("Privacy Policy content", () => {
  it("mentions CCPA and GDPR rights language", () => {
    render(<PrivacyPolicyPage />);
    const article = screen.getByRole("article");
    expect(article.textContent).toMatch(/CCPA/i);
    expect(article.textContent).toMatch(/GDPR/i);
  });

  it('shows a "Last updated" line with a date', () => {
    render(<PrivacyPolicyPage />);
    const article = screen.getByRole("article");
    expect(article.textContent).toMatch(/Last updated:/i);
    expect(article.textContent).toMatch(/March.*2026/i);
  });
});

describe("Disclaimer content", () => {
  it("includes UPL heading and document-preparation limitation", () => {
    render(<DisclaimerPage />);
    const article = screen.getByRole("article");
    expect(article.textContent).toMatch(/Unauthorized practice of law/i);
    expect(article.textContent).toMatch(/\bUPL\b/);
    expect(article.textContent).toMatch(/document preparation/i);
  });

  it('shows a "Last updated" line with a date', () => {
    render(<DisclaimerPage />);
    const article = screen.getByRole("article");
    expect(article.textContent).toMatch(/Last updated:/i);
    expect(article.textContent).toMatch(/March.*2026/i);
  });
});

describe("legal module imports", () => {
  it("all legal route modules resolve without error", async () => {
    await expect(import("../terms/page")).resolves.toBeTruthy();
    await expect(import("../privacy/page")).resolves.toBeTruthy();
    await expect(import("../disclaimer/page")).resolves.toBeTruthy();
  });
});
