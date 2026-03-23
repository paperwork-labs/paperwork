import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { TrustBadges } from "@/components/landing/trust-badges";
import { Comparison } from "@/components/landing/comparison";
import { FAQ } from "@/components/landing/faq";
import { faqJsonLd } from "@/components/landing/faq-data";
import { Footer } from "@/components/landing/footer";
import { JsonLd } from "@/components/json-ld";

const appJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "FileFree",
  url: "https://filefree.ai",
  description:
    "Free AI-powered tax filing. Snap your W-2, get your completed return in minutes.",
  applicationCategory: "FinanceApplication",
  operatingSystem: "Web",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
  },
};

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <JsonLd data={appJsonLd} />
      <JsonLd data={faqJsonLd} />
      <Hero />
      <HowItWorks />
      <TrustBadges />
      <Comparison />
      <FAQ />
      <Footer />
    </main>
  );
}
