/**
 * Server-side product registry reads from Brain ``/admin/products`` (WS-82).
 */

import { BrainClient, BrainClientError } from "@/lib/brain-client";
import { brainProductToRegistryEntry, type ProductRegistryEntry } from "@/lib/products-registry";

export async function loadProductsRegistry(): Promise<ProductRegistryEntry[]> {
  const client = BrainClient.fromEnv();
  if (!client) {
    throw new BrainClientError("products", 0, "Brain admin API not configured");
  }
  const rows = await client.getProducts();
  return rows.map(brainProductToRegistryEntry);
}

export async function loadProductRegistryBySlug(slug: string): Promise<ProductRegistryEntry> {
  const client = BrainClient.fromEnv();
  if (!client) {
    throw new BrainClientError("products/detail", 0, "Brain admin API not configured");
  }
  const row = await client.getProduct(slug);
  return brainProductToRegistryEntry(row);
}
