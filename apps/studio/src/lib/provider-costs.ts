export interface ProviderCost {
  name: string;
  monthlyCost: number;
  apiCalls: number;
  status: "active" | "inactive" | "degraded";
  lastChecked: string;
}

export function getProviderCosts(): ProviderCost[] {
  return [
    {
      name: "FMP (Financial Modeling Prep)",
      monthlyCost: 79,
      apiCalls: 12_450,
      status: "active",
      lastChecked: new Date().toISOString(),
    },
    {
      name: "Alpha Vantage",
      monthlyCost: 49.99,
      apiCalls: 8_320,
      status: "active",
      lastChecked: new Date().toISOString(),
    },
    {
      name: "Finnhub",
      monthlyCost: 0,
      apiCalls: 3_100,
      status: "active",
      lastChecked: new Date().toISOString(),
    },
    {
      name: "Polygon",
      monthlyCost: 199,
      apiCalls: 45_800,
      status: "active",
      lastChecked: new Date().toISOString(),
    },
    {
      name: "Twelve Data",
      monthlyCost: 29,
      apiCalls: 5_670,
      status: "inactive",
      lastChecked: new Date().toISOString(),
    },
  ];
}
