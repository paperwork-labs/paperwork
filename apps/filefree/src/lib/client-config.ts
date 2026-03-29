import { z } from "zod";

const clientSchema = z.object({
  apiUrl: z.string().default("http://localhost:8001"),
  posthogKey: z.string().default(""),
  posthogHost: z.string().default("https://us.i.posthog.com"),
  sentryDsn: z.string().default(""),
  googleClientId: z.string().default(""),
  appleClientId: z.string().default(""),
  appleRedirectUri: z.string().default(""),
});

export type ClientConfig = z.infer<typeof clientSchema>;

export const clientConfig: ClientConfig = clientSchema.parse({
  apiUrl: process.env.NEXT_PUBLIC_API_URL,
  posthogKey: process.env.NEXT_PUBLIC_POSTHOG_KEY,
  posthogHost: process.env.NEXT_PUBLIC_POSTHOG_HOST,
  sentryDsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  googleClientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
  appleClientId: process.env.NEXT_PUBLIC_APPLE_CLIENT_ID,
  appleRedirectUri: process.env.NEXT_PUBLIC_APPLE_REDIRECT_URI,
});
