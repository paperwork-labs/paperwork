import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  enabled: !!process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 1.0,
  integrations: [Sentry.replayIntegration()],
  beforeSend(event) {
    if (event.request?.data) {
      const data = JSON.stringify(event.request.data);
      if (/\d{3}-?\d{2}-?\d{4}/.test(data)) {
        event.request.data = "[REDACTED — PII]";
      }
    }
    return event;
  },
});
