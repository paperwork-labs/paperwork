import { z } from "zod";

const serverSchema = z.object({
  N8N_API_KEY: z.string().default(""),
  N8N_HOST: z.string().default("https://n8n.filefree.tax"),
  GITHUB_TOKEN: z.string().default(""),
});

export type ServerConfig = z.infer<typeof serverSchema>;

export const serverConfig: ServerConfig = serverSchema.parse({
  N8N_API_KEY: process.env.N8N_API_KEY,
  N8N_HOST: process.env.N8N_HOST,
  GITHUB_TOKEN: process.env.GITHUB_TOKEN,
});
