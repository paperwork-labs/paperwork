import { describe, it, expect, beforeEach } from "vitest";
import { useFilingStore, FILING_STEPS, type W2Data } from "./filing-store";

const sampleW2: W2Data = {
  employer_name: "Acme Corp",
  employer_ein: "12-3456789",
  employer_address: "123 Main St",
  employee_name: "John Doe",
  employee_address: "456 Oak Ave",
  ssn_last_four: "6789",
  wages: 5000000,
  federal_tax_withheld: 800000,
  social_security_wages: 5000000,
  social_security_tax: 310000,
  medicare_wages: 5000000,
  medicare_tax: 72500,
  state: "CA",
  state_wages: 5000000,
  state_tax_withheld: 200000,
  confidence: 0.95,
};

describe("filing-store", () => {
  beforeEach(() => {
    useFilingStore.getState().reset();
  });

  it("starts with default state", () => {
    const state = useFilingStore.getState();
    expect(state.filingId).toBeNull();
    expect(state.taxYear).toBe(2025);
    expect(state.currentStep).toBe(0);
    expect(state.w2s).toEqual([]);
    expect(state.filingStatusType).toBeNull();
  });

  it("sets filing ID", () => {
    useFilingStore.getState().setFilingId("abc-123");
    expect(useFilingStore.getState().filingId).toBe("abc-123");
  });

  it("sets current step", () => {
    useFilingStore.getState().setCurrentStep(2);
    expect(useFilingStore.getState().currentStep).toBe(2);
  });

  it("adds W2", () => {
    useFilingStore.getState().addW2(sampleW2);
    expect(useFilingStore.getState().w2s).toHaveLength(1);
    expect(useFilingStore.getState().w2s[0].employer_name).toBe("Acme Corp");
  });

  it("adds multiple W2s", () => {
    useFilingStore.getState().addW2(sampleW2);
    useFilingStore.getState().addW2({ ...sampleW2, employer_name: "Beta Inc" });
    expect(useFilingStore.getState().w2s).toHaveLength(2);
  });

  it("updates W2 at index", () => {
    useFilingStore.getState().addW2(sampleW2);
    useFilingStore.getState().updateW2(0, { wages: 6000000 });
    expect(useFilingStore.getState().w2s[0].wages).toBe(6000000);
    expect(useFilingStore.getState().w2s[0].employer_name).toBe("Acme Corp");
  });

  it("removes W2 at index", () => {
    useFilingStore.getState().addW2(sampleW2);
    useFilingStore.getState().addW2({ ...sampleW2, employer_name: "Beta Inc" });
    useFilingStore.getState().removeW2(0);
    expect(useFilingStore.getState().w2s).toHaveLength(1);
    expect(useFilingStore.getState().w2s[0].employer_name).toBe("Beta Inc");
  });

  it("sets filing status type", () => {
    useFilingStore.getState().setFilingStatusType("single");
    expect(useFilingStore.getState().filingStatusType).toBe("single");
  });

  it("resets to initial state", () => {
    useFilingStore.getState().setFilingId("abc");
    useFilingStore.getState().setCurrentStep(3);
    useFilingStore.getState().addW2(sampleW2);
    useFilingStore.getState().setFilingStatusType("married_joint");

    useFilingStore.getState().reset();

    const state = useFilingStore.getState();
    expect(state.filingId).toBeNull();
    expect(state.currentStep).toBe(0);
    expect(state.w2s).toEqual([]);
    expect(state.filingStatusType).toBeNull();
  });

  it("FILING_STEPS has correct structure", () => {
    expect(FILING_STEPS).toHaveLength(4);
    expect(FILING_STEPS[0]).toEqual({
      key: "w2",
      label: "W-2",
      path: "/file/w2",
    });
    expect(FILING_STEPS[3]).toEqual({
      key: "summary",
      label: "Summary",
      path: "/file/summary",
    });
  });
});
