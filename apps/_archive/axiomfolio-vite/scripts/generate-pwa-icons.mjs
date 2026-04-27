// Generates PWA icons from the brand SVG into frontend/public/icons.
//
// Why this exists rather than using vite-plugin-pwa: that plugin's 1.2.x
// release uses createRequire('.') internally, which fails on Node >= 22 and
// silently aborts the PWA build step. We render once at icon-creation time
// and ship the resulting PNGs as static assets.
//
// Run via: npm run pwa:icons (from frontend/).

import { fileURLToPath } from 'node:url'
import path from 'node:path'
import fs from 'node:fs/promises'
import sharp from 'sharp'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_FRONTEND = path.resolve(__dirname, '..')
const SVG_PATH = path.join(REPO_FRONTEND, 'src/assets/logos/axiomfolio-icon-star.svg')
const OUT_DIR = path.join(REPO_FRONTEND, 'public/icons')

// Brand background — matches the dark-mode `--background` token used by the
// app shell. Keeping these aligned avoids a flash of the wrong color when the
// PWA splash screen shows the icon on its background.
const BRAND_BG = '#020617'

async function ensureOutDir() {
  await fs.mkdir(OUT_DIR, { recursive: true })
}

async function loadSvg() {
  return fs.readFile(SVG_PATH)
}

// Renders an "any" purpose icon: logo inset slightly so it doesn't touch the
// edge but still fills most of the canvas.
async function renderAnyIcon(svgBuffer, size, outName) {
  const inset = Math.round(size * 0.08)
  const logoSize = size - inset * 2
  const logo = await sharp(svgBuffer, { density: 384 })
    .resize(logoSize, logoSize, {
      fit: 'contain',
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer()
  await sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: BRAND_BG,
    },
  })
    .composite([{ input: logo, top: inset, left: inset }])
    .png({ compressionLevel: 9 })
    .toFile(path.join(OUT_DIR, outName))
}

// Renders a "maskable" purpose icon with the recommended ~20% safe-zone
// padding so platforms (Android adaptive icons) can mask without clipping.
async function renderMaskableIcon(svgBuffer, size, outName) {
  const padding = Math.round(size * 0.2)
  const logoSize = size - padding * 2
  const logo = await sharp(svgBuffer, { density: 384 })
    .resize(logoSize, logoSize, {
      fit: 'contain',
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer()
  await sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: BRAND_BG,
    },
  })
    .composite([{ input: logo, top: padding, left: padding }])
    .png({ compressionLevel: 9 })
    .toFile(path.join(OUT_DIR, outName))
}

async function main() {
  await ensureOutDir()
  const svg = await loadSvg()
  await renderAnyIcon(svg, 192, 'icon-192.png')
  await renderAnyIcon(svg, 512, 'icon-512.png')
  await renderMaskableIcon(svg, 192, 'icon-192-maskable.png')
  await renderMaskableIcon(svg, 512, 'icon-512-maskable.png')
  await renderAnyIcon(svg, 180, 'apple-touch-icon.png')
  console.log('PWA icons generated in', OUT_DIR)
}

main().catch((err) => {
  console.error('Failed to generate PWA icons:', err)
  process.exitCode = 1
})
