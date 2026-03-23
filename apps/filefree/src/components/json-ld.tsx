/**
 * Emits JSON-LD for SEO. Uses text children (not dangerouslySetInnerHTML) so
 * React 19 / Next.js 16 don't treat the node as an invalid script resource.
 * Escapes `<` so a `</script>` substring in JSON cannot break out of the tag.
 */
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return (
    <script type="application/ld+json" suppressHydrationWarning>
      {json}
    </script>
  );
}
