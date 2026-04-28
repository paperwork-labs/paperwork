/**
 * Downscales apps/studio/public/brand/renders/paperclip-LOCKED-canonical-icon-1024.png
 * to 32×32 favicon.ico for each Next.js app. Run from repo root after install:
 *   pnpm add -D sharp to-ico -w && node scripts/generate-pwl-favicon-ico.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import toIco from "to-ico";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const iconPngPath = path.join(
  root,
  "apps/studio/public/brand/renders/paperclip-LOCKED-canonical-icon-1024.png",
);

const png32 = await sharp(iconPngPath).resize(32, 32).png().toBuffer();
const ico = await toIco([png32]);

const apps = [
  "studio",
  "filefree",
  "launchfree",
  "distill",
  "trinkets",
  "axiomfolio",
];

for (const app of apps) {
  const dir = path.join(root, `apps/${app}/public`);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "favicon.ico"), ico);
}

console.log("Wrote favicon.ico for:", apps.join(", "));
