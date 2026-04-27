import { randomBytes } from "node:crypto";

/** RFC 4648 base32 alphabet (uppercase A–Z and 2–7). */
const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

/**
 * URL-safe opaque token: 16 bytes (128 bits) → base32 without padding (~26 chars).
 */
export function generateIntakeToken(): string {
  return encodeBase32NoPadding(randomBytes(16));
}

function encodeBase32NoPadding(buf: Buffer): string {
  let bits = 0;
  let value = 0;
  let output = "";
  for (let i = 0; i < buf.length; i++) {
    value = (value << 8) | buf[i];
    bits += 8;
    while (bits >= 5) {
      output += BASE32_ALPHABET[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) {
    output += BASE32_ALPHABET[(value << (5 - bits)) & 31];
  }
  return output;
}
