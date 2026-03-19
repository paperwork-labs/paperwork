import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { TrustBadges } from "@/components/landing/trust-badges";
import { Comparison } from "@/components/landing/comparison";
import { FAQ, faqJsonLd } from "@/components/landing/faq";
import { Footer } from "@/components/landing/footer";

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
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(appJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      <Hero />
      <HowItWorks />
      <TrustBadges />
      <Comparison />
      <FAQ />
      <Footer />
    </main>
  );
}
