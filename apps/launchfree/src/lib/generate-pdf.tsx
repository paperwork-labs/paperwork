/**
 * PDF Generation Utilities
 *
 * Server-side PDF generation for formation documents.
 */

import { renderToBuffer } from "@react-pdf/renderer";
import { CAArticlesOfOrganization, type CAArticlesProps } from "./pdf-templates";

export type SupportedState = "CA";

export interface GeneratePDFOptions {
  stateCode: SupportedState;
  documentType: "articles" | "operating-agreement";
  data: CAArticlesProps;
}

export async function generateFormationPDF(
  options: GeneratePDFOptions
): Promise<Buffer> {
  const { stateCode, documentType, data } = options;

  if (documentType !== "articles") {
    throw new Error(`Document type "${documentType}" not yet supported`);
  }

  switch (stateCode) {
    case "CA":
      return renderToBuffer(<CAArticlesOfOrganization {...data} />);
    default:
      throw new Error(`State "${stateCode}" not yet supported`);
  }
}

export async function generateCAArticles(data: CAArticlesProps): Promise<Buffer> {
  return generateFormationPDF({
    stateCode: "CA",
    documentType: "articles",
    data,
  });
}
