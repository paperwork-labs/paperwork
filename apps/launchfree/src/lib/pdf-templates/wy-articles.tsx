/**
 * Wyoming Articles of Organization
 *
 * PDF template for Wyoming LLC formation using @react-pdf/renderer.
 * Based on Wyoming Limited Liability Company Act requirements.
 *
 * Filing fee: $100 (online filing)
 * State law: Wyo. Stat. § 17-29-201 (Wyoming LLC Act)
 *
 * Wyoming is privacy-friendly with minimal public disclosure requirements.
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

export interface WYArticlesProps {
  llcName: string;
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
  /** Optional purpose; Wyoming permits any lawful purpose. */
  purpose?: string;
  filingDate?: string;
}

export function WYArticlesOfOrganization({
  llcName,
  registeredAgent,
  organizer,
  purpose,
  filingDate,
}: WYArticlesProps) {
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
            Limited Liability Company — Wyoming Limited Liability Company Act
            Section 17-29-201
          </Text>
          <Text style={styles.subtitle}>
            Wyoming Secretary of State — Business Division
          </Text>
          <Text style={styles.subtitle}>Filing fee (online): $100</Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE I — NAME</Text>
          <Text style={styles.articleText}>
            The name of the limited liability company is: {llcName}
          </Text>
          <Text style={styles.note}>
            The name must contain the words &quot;Limited Liability Company,&quot;
            &quot;Limited Company,&quot; or an abbreviation (e.g., L.L.C., LLC, LC,
            L.C., Ltd. Liability Co.).
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE II — REGISTERED AGENT</Text>
          <Text style={styles.articleText}>
            The name and Wyoming street address of the registered agent are:
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
            The registered agent must have a physical street address in Wyoming
            (P.O. box alone is not sufficient).
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE III — PURPOSE</Text>
          <Text style={styles.articleText}>
            {purpose ??
              "The limited liability company is formed for the transaction of any lawful business for which limited liability companies may be organized under the Wyoming Limited Liability Company Act."}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE IV — ORGANIZER</Text>
          <Text style={styles.articleText}>
            The undersigned is the organizer executing these Articles of
            Organization:
          </Text>
          <View style={styles.address}>
            <Text>{organizer.name}</Text>
            <Text>{organizer.street}</Text>
            <Text>
              {organizer.city}, {organizer.state} {organizer.zip}
            </Text>
          </View>
        </View>

        <View style={styles.signatureSection}>
          <Text style={styles.articleNumber}>CERTIFICATION</Text>
          <Text style={styles.articleText}>
            The undersigned certifies that the foregoing is true and correct.
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
            consult a licensed attorney. Wyoming allows minimal public
            disclosure; confirm current SOS forms and fees before filing.
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

export default WYArticlesOfOrganization;
