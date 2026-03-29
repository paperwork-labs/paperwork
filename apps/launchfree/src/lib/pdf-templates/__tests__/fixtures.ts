/**
 * Mock formation data for PDF template tests.
 * Values are synthetic — not real PII or business data.
 */

import type { CAArticlesProps } from "../ca-articles";
import type { TXArticlesProps } from "../tx-articles";
import type { FLArticlesProps } from "../fl-articles";
import type { DEArticlesProps } from "../de-articles";
import type { WYArticlesProps } from "../wy-articles";
import type { NYArticlesProps } from "../ny-articles";
import type { NVArticlesProps } from "../nv-articles";
import type { ILArticlesProps } from "../il-articles";
import type { GAArticlesProps } from "../ga-articles";
import type { WAArticlesProps } from "../wa-articles";

const MOCK_AGENT = {
  name: "Example Registered Agent LLC",
  street: "100 Example Street, Suite 200",
  city: "Example City",
  state: "CA",
  zip: "94102",
} as const;

const MOCK_ORGANIZER = {
  name: "Alex Organizer",
  street: "200 Sample Ave",
  city: "Sampletown",
  state: "CA",
  zip: "90210",
} as const;

const MOCK_PRINCIPAL = {
  street: "300 Business Blvd",
  city: "Commerce",
  state: "CA",
  zip: "90001",
} as const;

/** Valid props for California LLC-1-style template */
export const mockCAArticlesProps: CAArticlesProps = {
  llcName: "Example Ventures LLC",
  purpose:
    "Any lawful act or activity for which a limited liability company may be organized under the California Revised Uniform Limited Liability Company Act.",
  registeredAgent: { ...MOCK_AGENT, state: "CA" },
  principalAddress: { ...MOCK_PRINCIPAL, state: "CA" },
  mailingAddress: {
    street: "PO Box 1000",
    city: "Commerce",
    state: "CA",
    zip: "90002",
  },
  organizer: { ...MOCK_ORGANIZER, state: "CA" },
  isManagerManaged: false,
  effectiveDate: "January 1, 2027",
  filingDate: "March 15, 2027",
};

/** Valid props for Texas Form 205-style template */
export const mockTXArticlesProps: TXArticlesProps = {
  llcName: "Lone Star Example LLC",
  purpose:
    "The transaction of any and all lawful business for which limited liability companies may be organized under the Texas Business Organizations Code.",
  registeredAgent: {
    name: "Texas Agent Services Inc.",
    street: "400 Austin Loop",
    city: "Austin",
    state: "TX",
    zip: "78701",
  },
  isManagerManaged: true,
  organizer: {
    name: "Jordan Organizer",
    street: "500 Houston St",
    city: "Houston",
    state: "TX",
    zip: "77002",
  },
  filingDate: "March 15, 2027",
};

/** Valid props for Florida Division of Corporations-style template */
export const mockFLArticlesProps: FLArticlesProps = {
  llcName: "Sunshine Example LLC",
  principalAddress: {
    street: "600 Ocean Dr",
    city: "Miami",
    state: "FL",
    zip: "33139",
  },
  registeredAgent: {
    name: "Florida RA Corp",
    street: "700 Tampa Way",
    city: "Tampa",
    state: "FL",
    zip: "33602",
  },
  organizer: {
    name: "Pat Organizer",
    street: "800 Orlando Rd",
    city: "Orlando",
    state: "FL",
    zip: "32801",
  },
  filingDate: "March 15, 2027",
};

/** Valid props for Delaware certificate of formation */
export const mockDEArticlesProps: DEArticlesProps = {
  llcName: "First State Example LLC",
  registeredAgent: {
    name: "Delaware Agent Company",
    street: "9 East Loockerman Street",
    city: "Dover",
    state: "DE",
    zip: "19901",
  },
  organizer: {
    name: "Sam Organizer",
    street: "1 Corporate Way",
    city: "Wilmington",
    state: "DE",
    zip: "19801",
  },
  optionalProvisions: "The company shall be governed by a single member.",
  filingDate: "March 15, 2027",
};

/** Valid props for Wyoming articles */
export const mockWYArticlesProps: WYArticlesProps = {
  llcName: "High Plains Example LLC",
  registeredAgent: {
    name: "Wyoming Registered Agent LLC",
    street: "123 Capitol Ave",
    city: "Cheyenne",
    state: "WY",
    zip: "82001",
  },
  organizer: {
    name: "Taylor Organizer",
    street: "456 Prairie Rd",
    city: "Casper",
    state: "WY",
    zip: "82601",
  },
  purpose: "Any lawful purpose for which an LLC may be organized under Wyoming law.",
  filingDate: "March 15, 2027",
};

/** Valid props for New York articles */
export const mockNYArticlesProps: NYArticlesProps = {
  llcName: "Empire Example LLC",
  countyOfOffice: "New York",
  registeredAgent: {
    name: "New York Department of State",
    street: "One Commerce Plaza",
    city: "Albany",
    state: "NY",
    zip: "12231",
  },
  organizer: {
    name: "Riley Organizer",
    street: "789 Broadway",
    city: "New York",
    state: "NY",
    zip: "10003",
  },
  serviceOfProcessAddress: {
    street: "789 Broadway",
    city: "New York",
    state: "NY",
    zip: "10003",
  },
  filingDate: "March 15, 2027",
};

/** Valid props for Nevada articles (includes managers per NV practice) */
export const mockNVArticlesProps: NVArticlesProps = {
  llcName: "Silver State Example LLC",
  registeredAgent: {
    name: "Nevada Agent Services LLC",
    street: "200 Carson St",
    city: "Carson City",
    state: "NV",
    zip: "89701",
  },
  managers: [
    { name: "Morgan Manager", title: "Manager" },
    { name: "Casey Member", title: "Managing Member" },
  ],
  organizer: {
    name: "Quinn Organizer",
    street: "300 Vegas Blvd",
    city: "Las Vegas",
    state: "NV",
    zip: "89101",
  },
  isManagerManaged: true,
  purpose: "Any lawful purpose under Nevada Revised Statutes Chapter 86.",
  filingDate: "March 15, 2027",
};

/** Valid props for Illinois articles */
export const mockILArticlesProps: ILArticlesProps = {
  llcName: "Prairie Example LLC",
  principalAddress: {
    street: "400 Wacker Dr",
    city: "Chicago",
    state: "IL",
    zip: "60606",
  },
  registeredAgent: {
    name: "Illinois RA Inc.",
    street: "500 Springfield Ave",
    city: "Springfield",
    state: "IL",
    zip: "62701",
  },
  organizer: {
    name: "Drew Organizer",
    street: "600 Peoria St",
    city: "Peoria",
    state: "IL",
    zip: "61602",
  },
  isManagerManaged: false,
  managerNames: [],
  filingDate: "March 15, 2027",
};

/** Valid props for Georgia articles */
export const mockGAArticlesProps: GAArticlesProps = {
  llcName: "Peach Example LLC",
  principalAddress: {
    street: "700 Peachtree St",
    city: "Atlanta",
    state: "GA",
    zip: "30308",
  },
  registeredAgent: {
    name: "Georgia Agent LLC",
    street: "800 Savannah Rd",
    city: "Savannah",
    state: "GA",
    zip: "31401",
  },
  organizer: {
    name: "Jamie Organizer",
    street: "900 Augusta Ave",
    city: "Augusta",
    state: "GA",
    zip: "30901",
  },
  filingDate: "March 15, 2027",
};

/** Valid props for Washington certificate of formation */
export const mockWAArticlesProps: WAArticlesProps = {
  llcName: "Evergreen Example LLC",
  officialEmail: "compliance@example-evergreen.test",
  registeredAgent: {
    name: "Washington RA Corp",
    street: "1000 Seattle Way",
    city: "Seattle",
    state: "WA",
    zip: "98101",
  },
  organizer: {
    name: "Sky Organizer",
    street: "1100 Tacoma St",
    city: "Tacoma",
    state: "WA",
    zip: "98402",
  },
  principalAddress: {
    street: "1200 Bellevue Blvd",
    city: "Bellevue",
    state: "WA",
    zip: "98004",
  },
  filingDate: "March 15, 2027",
};
