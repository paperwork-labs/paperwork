/**
 * New York Articles of Organization
 *
 * PDF template for New York LLC formation using @react-pdf/renderer.
 * Based on New York Limited Liability Company Law requirements.
 *
 * Filing fee: $200
 * State law: NY LLC Law § 203
 *
 * After filing, NY requires publication of the articles (or notice) in two
 * newspapers designated by the county clerk for six consecutive weeks.
 */

import { Document, Page, Text, View, StyleSheet } from "@react-pdf/renderer";

const styles = StyleSheet.create({
  page: {
    padding: 50,
    fontSize: 10,
    fontFamily: "Helvetica",
    lineHeight: 1.4,
  },
  header: {
    textAlign: "center",
    marginBottom: 20,
  },
  title: {
    fontSize: 14,
    fontWeight: "bold",
    marginBottom: 5,
  },
  subtitle: {
    fontSize: 10,
    color: "#666",
    marginBottom: 10,
  },
  article: {
    marginBottom: 12,
  },
  articleNumber: {
    fontWeight: "bold",
    marginBottom: 3,
  },
  articleText: {
    paddingLeft: 20,
  },
  address: {
    paddingLeft: 20,
    marginBottom: 5,
  },
  footer: {
    position: "absolute",
    bottom: 50,
    left: 50,
    right: 50,
    textAlign: "center",
    fontSize: 8,
    color: "#666",
  },
  signatureSection: {
    marginTop: 30,
    borderTop: "1 solid #000",
    paddingTop: 15,
  },
  signatureLine: {
    borderBottom: "1 solid #000",
    marginTop: 30,
    marginBottom: 5,
    width: 250,
  },
  signatureLabel: {
    fontSize: 8,
  },
  disclaimer: {
    marginTop: 20,
    padding: 10,
    backgroundColor: "#f5f5f5",
    fontSize: 8,
  },
  note: {
    marginTop: 8,
    paddingLeft: 20,
    fontSize: 9,
    color: "#444",
    fontStyle: "italic",
  },
});

export interface NYArticlesProps {
  llcName: string;
  /** County in New York where the LLC office is located. */
  countyOfOffice: string;
  /**
   * Registered agent. The New York Secretary of State may be designated as
   * agent for service of process; use name/address accordingly.
   */
  registeredAgent: {
    name: string;
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  organizer: {
    name: string;
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  /** Service of process address if different from agent (when applicable). */
  serviceOfProcessAddress?: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  filingDate?: string;
}

export function NYArticlesOfOrganization({
  llcName,
  countyOfOffice,
  registeredAgent,
  organizer,
  serviceOfProcessAddress,
  filingDate,
}: NYArticlesProps) {
  const formattedDate =
    filingDate ??
    new Date().toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });

  return (
    <Document>
      <Page size="LETTER" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.title}>ARTICLES OF ORGANIZATION</Text>
          <Text style={styles.subtitle}>
            Limited Liability Company — New York Limited Liability Company Law
            Section 203
          </Text>
          <Text style={styles.subtitle}>
            New York Department of State — Division of Corporations
          </Text>
          <Text style={styles.subtitle}>Filing fee: $200</Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE I — NAME</Text>
          <Text style={styles.articleText}>
            The name of the limited liability company is: {llcName}
          </Text>
          <Text style={styles.note}>
            The name must include &quot;Limited Liability Company,&quot;
            &quot;L.L.C.,&quot; or &quot;LLC&quot; and meet Department of State
            naming requirements.
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE II — COUNTY OF OFFICE
          </Text>
          <Text style={styles.articleText}>
            The county within the State of New York in which the office of the
            limited liability company is to be located is: {countyOfOffice}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE III — SERVICE OF PROCESS / REGISTERED AGENT
          </Text>
          <Text style={styles.articleText}>
            The Secretary of State is designated as agent of the limited
            liability company upon whom process against it may be served, and
            the post office address within or without the state to which the
            Secretary of State shall mail a copy of any process against the
            limited liability company served upon him or her is:
          </Text>
          <View style={styles.address}>
            <Text>{registeredAgent.name}</Text>
            <Text>{registeredAgent.street}</Text>
            <Text>
              {registeredAgent.city}, {registeredAgent.state}{" "}
              {registeredAgent.zip}
            </Text>
          </View>
          <Text style={styles.note}>
            Filers may designate the Secretary of State as agent; the address
            above is typically where the SOS forwards notice of process. Confirm
            current DOS form language for your filing method.
          </Text>
        </View>

        {serviceOfProcessAddress && (
          <View style={styles.article}>
            <Text style={styles.articleNumber}>
              ARTICLE III (SUPPLEMENT) — ALTERNATE SERVICE ADDRESS
            </Text>
            <Text style={styles.articleText}>
              Additional address for service of process correspondence:
            </Text>
            <View style={styles.address}>
              <Text>{serviceOfProcessAddress.street}</Text>
              <Text>
                {serviceOfProcessAddress.city}, {serviceOfProcessAddress.state}{" "}
                {serviceOfProcessAddress.zip}
              </Text>
            </View>
          </View>
        )}

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE IV — ORGANIZER</Text>
          <Text style={styles.articleText}>
            The name and address of the organizer are:
          </Text>
          <View style={styles.address}>
            <Text>{organizer.name}</Text>
            <Text>{organizer.street}</Text>
            <Text>
              {organizer.city}, {organizer.state} {organizer.zip}
            </Text>
          </View>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            PUBLICATION REQUIREMENT (POST-FILING)
          </Text>
          <Text style={styles.articleText}>
            Within 120 days after effectiveness, New York law requires
            publication of the articles (or a related notice) once each week for
            six consecutive weeks in two newspapers designated by the county
            clerk of the county where the LLC office is located. Failure to
            publish can affect good standing.
          </Text>
        </View>

        <View style={styles.signatureSection}>
          <Text style={styles.articleNumber}>ORGANIZER SIGNATURE</Text>
          <Text style={styles.articleText}>
            The undersigned, being the organizer named above, executes these
            Articles of Organization.
          </Text>
          <View style={styles.signatureLine} />
          <Text style={styles.signatureLabel}>Signature of Organizer</Text>
          <Text style={{ fontSize: 8, marginTop: 5 }}>Date: {formattedDate}</Text>
        </View>

        <View style={styles.disclaimer}>
          <Text>
            This document was prepared by LaunchFree (launchfree.ai), a product
            of Paperwork Labs LLC. LaunchFree provides document preparation
            services only and does not provide legal advice. For legal advice,
            consult a licensed attorney. Verify DOS forms, fees, and
            publication rules before filing.
          </Text>
        </View>

        <View style={styles.footer}>
          <Text>
            Generated by LaunchFree — launchfree.ai — A Paperwork Labs Product
          </Text>
        </View>
      </Page>
    </Document>
  );
}

export default NYArticlesOfOrganization;
