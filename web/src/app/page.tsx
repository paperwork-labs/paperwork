import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { TrustBadges } from "@/components/landing/trust-badges";
import { Comparison } from "@/components/landing/comparison";
import { Footer } from "@/components/landing/footer";

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <Hero />
      <HowItWorks />
      <TrustBadges />
      <Comparison />
      <Footer />
    </main>
  );
}
