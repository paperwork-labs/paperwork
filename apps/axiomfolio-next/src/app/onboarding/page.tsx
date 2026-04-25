"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { CheckCircle, ChevronRight, Link2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

type Step = "welcome" | "verify" | "broker" | "sync" | "complete";

const STEPS: { id: Step; title: string; description: string }[] = [
  { id: "welcome", title: "Welcome", description: "Get started with AxiomFolio" },
  { id: "verify", title: "Verify Email", description: "Confirm your email address" },
  { id: "broker", title: "Connect Broker", description: "Link your brokerage account" },
  { id: "sync", title: "First Sync", description: "Import your portfolio data" },
  { id: "complete", title: "Complete", description: "Ready to go!" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = React.useState<Step>("welcome");
  const [skippedBroker, setSkippedBroker] = React.useState(false);

  const currentStepIndex = STEPS.findIndex((s) => s.id === currentStep);

  const goToNext = () => {
    const nextIndex = currentStepIndex + 1;
    if (nextIndex < STEPS.length) {
      setCurrentStep(STEPS[nextIndex].id);
    }
  };

  const skipBroker = () => {
    setSkippedBroker(true);
    setCurrentStep("complete");
  };

  const finish = () => {
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <div className="flex items-center justify-between mb-8">
          {STEPS.map((step, i) => (
            <React.Fragment key={step.id}>
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium",
                    i < currentStepIndex
                      ? "bg-primary text-primary-foreground"
                      : i === currentStepIndex
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  {i < currentStepIndex ? <CheckCircle className="w-5 h-5" /> : i + 1}
                </div>
                <span className="text-xs mt-1 text-muted-foreground">{step.title}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={cn("flex-1 h-0.5 mx-2", i < currentStepIndex ? "bg-primary" : "bg-muted")}
                />
              )}
            </React.Fragment>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{STEPS[currentStepIndex].title}</CardTitle>
            <CardDescription>{STEPS[currentStepIndex].description}</CardDescription>
          </CardHeader>
          <CardContent>
            {currentStep === "welcome" && (
              <div className="space-y-4">
                <p>Welcome to AxiomFolio, {user?.full_name || user?.username || "trader"}!</p>
                <p className="text-muted-foreground">
                  Let&apos;s get you set up in just a few steps. You&apos;ll be analyzing the market with Stage
                  Analysis in no time.
                </p>
                <Button onClick={goToNext} className="w-full">
                  Get Started <ChevronRight className="ml-2 w-4 h-4" />
                </Button>
              </div>
            )}

            {currentStep === "verify" && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 bg-muted rounded-lg">
                  <Mail className="w-8 h-8 text-muted-foreground" />
                  <div>
                    <p className="font-medium">{user?.email ?? "—"}</p>
                    <p className="text-sm text-muted-foreground">
                      {user?.is_verified ? "Email verified!" : "Check your inbox for verification link"}
                    </p>
                  </div>
                </div>
                <Button onClick={goToNext} className="w-full" disabled={!user?.is_verified}>
                  {user?.is_verified ? "Continue" : "Waiting for verification..."}
                </Button>
                {!user?.is_verified && (
                  <Button variant="ghost" onClick={goToNext} className="w-full">
                    Skip for now
                  </Button>
                )}
              </div>
            )}

            {currentStep === "broker" && (
              <div className="space-y-4">
                <p className="text-muted-foreground">Connect your brokerage to sync positions and enable trading.</p>
                <div className="grid gap-3">
                  <Button variant="outline" className="justify-start h-auto p-4">
                    <Link2 className="w-5 h-5 mr-3" />
                    <div className="text-left">
                      <p className="font-medium">Interactive Brokers</p>
                      <p className="text-xs text-muted-foreground">FlexQuery + Gateway</p>
                    </div>
                  </Button>
                  <Button variant="outline" className="justify-start h-auto p-4">
                    <Link2 className="w-5 h-5 mr-3" />
                    <div className="text-left">
                      <p className="font-medium">Schwab</p>
                      <p className="text-xs text-muted-foreground">OAuth integration</p>
                    </div>
                  </Button>
                  <Button variant="outline" className="justify-start h-auto p-4">
                    <Link2 className="w-5 h-5 mr-3" />
                    <div className="text-left">
                      <p className="font-medium">Tastytrade</p>
                      <p className="text-xs text-muted-foreground">SDK integration</p>
                    </div>
                  </Button>
                </div>
                <Button variant="ghost" onClick={skipBroker} className="w-full">
                  Skip for now (Market-only mode)
                </Button>
              </div>
            )}

            {currentStep === "sync" && (
              <div className="space-y-4">
                <p>Syncing your portfolio data...</p>
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-primary animate-pulse w-1/2" />
                </div>
                <Button onClick={goToNext} className="w-full">
                  Continue
                </Button>
              </div>
            )}

            {currentStep === "complete" && (
              <div className="space-y-4 text-center">
                <CheckCircle className="w-16 h-16 text-primary mx-auto" />
                <p className="text-lg font-medium">You&apos;re all set!</p>
                <p className="text-muted-foreground">
                  {skippedBroker
                    ? "You can connect a broker later in Settings."
                    : "Your portfolio is synced and ready."}
                </p>
                <Button onClick={finish} className="w-full">
                  Go to Dashboard
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
