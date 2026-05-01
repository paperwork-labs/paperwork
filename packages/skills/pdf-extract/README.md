# @paperwork/skills-pdf-extract

**PDF text extraction** and **lightweight invoice/receipt heuristics** for inbound mail and future upload flows. Single runtime dependency: [`pdf-parse`](https://www.npmjs.com/package/pdf-parse) for native (text-based) PDFs.

## OCR / scanned images

Image extraction (`extractImage`) is **not implemented** yet. Adding Tesseract (or similar) requires native bindings and extra packaging; that work is intentionally deferred — see issue/PR tracking for this skill when OCR is scheduled.

## Install (monorepo)

```json
{
  "dependencies": {
    "@paperwork/skills-pdf-extract": "workspace:*"
  }
}
```

## API

- `extractPdf(buffer: Buffer): Promise<ExtractedDocument>` — text, optional per-page split, page count, PDF `info` metadata when present.
- `extractImage(buffer: Buffer, contentType: string): Promise<ExtractedDocument>` — throws `OCR not yet supported` until OCR is wired.
- `classifyAsInvoice(doc: ExtractedDocument): InvoiceCandidate` — regex/heuristic pass for vendor, invoice number, amounts (`$` / `USD` / `Total` lines), due date (numeric + simple month/day/year phrases), optional issue date; `confidence` is the fraction of four headline fields found (vendor, invoice #, amount, due date).

## Build

```bash
pnpm -C packages/skills/pdf-extract build
pnpm -C packages/skills/pdf-extract test
```
