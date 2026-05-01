/** System graph node ids whose production deploy time is fetched from the Vercel API (project slug → vercel.com/paperwork-labs/{slug}). */
export const NODE_VERCEL_PROJECT: Partial<Record<string, string>> = {
  "studio.frontend": "studio",
  "filefree.frontend": "filefree",
  "launchfree.frontend": "launchfree",
  "distill.frontend": "distill",
  "trinkets.frontend": "trinkets",
};
