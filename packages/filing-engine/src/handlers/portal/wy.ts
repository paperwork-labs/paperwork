/**
 * Wyoming Portal Handler
 *
 * Tier 2 portal automation for Wyoming Secretary of State.
 * Extends BasePortalHandler with WY-specific field mapping.
 */

import type { FormationRequest, PortalConfig } from "../../types.js";
import { BasePortalHandler } from "./base.js";
import { loadPortalConfig } from "./config-loader.js";

export class WyomingPortalHandler extends BasePortalHandler {
  readonly supportedStates = ["WY"];
  protected readonly config: PortalConfig;

  constructor() {
    super();
    this.config = loadPortalConfig("WY");
  }

  canHandle(stateCode: string): boolean {
    return stateCode.toUpperCase() === "WY";
  }

  protected mapFormationToFields(
    request: FormationRequest
  ): Record<string, string> {
    const organizer = request.members.find((m) => m.isOrganizer) ?? request.members[0];

    return {
      entityType: "LLC",
      businessName: request.businessName,
      nameSuffix: "LLC",
      purpose: request.businessPurpose,

      agentType: request.registeredAgent.isCommercial ? "corporation" : "individual",
      agentName: request.registeredAgent.name,
      agentStreet: request.registeredAgent.address.street1,
      agentCity: request.registeredAgent.address.city,
      agentState: request.registeredAgent.address.state,
      agentZip: request.registeredAgent.address.zip,

      principalStreet: request.principalAddress.street1,
      principalCity: request.principalAddress.city,
      principalState: request.principalAddress.state,
      principalZip: request.principalAddress.zip,

      sameAsPhysical: request.mailingAddress ? "false" : "true",

      managementType: request.isManagerManaged ? "manager" : "member",

      organizerName: organizer.name,
      organizerStreet: organizer.address.street1,
      organizerCity: organizer.address.city,
      organizerState: organizer.address.state,
      organizerZip: organizer.address.zip,
    };
  }
}
