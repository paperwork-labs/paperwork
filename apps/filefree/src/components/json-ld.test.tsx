import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { JsonLd } from "./json-ld";

describe("JsonLd", () => {
  it("renders one application/ld+json script with stringified data", () => {
    const data = { "@context": "https://schema.org", "@type": "Thing", name: "x" };
    const { container } = render(<JsonLd data={data} />);

    const scripts = container.querySelectorAll('script[type="application/ld+json"]');
    expect(scripts.length).toBe(1);

    const el = scripts[0];
    expect(el?.textContent).toBe(JSON.stringify(data));
  });

  it("escapes angle brackets so </script> in JSON cannot close the tag early", () => {
    const data = { evil: "</script><script>alert(1)</script>" };
    const { container } = render(<JsonLd data={data} />);

    const el = container.querySelector('script[type="application/ld+json"]');
    const raw = el?.textContent ?? "";
    expect(raw).not.toContain("</script>");
    expect(raw).toContain("\\u003c");
    expect(JSON.parse(raw)).toEqual(data);
  });
});
