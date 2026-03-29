/**
 * Illinois Articles of Organization (Form LLC-5.5)
 *
 * PDF template for Illinois LLC formation using @react-pdf/renderer.
 * Based on Illinois Secretary of State LLC-5.5 requirements.
 *
 * Filing fee: $150
 * State law: 805 ILCS 180/5-5 (Illinois Limited Liability Company Act)
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
  managerList: {
    paddingLeft: 20,
    marginTop: 5,
  },
});

export interface ILArticlesProps {
  llcName: string;
  principalAddress: {
    street: string;
    city: string;
    state: string;
    zip: string;
  };
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
  /** When true, include manager names (manager-managed LLC). */
  isManagerManaged?: boolean;
  /** Names of initial manager(s); used when isManagerManaged is true. */
  managerNames?: string[];
  filingDate?: string;
}

export function ILArticlesOfOrganization({
  llcName,
  principalAddress,
  registeredAgent,
  organizer,
  isManagerManaged = false,
  managerNames = [],
  filingDate,
}: ILArticlesProps) {
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
            Limited Liability Company — Illinois Secretary of State (Form LLC-5.5)
          </Text>
          <Text style={styles.subtitle}>
            805 ILCS 180/5-5 — Illinois Limited Liability Company Act
          </Text>
        </View>

        <Text style={styles.feeNote}>
          Standard filing fee: $150 (verify current fee with the Illinois Secretary of State).
        </Text>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE I — NAME</Text>
          <Text style={styles.articleText}>
            The name of the limited liability company is: {llcName}
          </Text>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE II — PRINCIPAL PLACE OF BUSINESS
          </Text>
          <Text style={styles.articleText}>
            The street address of the principal place of business is:
          </Text>
          <View style={styles.address}>
            <Text>{principalAddress.street}</Text>
            <Text>
              {principalAddress.city}, {principalAddress.state}{" "}
              {principalAddress.zip}
            </Text>
          </View>
        </View>

        <View style={styles.article}>
          <Text style={styles.articleNumber}>
            ARTICLE III — REGISTERED AGENT AND REGISTERED OFFICE
          </Text>
          <Text style={styles.articleText}>
            The name and Illinois street address of the registered agent and
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

        <View style={styles.article}>
          <Text style={styles.articleNumber}>ARTICLE IV — MANAGEMENT</Text>
          <Text style={styles.articleText}>
            The limited liability company is{" "}
            {isManagerManaged
              ? "manager-managed. Management is vested in the manager(s) named below."
              : "member-managed. Management is vested in the member(s)."}
          </Text>
          {isManagerManaged && managerNames.length > 0 && (
            <View style={styles.managerList}>
              {managerNames.map((name, i) => (
                <Text key={`mgr-${i}`}>
                  • {name}
                </Text>
              ))}
            </View>
          )}
        </View>

        <View style={styles.signatureSection}>
          <Text style={styles.articleNumber}>ORGANIZER</Text>
          <Text style={styles.articleText}>
            The undersigned certifies that the statements herein are true and
            correct to the best of the organizer&apos;s knowledge.
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
            consult a licensed attorney. Verify form requirements and fees with
            the Illinois Secretary of State before filing.
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

export default ILArticlesOfOrganization;
