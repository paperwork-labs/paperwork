/** Implementation entry (avoids package root, which runs a debug self-test under ESM). */
declare module "pdf-parse/lib/pdf-parse.js" {
  import type { Buffer } from "node:buffer";

  function pdfParse(
    data: Buffer,
    options?: object,
  ): Promise<{
    numpages: number;
    text: string;
    info?: Record<string, unknown>;
  }>;

  export default pdfParse;
}
