import { describe, expect, it } from "vitest";

import type { OAuthCredentials, OAuthTokens } from "../types.js";
import {
  fidelityAdapter,
  ibkrAdapter,
  schwabAdapter,
  tastytradeAdapter,
} from "../index.js";
import {
  buildPkceUrl,
  generateCodeChallenge,
  generateCodeVerifier,
} from "../oauth.js";

const BASE64URL = /^[A-Za-z0-9_-]+$/;

/** Minimal token bag for exercising stub methods — not provider-issued data. */
const dummyTokens: OAuthTokens = {
  accessToken: "test-access",
  refreshToken: "test-refresh",
  expiresAt: 0,
  scope: [],
  raw: {},
};

const sampleCreds: OAuthCredentials = {
  clientId: "cid-demo",
  clientSecret: "secret-demo",
  redirectUri: "https://example.com/oauth/callback",
  scopes: ["read", "trade"],
};

describe("generateCodeVerifier", () => {
  it.each([43, 64, 128] as const)("returns base64url string of length %i", (len) => {
    const v = generateCodeVerifier(len);
    expect(v).toHaveLength(len);
    expect(BASE64URL.test(v)).toBe(true);
  });

  it("throws when length is outside RFC 7636 bounds", () => {
    expect(() => generateCodeVerifier(42)).toThrow(RangeError);
    expect(() => generateCodeVerifier(129)).toThrow(RangeError);
  });
});

describe("generateCodeChallenge", () => {
  it("matches SHA-256 S256 challenge for a fixed verifier", async () => {
    const verifier = "test-verifier-known-string";
    const expected = "f7BGVG3Eu4IbH7pr9jVlu71IN_vTMYHnN0BCKE_iXqA";
    await expect(generateCodeChallenge(verifier)).resolves.toBe(expected);
  });
});

describe("buildPkceUrl", () => {
  it("merges query params without dropping existing search params", () => {
    const url = buildPkceUrl("https://auth.example.com/oauth?existing=1", {
      client_id: "abc",
      code_challenge: "chal",
      code_challenge_method: "S256",
    });
    const parsed = new URL(url);
    expect(parsed.searchParams.get("existing")).toBe("1");
    expect(parsed.searchParams.get("client_id")).toBe("abc");
    expect(parsed.searchParams.get("code_challenge")).toBe("chal");
    expect(parsed.searchParams.get("code_challenge_method")).toBe("S256");
  });
});

describe("schwabAdapter", () => {
  it("buildAuthorizeUrl sets expected query params", () => {
    const url = schwabAdapter.buildAuthorizeUrl(sampleCreds, {
      state: "csrf-123",
    });
    const parsed = new URL(url);
    expect(parsed.origin + parsed.pathname).toBe(
      "https://api.schwabapi.com/v1/oauth/authorize",
    );
    expect(parsed.searchParams.get("response_type")).toBe("code");
    expect(parsed.searchParams.get("client_id")).toBe(sampleCreds.clientId);
    expect(parsed.searchParams.get("redirect_uri")).toBe(sampleCreds.redirectUri);
    expect(parsed.searchParams.get("scope")).toBe("read trade");
    expect(parsed.searchParams.get("state")).toBe("csrf-123");
  });

  it("defaults scope when creds.scopes omitted", () => {
    const url = schwabAdapter.buildAuthorizeUrl({
      ...sampleCreds,
      scopes: undefined,
    });
    expect(new URL(url).searchParams.get("scope")).toBe("read");
  });

  it("stub methods throw with Not implemented messages", async () => {
    await expect(
      schwabAdapter.exchangeCode(sampleCreds, "code"),
    ).rejects.toThrow(/Not implemented: Schwab OAuth exchange/);
    await expect(
      schwabAdapter.refreshTokens(sampleCreds, "rt"),
    ).rejects.toThrow(/Not implemented/);
    await expect(schwabAdapter.listAccounts(dummyTokens)).rejects.toThrow(
      /Not implemented: Schwab adapter is a stub/,
    );
    await expect(
      schwabAdapter.listPositions(dummyTokens, "acct"),
    ).rejects.toThrow(/Not implemented/);
    await expect(
      schwabAdapter.listTransactions(dummyTokens, "acct"),
    ).rejects.toThrow(/Not implemented/);
  });
});

describe("stub brokerage adapters", () => {
  it("fidelityAdapter throws on exchange", async () => {
    await expect(
      fidelityAdapter.exchangeCode(sampleCreds, "c"),
    ).rejects.toThrow(/Not implemented: Fidelity OAuth exchange/);
  });

  it("ibkrAdapter throws on listAccounts", async () => {
    await expect(ibkrAdapter.listAccounts(dummyTokens)).rejects.toThrow(
      /Not implemented: IBKR adapter is a stub/,
    );
  });

  it("tastytradeAdapter throws on listTransactions", async () => {
    await expect(
      tastytradeAdapter.listTransactions(dummyTokens, "a"),
    ).rejects.toThrow(/Not implemented/);
  });
});
