"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { ArrowRight, Loader2 } from "lucide-react";
import confetti from "canvas-confetti";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import api from "@/lib/api";
import { getAttribution } from "@/lib/attribution";
import { trackEvent } from "@/lib/posthog";
import { fadeIn, slideInUp } from "@/lib/motion";

const waitlistSchema = z.object({
  email: z.string().email("Enter a valid email address"),
});

type WaitlistForm = z.infer<typeof waitlistSchema>;

export function Hero() {
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<WaitlistForm>({
    resolver: zodResolver(waitlistSchema),
  });

  const onSubmit = async (data: WaitlistForm) => {
    try {
      const attribution = getAttribution();
      await api.post("/api/v1/waitlist", {
        email: data.email,
        source: "landing",
        attribution,
      });
      setSubmitted(true);
      trackEvent("waitlist_signup", {
        source: "landing_hero",
        ...attribution,
      });
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 },
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Something went wrong";
      if (message.includes("already on the waitlist")) {
        toast.info("You're already on the list! We'll be in touch soon.");
        setSubmitted(true);
      } else {
        trackEvent("waitlist_signup_error", { error: message });
        toast.error(message);
      }
    }
  };

  return (
    <section className="relative flex min-h-[90vh] flex-col items-center justify-center overflow-hidden px-4 py-20">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,hsl(263_70%_50%/0.15),transparent_70%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,hsl(238_76%_57%/0.1),transparent_60%)]" />

      <motion.div
        className="relative z-10 mx-auto flex max-w-2xl flex-col items-center text-center"
        initial="hidden"
        animate="visible"
        variants={fadeIn}
      >
        <motion.h1
          className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl md:text-6xl"
          variants={slideInUp}
        >
          Taxes shouldn&apos;t
          <br />
          <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
            make you cry.
          </span>
        </motion.h1>

        <motion.p
          className="mt-6 max-w-lg text-lg text-muted-foreground md:text-xl"
          variants={slideInUp}
        >
          Snap your W-2. Get your return in minutes. Actually free &mdash; no
          upsells, no hidden fees, no tricks.
        </motion.p>

        <motion.div className="mt-10 w-full max-w-md" variants={slideInUp}>
          {submitted ? (
            <div className="rounded-lg border border-violet-500/30 bg-violet-500/10 p-6 text-center">
              <p className="text-lg font-semibold text-foreground">
                You&apos;re on the list!
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                We&apos;ll let you know when FileFree is ready.
              </p>
            </div>
          ) : (
            <form
              onSubmit={handleSubmit(onSubmit)}
              className="flex flex-col gap-3 sm:flex-row"
            >
              <div className="flex-1">
                <Input
                  type="email"
                  placeholder="you@email.com"
                  className="h-12 border-border/50 bg-card/50 text-base backdrop-blur"
                  {...register("email")}
                />
                {errors.email && (
                  <p className="mt-1 text-sm text-destructive">
                    {errors.email.message}
                  </p>
                )}
              </div>
              <Button
                type="submit"
                size="lg"
                disabled={isSubmitting}
                className="h-12 bg-gradient-to-r from-violet-600 to-purple-600 px-6 text-base font-semibold hover:from-violet-500 hover:to-purple-500"
              >
                {isSubmitting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="mr-2 h-4 w-4" />
                )}
                Get Early Access
              </Button>
            </form>
          )}
        </motion.div>

        <motion.p
          className="mt-4 text-xs text-muted-foreground/60"
          variants={slideInUp}
        >
          Free forever. No credit card needed.
        </motion.p>
      </motion.div>
    </section>
  );
}
