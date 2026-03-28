/**
 * California Articles of Organization (LLC-1)
 *
 * PDF template for California LLC formation using @react-pdf/renderer.
 * Based on CA Secretary of State form LLC-1 requirements.
 *
 * Filing fee: $70 (standard) or $350 (24-hour expedited)
 */

import {
  Document,
  Page,
  Text,
  View,
  StyleSheet,
  Font,
} from "@react-pdf/renderer";

Font.register({
  family: "Helvetica",
  fonts: [
    { src: "Helvetica" },
    { src: "Helvetica-Bold", fontWeight: "bold" },
  ],
});

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

export interface CAArticlesProps {
  llcName: string;
  purpose: string;
  registeredAgent: {
    name: string;
    street: string;
    city: string;
    state: string;
    zip: string;
    isCommercial?: boolean;
  };
  principalAddress: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
  mailingAddress?: {
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
  isManagerManaged?: boolean;
  effectiveDate?: string;
  filingDate?: string;
}

export function CAArticlesOfOrganization({
  llcName,
  purpose,
  registeredAgent,
  principalAddress,
  mailingAddress,
  organizer,
  isManagerManaged = false,
  effectiveDate,
  filingDate,
}: CAArticlesProps) {
  const formattedDate = filingDate ?? new Date().toLocaleDateString("en-US", {
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
            Limited Liability Company (California Corporations Code Section 17702.01)
          </Text>
          <Text style={styles.subtitle}>
            Secretary of State — State of California
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE I — NAME</Text>
          <Text style={styles.articleText}>
            The name of the limited liability company is: {llcName}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE II — PURPOSE</Text>
          <Text style={styles.articleText}>
            The purpose of the limited liability company is to engage in:{" "}
            {purpose || "any lawful act or activity for which a limited liability company may be organized under the California Revised Uniform Limited Liability Company Act."}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE III — AGENT FOR SERVICE OF PROCESS
          </Text>
          <Text style={styles.articleText}>
            {registeredAgent.isCommercial
              ? `The name of the initial agent for service of process is: ${registeredAgent.name}`
              : `The name and address in this state of the initial agent for service of process is:`}
          </Text>
          {!registeredAgent.isCommercial && (
            <View style={styles.address}>
              <Text>{registeredAgent.name}</Text>
              <Text>{registeredAgent.street}</Text>
              <Text>
                {registeredAgent.city}, {registeredAgent.state}{" "}
                {registeredAgent.zip}
              </Text>
            </View>
          )}
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE IV — PRINCIPAL OFFICE ADDRESS
          </Text>
          <Text style={styles.articleText}>
            The street address of the initial principal office is:
          </Text>
          <View style={styles.address}>
            <Text>{principalAddress.street}</Text>
            <Text>
              {principalAddress.city}, {principalAddress.state}{" "}
              {principalAddress.zip}
            </Text>
          </View>
        </View>

        {mailingAddress && (
          <View style={styles.article}>
            <Text style={styles.articleNumber}>
              ARTICLE V — MAILING ADDRESS
            </Text>
            <Text style={styles.articleText}>
              The mailing address of the limited liability company is:
            </Text>
            <View style={styles.address}>
              <Text>{mailingAddress.street}</Text>
              <Text>
                {mailingAddress.city}, {mailingAddress.state}{" "}
                {mailingAddress.zip}
              </Text>
            </View>
          </View>
        )}

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE {mailingAddress ? "VI" : "V"} — MANAGEMENT
          </Text>
          <Text style={styles.articleText}>
            The limited liability company will be managed by:{" "}
            {isManagerManaged
              ? "one or more managers"
              : "all limited liability company member(s)"}
          </Text>
        </View>

        {effectiveDate && (
          <View style={styles.article}>
            <Text style={styles.articleNumber}>
              ARTICLE {mailingAddress ? "VII" : "VI"} — EFFECTIVE DATE
            </Text>
            <Text style={styles.articleText}>
              These articles of organization shall be effective on: {effectiveDate}
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
          <Text style={styles.signatureLabel}>
            Signature of Organizer
          </Text>
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

export default CAArticlesOfOrganization;
