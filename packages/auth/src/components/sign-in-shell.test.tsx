import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { SignInShell } from "./sign-in-shell";
import { SignUpShell } from "./sign-up-shell";

describe("<SignInShell>", () => {
  it("renders the app-name-primary headline by default (NOT 'Paperwork ID')", () => {
    render(
      <SignInShell
        appName="FileFree"
        appWordmark={<span data-testid="wordmark">FileFree</span>}
        appTagline="Free tax filing"
      >
        <div data-testid="clerk-stub">[clerk]</div>
      </SignInShell>,
    );

    const headline = screen.getByTestId("sign-in-shell-headline");
    expect(headline.textContent).toBe("Sign in to FileFree");
    expect(headline.textContent).not.toBe("Paperwork ID");
    expect(screen.getByTestId("wordmark")).toBeTruthy();
    expect(screen.getByTestId("clerk-stub")).toBeTruthy();
  });

  it("flips the headline to 'Paperwork ID' only when isPrimaryHost is true", () => {
    render(
      <SignInShell
        appName="Paperwork Labs"
        appWordmark={<span>Paperwork Labs</span>}
        appTagline="One account, every tool"
        isPrimaryHost
      >
        <div>[clerk]</div>
      </SignInShell>,
    );

    expect(screen.getByTestId("sign-in-shell-headline").textContent).toBe(
      "Paperwork ID",
    );

    const explainer = screen.getByTestId("sign-in-shell-explainer");
    expect(explainer.textContent).toContain("FileFree");
    expect(explainer.textContent).toContain("LaunchFree");
    expect(explainer.textContent).toContain("AxiomFolio");
    expect(explainer.textContent).toContain("Trinkets");
  });

  it("renders the attribution line with 'by Paperwork Labs' on customer apps", () => {
    render(
      <SignInShell
        appName="LaunchFree"
        appWordmark={<span>LaunchFree</span>}
        appTagline="Free LLC formation"
      >
        <div>[clerk]</div>
      </SignInShell>,
    );

    const attribution = screen.getByTestId("sign-in-shell-attribution");
    expect(attribution.textContent).toBe("Free LLC formation, by Paperwork Labs");
  });

  it("computes the sibling-product list excluding the current app", () => {
    render(
      <SignInShell
        appName="FileFree"
        appWordmark={<span>FileFree</span>}
        appTagline="Free tax filing"
      >
        <div>[clerk]</div>
      </SignInShell>,
    );

    const explainer = screen.getByTestId("sign-in-shell-explainer");
    const text = explainer.textContent ?? "";

    // FileFree is the current app — must NOT appear in the sibling list
    const fileFreeMentions = (text.match(/FileFree/g) ?? []).length;
    expect(fileFreeMentions).toBe(0);

    // Other products must appear
    expect(text).toContain("LaunchFree");
    expect(text).toContain("Distill");
    expect(text).toContain("AxiomFolio");
    expect(text).toContain("Trinkets");
    expect(text).toContain("Your Paperwork ID also works on");

    // Oxford comma + "and" before final
    expect(text).toContain(", and Trinkets.");
  });

  it("respects appSlug when it differs from appName casing/whitespace", () => {
    render(
      <SignInShell
        appName="AxiomFolio"
        appSlug="axiomfolio"
        appWordmark={<span>AxiomFolio</span>}
        appTagline="Portfolio + signals"
      >
        <div>[clerk]</div>
      </SignInShell>,
    );

    const explainer = screen.getByTestId("sign-in-shell-explainer");
    expect(explainer.textContent).not.toContain("AxiomFolio");
    expect(explainer.textContent).toContain("FileFree");
  });

  it("hides the cross-product explainer in admin variant (Studio)", () => {
    render(
      <SignInShell
        appName="Studio"
        appWordmark={<span>Studio</span>}
        appTagline="Paperwork Labs admin"
        variant="admin"
      >
        <div>[clerk]</div>
      </SignInShell>,
    );

    expect(screen.queryByTestId("sign-in-shell-explainer")).toBeNull();
    expect(screen.getByTestId("sign-in-shell-attribution").textContent).toBe(
      "Paperwork Labs admin, by Paperwork Labs",
    );
  });

  it("allows overriding the verb via signInVerb", () => {
    render(
      <SignInShell
        appName="Distill"
        appWordmark={<span>Distill</span>}
        appTagline="Compliance APIs for tax & formation"
        signInVerb="Welcome back to Distill"
      >
        <div>[clerk]</div>
      </SignInShell>,
    );

    expect(screen.getByTestId("sign-in-shell-headline").textContent).toBe(
      "Welcome back to Distill",
    );
  });

  it("renders the Clerk children inside the shell wrapper", () => {
    render(
      <SignInShell
        appName="Trinkets"
        appWordmark={<span>Trinkets</span>}
        appTagline="Tools for FileFree"
      >
        <div data-testid="clerk-mount">{"<SignIn />"}</div>
      </SignInShell>,
    );

    const wrapper = screen.getByTestId("sign-in-shell-clerk");
    expect(within(wrapper).getByTestId("clerk-mount")).toBeTruthy();
  });
});

describe("<SignUpShell>", () => {
  it("uses the create-account verb by default", () => {
    render(
      <SignUpShell
        appName="FileFree"
        appWordmark={<span>FileFree</span>}
        appTagline="Free tax filing"
      >
        <div>[clerk]</div>
      </SignUpShell>,
    );

    expect(screen.getByTestId("sign-in-shell-headline").textContent).toBe(
      "Create your FileFree account",
    );
  });

  it("respects isPrimaryHost (always 'Paperwork ID')", () => {
    render(
      <SignUpShell
        appName="Paperwork Labs"
        appWordmark={<span>Paperwork Labs</span>}
        appTagline="One account, every tool"
        isPrimaryHost
      >
        <div>[clerk]</div>
      </SignUpShell>,
    );

    expect(screen.getByTestId("sign-in-shell-headline").textContent).toBe(
      "Paperwork ID",
    );
  });

  it("allows overriding the sign-up verb", () => {
    render(
      <SignUpShell
        appName="LaunchFree"
        appWordmark={<span>LaunchFree</span>}
        appTagline="Free LLC formation"
        signUpVerb="Form your LLC for free"
      >
        <div>[clerk]</div>
      </SignUpShell>,
    );

    expect(screen.getByTestId("sign-in-shell-headline").textContent).toBe(
      "Form your LLC for free",
    );
  });
});
