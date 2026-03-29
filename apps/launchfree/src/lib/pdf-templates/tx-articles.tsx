/**
 * Texas Certificate of Formation — Limited Liability Company (Form 205)
 *
 * PDF template for Texas LLC formation using @react-pdf/renderer.
 * Based on Texas Secretary of State Form 205 and TBOC requirements.
 *
 * Filing fee: $300
 * State law: Texas Business Organizations Code Section 3.005
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
});

export interface TXArticlesProps {
  llcName: string;
  purpose: string;
  registeredAgent: {
    name: string;
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  isManagerManaged?: boolean;
  organizer: {
    name: string;
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  effectiveDate?: string;
  filingDate?: string;
}

export function TXArticlesOfOrganization({
  llcName,
  purpose,
  registeredAgent,
  isManagerManaged = false,
  organizer,
  effectiveDate,
  filingDate,
}: TXArticlesProps) {
  const formattedDate = filingDate ?? new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <Document>
      <Page size="LETTER" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.title}>CERTIFICATE OF FORMATION</Text>
          <Text style={styles.subtitle}>
            Limited Liability Company — Texas Business Organizations Code Section
            3.005 (Form 205)
          </Text>
          <Text style={styles.subtitle}>
            Secretary of State — State of Texas — Filing fee: $300
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE 1 — ENTITY NAME</Text>
          <Text style={styles.articleText}>
            The name of the limited liability company is: {llcName}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE 2 — REGISTERED AGENT</Text>
          <Text style={styles.articleText}>
            The name and address in Texas of the entity&apos;s initial
            registered agent for service of process are:
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

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE 3 — PURPOSE</Text>
          <Text style={styles.articleText}>
            The purpose for which the limited liability company is formed is:{" "}
            {purpose ||
              "the transaction of any and all lawful business for which limited liability companies may be organized under the Texas Business Organizations Code."}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE 4 — MANAGEMENT</Text>
          <Text style={styles.articleText}>
            The management of the limited liability company is vested in:{" "}
            {isManagerManaged
              ? "one or more managers"
              : "its member(s)"}
            .
          </Text>
        </View>

        {effectiveDate && (
          <View style={styles.article}>
            <Text style={styles.articleNumber}>ARTICLE 5 — EFFECTIVE DATE</Text>
            <Text style={styles.articleText}>
              This certificate of formation is effective on: {effectiveDate}
            </Text>
          </View>
        )}

        <View style={styles.signatureSection}>
          <Text style={styles.articleNumber}>ORGANIZER</Text>
          <View style={styles.address}>
            <Text>{organizer.name}</Text>
            <Text>{organizer.street}</Text>
            <Text>
              {organizer.city}, {organizer.state} {organizer.zip}
            </Text>
          </View>
          <View style={styles.signatureLine} />
          <Text style={styles.signatureLabel}>Signature of Organizer</Text>
          <Text style={{ fontSize: 8, marginTop: 5 }}>
            Date: {formattedDate}
          </Text>
        </View>

        <View style={styles.disclaimer}>
          <Text>
            This document was prepared by LaunchFree (launchfree.ai), a product
            of Paperwork Labs LLC. LaunchFree provides document preparation
            services only and does not provide legal advice. For legal advice,
            consult a licensed attorney.
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

export default TXArticlesOfOrganization;
