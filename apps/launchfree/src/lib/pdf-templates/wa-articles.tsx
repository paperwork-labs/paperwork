/**
 * Washington Certificate of Formation
 *
 * PDF template for Washington LLC formation using @react-pdf/renderer.
 * Based on Washington Secretary of State (Corporations Division) requirements.
 *
 * Filing fee: $180
 * State law: RCW 25.15.071
 *
 * Washington requires a designated email address for official communications.
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
  section: {
    marginBottom: 15,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: "bold",
    marginBottom: 8,
    borderBottom: "1 solid #000",
    paddingBottom: 3,
  },
  row: {
    flexDirection: "row",
    marginBottom: 5,
  },
  label: {
    width: 150,
    fontWeight: "bold",
  },
  value: {
    flex: 1,
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
  feeNote: {
    fontSize: 9,
    marginBottom: 10,
    textAlign: "center",
    color: "#333",
  },
  emailNote: {
    fontSize: 8,
    fontStyle: "italic",
    paddingLeft: 20,
    marginTop: 4,
    color: "#444",
  },
});

export interface WAArticlesProps {
  llcName: string;
  /** Email for official communications from the Secretary of State (required in Washington). */
  officialEmail: string;
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
  /** Optional principal office; certificate may list registered office only on some filings. */
  principalAddress?: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  filingDate?: string;
}

export function WAArticlesOfOrganization({
  llcName,
  officialEmail,
  registeredAgent,
  organizer,
  principalAddress,
  filingDate,
}: WAArticlesProps) {
  const formattedDate =
    filingDate ??
    new Date().toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });

  /** Roman numerals for articles (optional principal office shifts later sections). */
  const emailArticle = principalAddress ? "IV" : "III";
  const organizerArticle = principalAddress ? "V" : "IV";

  return (
    <Document>
      <Page size="LETTER" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.title}>CERTIFICATE OF FORMATION</Text>
          <Text style={styles.subtitle}>
            Limited Liability Company — Washington Secretary of State
          </Text>
          <Text style={styles.subtitle}>
            RCW 25.15.071 — Washington Limited Liability Company Act
          </Text>
        </View>

        <Text style={styles.feeNote}>
          Standard filing fee: $180 (verify current fee with the Washington Secretary of State).
        </Text>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE I — NAME</Text>
          <Text style={styles.articleText}>
            The name of the limited liability company is: {llcName}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE II — REGISTERED AGENT AND REGISTERED OFFICE
          </Text>
          <Text style={styles.articleText}>
            The name and Washington street address of the registered agent and
            registered office are:
          </Text>
          <View style={styles.address}>
            <Text>{registeredAgent.name}</Text>
            <Text>{registeredAgent.street}</Text>
            <Text>
              {registeredAgent.city}, {registeredAgent.state}{" "}
              {registeredAgent.zip}
            </Text>
          </View>
        </View>

        {principalAddress && (
          <View style={styles.article}>
            <Text style={styles.articleNumber}>
              ARTICLE III — PRINCIPAL OFFICE
            </Text>
            <Text style={styles.articleText}>
              The street address of the principal office is:
            </Text>
            <View style={styles.address}>
              <Text>{principalAddress.street}</Text>
              <Text>
                {principalAddress.city}, {principalAddress.state}{" "}
                {principalAddress.zip}
              </Text>
            </View>
          </View>
        )}

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE {emailArticle} — EMAIL FOR OFFICIAL COMMUNICATIONS
          </Text>
          <Text style={styles.articleText}>
            The limited liability company designates the following email address
            for receipt of notice and official communications from the Secretary
            of State as required under Washington law:
          </Text>
          <View style={styles.address}>
            <Text>{officialEmail}</Text>
          </View>
          <Text style={styles.emailNote}>
            Washington requires a valid email address on file for service of
            process notices and other official correspondence.
          </Text>
        </View>

        <View style={styles.signatureSection}>
          <Text style={styles.articleNumber}>
            ARTICLE {organizerArticle} — ORGANIZER
          </Text>
          <Text style={styles.articleText}>
            The undersigned, as organizer, certifies that the statements in this
            certificate are true and correct.
          </Text>
          <View style={styles.address}>
            <Text>{organizer.name}</Text>
            <Text>{organizer.street}</Text>
            <Text>
              {organizer.city}, {organizer.state} {organizer.zip}
            </Text>
          </View>
          <View style={styles.signatureLine} />
          <Text style={styles.signatureLabel}>Signature of Organizer</Text>
          <Text style={{ fontSize: 8, marginTop: 5 }}>Date: {formattedDate}</Text>
        </View>

        <View style={styles.disclaimer}>
          <Text>
            This document was prepared by LaunchFree (launchfree.ai), a product
            of Paperwork Labs LLC. LaunchFree provides document preparation
            services only and does not provide legal advice. For legal advice,
            consult a licensed attorney. Verify form requirements, email
            obligations, and fees with the Washington Secretary of State before
            filing.
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

export default WAArticlesOfOrganization;
