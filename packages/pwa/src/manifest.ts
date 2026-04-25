// Track M.7 — small helpers for building a web-app manifest.
//
// Not required — you can always ship your own manifest.webmanifest —
// but handy when Studio and AxiomFolio want the same default shape
// (display=standalone, start_url=/, theme_color driven by brand token).

export interface ManifestIcon {
  src: string;
  sizes: string;
  type?: string;
  purpose?: "any" | "maskable" | "monochrome";
}

export interface BuildManifestInput {
  name: string;
  shortName?: string;
  description?: string;
  startUrl?: string;
  scope?: string;
  display?: "standalone" | "minimal-ui" | "fullscreen" | "browser";
  backgroundColor?: string;
  themeColor?: string;
  icons?: ManifestIcon[];
  /**
   * Categories used by app stores (Chrome Web Store etc). Optional.
   * See https://github.com/w3c/manifest/wiki/Categories.
   */
  categories?: string[];
}

export interface WebAppManifest {
  name: string;
  short_name: string;
  description?: string;
  start_url: string;
  scope: string;
  display: NonNullable<BuildManifestInput["display"]>;
  background_color: string;
  theme_color: string;
  icons: ManifestIcon[];
  categories?: string[];
}

export function buildManifest(input: BuildManifestInput): WebAppManifest {
  return {
    name: input.name,
    short_name: input.shortName ?? input.name,
    description: input.description,
    start_url: input.startUrl ?? "/",
    scope: input.scope ?? "/",
    display: input.display ?? "standalone",
    background_color: input.backgroundColor ?? "#ffffff",
    theme_color: input.themeColor ?? "#111827",
    icons: input.icons ?? [],
    categories: input.categories,
  };
}
