"use client";

import { notFound } from "next/navigation";
import { useState } from "react";
import { motion } from "framer-motion";
import {
  Shield,
  Zap,
  Camera,
  ChevronDown,
  Mail,
  Search,
  Bell,
  Settings,
  Heart,
  Star,
  Check,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  RadioGroup,
  RadioGroupItem,
} from "@/components/ui/radio-group";
import {
  fadeIn,
  slideInUp,
  slideInRight,
  scaleIn,
  staggerContainer,
} from "@/lib/motion";

if (process.env.NODE_ENV === "production") {
  notFound();
}

const COLORS = [
  { name: "Primary", var: "--primary", class: "bg-primary" },
  { name: "Secondary", var: "--secondary", class: "bg-secondary" },
  { name: "Muted", var: "--muted", class: "bg-muted" },
  { name: "Accent", var: "--accent", class: "bg-accent" },
  { name: "Destructive", var: "--destructive", class: "bg-destructive" },
  { name: "Background", var: "--background", class: "bg-background" },
  { name: "Card", var: "--card", class: "bg-card" },
  { name: "Border", var: "--border", class: "bg-border" },
];

const CHART_COLORS = [
  { name: "Chart 1", class: "bg-chart-1" },
  { name: "Chart 2", class: "bg-chart-2" },
  { name: "Chart 3", class: "bg-chart-3" },
  { name: "Chart 4", class: "bg-chart-4" },
  { name: "Chart 5", class: "bg-chart-5" },
];

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-6">
      <h2 className="text-2xl font-bold tracking-tight border-b border-border pb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

function SubSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}

export default function DesignSystemPage() {
  const [progress, setProgress] = useState(60);
  const [switchOn, setSwitchOn] = useState(true);

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background text-foreground">
        <div className="max-w-6xl mx-auto px-6 py-12 space-y-16">
          <header>
            <h1 className="text-4xl font-bold tracking-tight">
              FileFree Design System
            </h1>
            <p className="text-muted-foreground mt-2">
              Dev-only preview of colors, typography, components, and animations.
            </p>
          </header>

          {/* ---- Colors ---- */}
          <Section title="Colors">
            <SubSection title="Semantic Colors">
              <div className="grid grid-cols-4 gap-4 md:grid-cols-8">
                {COLORS.map((c) => (
                  <div key={c.name} className="space-y-2 text-center">
                    <div
                      className={`h-16 w-full rounded-lg border border-border ${c.class}`}
                    />
                    <p className="text-xs font-medium">{c.name}</p>
                    <p className="text-xs text-muted-foreground font-mono">
                      {c.var}
                    </p>
                  </div>
                ))}
              </div>
            </SubSection>
            <SubSection title="Chart Colors">
              <div className="grid grid-cols-5 gap-4">
                {CHART_COLORS.map((c) => (
                  <div key={c.name} className="space-y-2 text-center">
                    <div
                      className={`h-16 w-full rounded-lg border border-border ${c.class}`}
                    />
                    <p className="text-xs font-medium">{c.name}</p>
                  </div>
                ))}
              </div>
            </SubSection>
            <SubSection title="Gradient Accent">
              <div className="h-16 w-full rounded-lg bg-gradient-to-r from-violet-500 to-purple-600" />
              <p className="text-xs text-muted-foreground font-mono">
                from-violet-500 to-purple-600
              </p>
            </SubSection>
          </Section>

          {/* ---- Typography ---- */}
          <Section title="Typography">
            <SubSection title="Inter (Sans)">
              <div className="space-y-3">
                <p className="text-4xl font-bold">
                  Heading 1 — Bold 700
                </p>
                <p className="text-3xl font-semibold">
                  Heading 2 — Semibold 600
                </p>
                <p className="text-2xl font-medium">
                  Heading 3 — Medium 500
                </p>
                <p className="text-xl">
                  Heading 4 — Regular 400
                </p>
                <p className="text-base">
                  Body text — The quick brown fox jumps over the lazy dog.
                  FileFree makes tax filing actually free, fast, and painless.
                </p>
                <p className="text-sm text-muted-foreground">
                  Caption — Smaller supporting text for labels and descriptions.
                </p>
                <p className="text-xs text-muted-foreground">
                  Overline — Tiny text for metadata and timestamps.
                </p>
              </div>
            </SubSection>
            <SubSection title="JetBrains Mono (Monospace)">
              <div className="space-y-2 font-mono">
                <p className="text-lg font-semibold">
                  Code Heading — Semibold 600
                </p>
                <p className="text-base font-medium">
                  const refund = calculateTax(income, deductions);
                </p>
                <p className="text-sm">
                  SSN: XXX-XX-1234 | Filing: #a1b2c3d4
                </p>
              </div>
            </SubSection>
          </Section>

          {/* ---- Spacing ---- */}
          <Section title="Spacing Scale">
            <div className="flex items-end gap-2">
              {[1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24].map((s) => (
                <div key={s} className="text-center">
                  <div
                    className="bg-primary rounded"
                    style={{ width: `${s * 4}px`, height: `${s * 4}px` }}
                  />
                  <p className="text-xs text-muted-foreground mt-1">{s}</p>
                </div>
              ))}
            </div>
          </Section>

          {/* ---- Buttons ---- */}
          <Section title="Button">
            <SubSection title="Variants">
              <div className="flex flex-wrap gap-3">
                <Button variant="default">Default</Button>
                <Button variant="secondary">Secondary</Button>
                <Button variant="destructive">Destructive</Button>
                <Button variant="outline">Outline</Button>
                <Button variant="ghost">Ghost</Button>
                <Button variant="link">Link</Button>
              </div>
            </SubSection>
            <SubSection title="Sizes">
              <div className="flex flex-wrap items-center gap-3">
                <Button size="sm">Small</Button>
                <Button size="default">Default</Button>
                <Button size="lg">Large</Button>
                <Button size="icon">
                  <Heart />
                </Button>
              </div>
            </SubSection>
            <SubSection title="With Icons">
              <div className="flex flex-wrap gap-3">
                <Button>
                  <Mail /> Send Email
                </Button>
                <Button variant="outline">
                  <Camera /> Snap W-2
                </Button>
                <Button variant="secondary">
                  <Shield /> Secure
                </Button>
              </div>
            </SubSection>
            <SubSection title="States">
              <div className="flex flex-wrap gap-3">
                <Button disabled>Disabled</Button>
                <Button className="bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white border-0">
                  <Zap /> Gradient CTA
                </Button>
              </div>
            </SubSection>
          </Section>

          {/* ---- Badge ---- */}
          <Section title="Badge">
            <div className="flex flex-wrap gap-3">
              <Badge variant="default">Default</Badge>
              <Badge variant="secondary">Secondary</Badge>
              <Badge variant="destructive">Destructive</Badge>
              <Badge variant="outline">Outline</Badge>
              <Badge className="bg-green-500/10 text-green-500 border-green-500/20">
                Accepted
              </Badge>
              <Badge className="bg-yellow-500/10 text-yellow-500 border-yellow-500/20">
                Processing
              </Badge>
            </div>
          </Section>

          {/* ---- Input / Textarea ---- */}
          <Section title="Input & Textarea">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2 max-w-2xl">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" placeholder="you@example.com" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="search">Search</Label>
                <Input id="search" type="search" placeholder="Search filings..." />
              </div>
              <div className="space-y-2">
                <Label htmlFor="disabled">Disabled</Label>
                <Input id="disabled" disabled placeholder="Cannot edit" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="notes">Notes</Label>
                <Textarea id="notes" placeholder="Additional information..." />
              </div>
            </div>
          </Section>

          {/* ---- Card ---- */}
          <Section title="Card">
            <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle>Federal Return</CardTitle>
                  <CardDescription>Tax year 2025</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-green-500">$2,847</p>
                  <p className="text-sm text-muted-foreground">Estimated refund</p>
                </CardContent>
                <CardFooter>
                  <Button size="sm" className="w-full">
                    View Details
                  </Button>
                </CardFooter>
              </Card>
              <Card className="border-primary/50">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>W-2 Upload</CardTitle>
                    <Badge>95% confidence</Badge>
                  </div>
                  <CardDescription>Employer: Acme Corp</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Box 1 — Wages</span>
                    <span className="font-mono">$72,500.00</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Box 2 — Federal tax</span>
                    <span className="font-mono">$11,200.00</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Skeleton Loading</CardTitle>
                  <CardDescription>Content is loading...</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Skeleton className="h-8 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-2/3" />
                </CardContent>
              </Card>
            </div>
          </Section>

          {/* ---- Select ---- */}
          <Section title="Select">
            <div className="max-w-xs">
              <Label>Filing Status</Label>
              <Select>
                <SelectTrigger>
                  <SelectValue placeholder="Choose status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="single">Single</SelectItem>
                  <SelectItem value="married-joint">Married Filing Jointly</SelectItem>
                  <SelectItem value="married-separate">Married Filing Separately</SelectItem>
                  <SelectItem value="head">Head of Household</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </Section>

          {/* ---- Checkbox, Switch, Radio ---- */}
          <Section title="Checkbox, Switch & Radio">
            <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
              <SubSection title="Checkbox">
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Checkbox id="terms" defaultChecked />
                    <Label htmlFor="terms">I accept the terms</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="newsletter" />
                    <Label htmlFor="newsletter">Subscribe to updates</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox id="disabled-check" disabled />
                    <Label htmlFor="disabled-check" className="text-muted-foreground">
                      Disabled
                    </Label>
                  </div>
                </div>
              </SubSection>
              <SubSection title="Switch">
                <div className="space-y-3">
                  <div className="flex items-center space-x-2">
                    <Switch
                      id="dark-mode"
                      checked={switchOn}
                      onCheckedChange={setSwitchOn}
                    />
                    <Label htmlFor="dark-mode">
                      Dark mode {switchOn ? "on" : "off"}
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch id="notifications" />
                    <Label htmlFor="notifications">Notifications</Label>
                  </div>
                </div>
              </SubSection>
              <SubSection title="Radio Group">
                <RadioGroup defaultValue="standard">
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="standard" id="r-standard" />
                    <Label htmlFor="r-standard">Standard deduction</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="itemized" id="r-itemized" />
                    <Label htmlFor="r-itemized">Itemized deduction</Label>
                  </div>
                </RadioGroup>
              </SubSection>
            </div>
          </Section>

          {/* ---- Progress ---- */}
          <Section title="Progress">
            <div className="space-y-4 max-w-md">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Filing progress</span>
                  <span className="text-muted-foreground">{progress}%</span>
                </div>
                <Progress value={progress} />
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setProgress(Math.max(0, progress - 20))}
                >
                  -20
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setProgress(Math.min(100, progress + 20))}
                >
                  +20
                </Button>
              </div>
            </div>
          </Section>

          {/* ---- Separator ---- */}
          <Section title="Separator">
            <div className="space-y-4 max-w-md">
              <p>Content above</p>
              <Separator />
              <p>Content below</p>
              <div className="flex items-center gap-4 h-5">
                <span>Income</span>
                <Separator orientation="vertical" />
                <span>Deductions</span>
                <Separator orientation="vertical" />
                <span>Credits</span>
              </div>
            </div>
          </Section>

          {/* ---- Tooltip ---- */}
          <Section title="Tooltip">
            <div className="flex gap-4">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="icon">
                    <Search />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Search filings</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="icon">
                    <Bell />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Notifications</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="icon">
                    <Settings />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Settings</TooltipContent>
              </Tooltip>
            </div>
          </Section>

          {/* ---- Accordion ---- */}
          <Section title="Accordion">
            <Accordion type="single" collapsible className="max-w-lg">
              <AccordionItem value="item-1">
                <AccordionTrigger>Is FileFree really free?</AccordionTrigger>
                <AccordionContent>
                  Yes. Federal and state filing are free forever. We make money
                  through optional financial products, not filing fees.
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="item-2">
                <AccordionTrigger>How do you handle my SSN?</AccordionTrigger>
                <AccordionContent>
                  Your SSN is extracted locally on our servers and encrypted with
                  AES-256. It is never sent to any AI model or third party.
                </AccordionContent>
              </AccordionItem>
              <AccordionItem value="item-3">
                <AccordionTrigger>What documents do you support?</AccordionTrigger>
                <AccordionContent>
                  Currently W-2 forms. 1099s, 1098s, and other documents coming
                  in Sprint 3.
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </Section>

          {/* ---- Animations ---- */}
          <Section title="Animations (Framer Motion)">
            <p className="text-sm text-muted-foreground mb-4">
              Click the button to replay each animation.
            </p>
            <AnimationShowcase />
          </Section>

          {/* ---- Gradient / Special Effects ---- */}
          <Section title="Special Effects">
            <SubSection title="AI Thinking Indicator">
              <div className="flex items-center gap-3">
                <div className="relative h-8 w-8">
                  <div className="absolute inset-0 rounded-full bg-gradient-to-r from-violet-500 to-purple-600 animate-pulse" />
                  <div className="absolute inset-1 rounded-full bg-background" />
                  <div className="absolute inset-2 rounded-full bg-gradient-to-r from-violet-500 to-purple-600 animate-pulse" />
                </div>
                <span className="text-sm text-muted-foreground">
                  AI is analyzing your W-2...
                </span>
              </div>
            </SubSection>
            <SubSection title="Confidence Colors">
              <div className="flex gap-4">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-green-500" />
                  <span className="text-sm">High (95%+)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-yellow-500" />
                  <span className="text-sm">Medium (85-95%)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full bg-red-500" />
                  <span className="text-sm">Low (&lt;85%)</span>
                </div>
              </div>
            </SubSection>
          </Section>
        </div>
      </div>
    </TooltipProvider>
  );
}

function AnimationShowcase() {
  const [key, setKey] = useState(0);
  const replay = () => setKey((k) => k + 1);

  return (
    <div className="space-y-6">
      <Button variant="outline" onClick={replay}>
        Replay All Animations
      </Button>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4" key={key}>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">fadeIn</CardTitle>
          </CardHeader>
          <CardContent>
            <motion.div
              variants={fadeIn}
              initial="hidden"
              animate="visible"
              className="h-16 rounded-lg bg-primary/20 flex items-center justify-center"
            >
              <Star className="text-primary" />
            </motion.div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">slideInUp</CardTitle>
          </CardHeader>
          <CardContent>
            <motion.div
              variants={slideInUp}
              initial="hidden"
              animate="visible"
              className="h-16 rounded-lg bg-primary/20 flex items-center justify-center"
            >
              <Zap className="text-primary" />
            </motion.div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">slideInRight</CardTitle>
          </CardHeader>
          <CardContent>
            <motion.div
              variants={slideInRight}
              initial="hidden"
              animate="visible"
              className="h-16 rounded-lg bg-primary/20 flex items-center justify-center"
            >
              <Camera className="text-primary" />
            </motion.div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">scaleIn</CardTitle>
          </CardHeader>
          <CardContent>
            <motion.div
              variants={scaleIn}
              initial="hidden"
              animate="visible"
              className="h-16 rounded-lg bg-primary/20 flex items-center justify-center"
            >
              <Shield className="text-primary" />
            </motion.div>
          </CardContent>
        </Card>
      </div>

      <SubSection title="staggerContainer">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
          className="flex gap-3"
        >
          {["Snap", "Read", "Calculate", "File", "Done"].map((step) => (
            <motion.div
              key={step}
              variants={slideInUp}
              className="flex items-center gap-1 rounded-full bg-primary/10 px-4 py-2"
            >
              <Check className="h-3 w-3 text-primary" />
              <span className="text-sm font-medium">{step}</span>
            </motion.div>
          ))}
        </motion.div>
      </SubSection>
    </div>
  );
}
