/**
 * Nevada Articles of Organization
 *
 * PDF template for Nevada LLC formation using @react-pdf/renderer.
 * Based on Nevada Revised Statutes Chapter 86 (limited-liability companies).
 *
 * Typical total at formation: $425 — $75 filing + $150 initial list + $200
 * state business license (amounts subject to change; confirm with Secretary of State).
 * State law: NRS Chapter 86
 *
 * Nevada requires disclosure of managers (or managing members) on the
 * annual/initial list; this template includes manager names in the articles section.
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
  managerRow: {
    paddingLeft: 20,
    marginBottom: 4,
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

export interface NVManager {
  name: string;
  /** Optional title, e.g. "Manager", "Managing Member". */
  title?: string;
}

export interface NVArticlesProps {
  llcName: string;
  registeredAgent: {
    name: string;
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  /** Nevada requires manager/member disclosure on filings; list all managers or managing members. */
  managers: NVManager[];
  organizer: {
    name: string;
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  /** Manager-managed if true; affects narrative only unless you add member names. */
  isManagerManaged?: boolean;
  purpose?: string;
  filingDate?: string;
}

export function NVArticlesOfOrganization({
  llcName,
  registeredAgent,
  managers,
  organizer,
  isManagerManaged = true,
  purpose,
  filingDate,
}: NVArticlesProps) {
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
            Domestic Limited Liability Company — Nevada Revised Statutes Chapter
            86
          </Text>
          <Text style={styles.subtitle}>
            Nevada Secretary of State — Commercial Recordings Division
          </Text>
          <Text style={styles.subtitle}>
            Typical fees at formation: $75 filing + $150 initial list + $200
            business license ($425 total; confirm current amounts)
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE I — NAME</Text>
          <Text style={styles.articleText}>
            The name of the limited-liability company is: {llcName}
          </Text>
          <Text style={styles.note}>
            The name must contain &quot;Limited-Liability Company,&quot;
            &quot;Limited Liability Company,&quot; &quot;Limited Company,&quot;
            or an approved abbreviation (e.g., L.L.C., LLC).
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE II — REGISTERED AGENT</Text>
          <Text style={styles.articleText}>
            The name and Nevada street address of the registered agent are:
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
            The registered agent must maintain a physical street address in
            Nevada where process may be served during business hours.
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE III — MANAGEMENT</Text>
          <Text style={styles.articleText}>
            The limited-liability company is{" "}
            {isManagerManaged
              ? "managed by one or more managers"
              : "managed by its members"}
            . The following person(s) are named as{" "}
            {isManagerManaged ? "manager(s)" : "managing member(s)"} (Nevada
            disclosure requirements):
          </Text>
          {managers.map((m, i) => (
            <View key={i} style={styles.managerRow}>
              <Text>
                {i + 1}. {m.name}
                {m.title ? ` — ${m.title}` : ""}
              </Text>
            </View>
          ))}
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE IV — PURPOSE</Text>
          <Text style={styles.articleText}>
            {purpose ??
              "The purpose for which the limited-liability company is organized is to engage in any lawful act or activity for which a limited-liability company may be organized under Chapter 86 of the Nevada Revised Statutes."}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE V — ORGANIZER</Text>
          <Text style={styles.articleText}>
            The undersigned organizer executes these Articles of Organization:
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
            The undersigned certifies under penalty of law that the foregoing is
            true and correct.
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
            consult a licensed attorney. Confirm SOS forms, initial list, and
            business license fees before filing.
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

export default NVArticlesOfOrganization;
