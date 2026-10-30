import { ArrowRight, BookOpen, CreditCard, Landmark, Plus, TrendingUp } from "lucide-react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import {
  Alert,
  Avatar,
  Badge,
  Button,
  Card,
  CardTitle,
  Checkbox,
  ClassCover,
  Container,
  DataList,
  EmptyState,
  Field,
  Input,
  Logo,
  PageHeader,
  Select,
  Skeleton,
  StatTile,
  StatusPill,
  Textarea,
} from "@eduzone/ui";

import { DialogDemo, ToastDemo } from "./demos";

// Internal style guide: every component of packages/ui in one place, for review before use.
// Development only; sample copy is in English on purpose (not user-facing).
export const metadata: Metadata = { title: "EduZone design system", robots: { index: false } };

const swatches: Array<[string, string]> = [
  ["brand-950", "--ez-brand-950"],
  ["brand-900", "--ez-brand-900"],
  ["brand-800", "--ez-brand-800"],
  ["brand-700 · accent", "--ez-brand-700"],
  ["brand-600", "--ez-brand-600"],
  ["brand-500", "--ez-brand-500"],
  ["brand-300", "--ez-brand-300"],
  ["brand-100", "--ez-brand-100"],
  ["brand-50", "--ez-brand-50"],
  ["gold-600", "--ez-gold-600"],
  ["gold-500", "--ez-gold-500"],
  ["gold-300", "--ez-gold-300"],
  ["gold-100", "--ez-gold-100"],
  ["paper (page)", "--ez-surface"],
  ["sunken", "--ez-sunken"],
  ["border", "--ez-border"],
  ["text", "--ez-text"],
  ["muted", "--ez-text-muted"],
];

export default function DesignPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <Container className="flex flex-col gap-16 py-12">
      <div className="flex items-center justify-between">
        <Logo name="EduZone" sub="Design system" />
        <Badge tone="gold">v1 · placeholder brand</Badge>
      </div>

      <PageHeader
        eyebrow="Foundations"
        title="Scholarly, modern, calm."
        description="Deep forest green for trust, warm gold for emphasis, ivory paper for reading. Fraunces for headings, Instrument Sans for everything else."
      />

      <Section title="Colour">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {swatches.map(([name, v]) => (
            <div key={v} className="overflow-hidden rounded-ez border border-border bg-surface">
              <div className="h-16" style={{ background: `var(${v})` }} />
              <div className="p-2.5">
                <p className="text-xs font-semibold">{name}</p>
                <p className="font-mono text-[0.7rem] text-muted">{v}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {(["success", "warning", "danger", "info", "brand", "gold", "neutral"] as const).map((tone) => (
            <Badge key={tone} tone={tone} dot>
              {tone}
            </Badge>
          ))}
        </div>
      </Section>

      <Section title="Type">
        <div className="flex flex-col gap-4">
          <p className="font-display text-6xl leading-none font-semibold">
            Display <span className="text-brand-600 italic">60</span>
          </p>
          <p className="font-display text-4xl font-semibold">Page title · 36</p>
          <p className="font-display text-2xl font-semibold">Section title · 24</p>
          <p className="text-lg">Lead text · 18 — Join live classes, watch recordings and download tutes.</p>
          <p>Body · 16 — Pay month by month, only for what you need. ශිෂ්‍යයින් සඳහා පන්ති.</p>
          <p className="text-sm text-muted">Small · 14 — Supporting text and hints.</p>
          <p className="text-xs font-bold tracking-[0.14em] text-brand-600 uppercase">Eyebrow · 12</p>
          <p className="font-display text-3xl font-semibold tabular-nums">Rs. 2,000.00</p>
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="gold" iconRight={<ArrowRight className="size-4" />}>
            Gold
          </Button>
          <Button variant="danger">Danger</Button>
          <Button variant="link">Link</Button>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button size="sm" icon={<Plus className="size-4" />}>Small</Button>
          <Button icon={<CreditCard className="size-4.5" />}>Pay Rs. 2,000.00</Button>
          <Button size="lg">Large</Button>
          <Button loading>Saving</Button>
          <Button disabled>Disabled</Button>
        </div>
      </Section>

      <Section title="Forms">
        <Card className="grid gap-5 sm:grid-cols-2">
          <Field label="Phone number" hint="For example 077 123 4567">
            <Input type="tel" placeholder="077 123 4567" />
          </Field>
          <Field label="Exam" optional="Optional">
            <Select defaultValue="al">
              <option value="al">A/L</option>
              <option value="ol">O/L</option>
            </Select>
          </Field>
          <Field label="Class title" error="A title is required.">
            <Input aria-invalid placeholder="2027 A/L Physics" />
          </Field>
          <Field label="Code">
            <Input className="min-h-14 text-center font-display text-2xl tracking-[0.5em]" defaultValue="835388" />
          </Field>
          <Field label="Description" className="sm:col-span-2">
            <Textarea placeholder="What students will learn…" />
          </Field>
          <Checkbox label="Allow students to request past months" defaultChecked />
        </Card>
      </Section>

      <Section title="Status">
        <div className="flex flex-wrap gap-2">
          <StatusPill state="paid">You have access</StatusPill>
          <StatusPill state="unpaid">Pay to unlock</StatusPill>
          <StatusPill state="pending">Request sent</StatusPill>
          <StatusPill state="closed">Past month</StatusPill>
          <StatusPill state="upcoming">Opens soon</StatusPill>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <Alert tone="success" title="Payment received">You now have access to November 2026.</Alert>
          <Alert tone="warning" title="Storage almost full">80% of your video storage is used.</Alert>
          <Alert tone="danger">The code is wrong. 4 tries left.</Alert>
          <Alert tone="info">The Zoom link will appear before the class.</Alert>
        </div>
      </Section>

      <Section title="Cards and data">
        <div className="grid gap-4 md:grid-cols-3">
          <StatTile tone="brand" icon={<Landmark />} label="EduZone owes you" value="Rs. 3,620.00" hint="After commission, fees and payouts" />
          <StatTile icon={<TrendingUp />} label="Your earnings" value="Rs. 4,620.00" hint="Last 12 months" />
          <StatTile tone="gold" label="Commission" value="20%" hint="Gateway fees from your earnings" />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardTitle action={<Button size="sm" variant="secondary">Edit</Button>}>Receipt</CardTitle>
            <DataList
              className="mt-3"
              items={[
                ["Order number", "EZ-2610-417931"],
                ["Paid on", "30 Oct 2026, 01:00"],
                ["Amount", "Rs. 2,000.00"],
              ]}
            />
          </Card>
          <Card className="flex flex-col gap-4">
            <CardTitle>People</CardTitle>
            {["Kasun Perera", "Nimali Silva", "Tharindu Jayasinghe"].map((n) => (
              <div key={n} className="flex items-center gap-3">
                <Avatar name={n} />
                <div>
                  <p className="font-semibold">{n}</p>
                  <p className="text-sm text-muted">+94 77 ••• ••••</p>
                </div>
              </div>
            ))}
          </Card>
        </div>
      </Section>

      <Section title="Class covers (generated)">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            ["2027 A/L Physics - Theory", "Physics", "A/L"],
            ["Combined Maths Revision", "Combined Maths", "A/L"],
            ["O/L Science Paper Class", "Science", "O/L"],
            ["Grade 5 Scholarship", "Scholarship", "Grade 5"],
            ["Biology Unit 4", "Biology", "A/L"],
            ["ICT Practical", "ICT", "A/L"],
            ["English Literature", "English", "O/L"],
            ["Accounting Theory", "Accounting", "A/L"],
          ].map(([title, subject, exam]) => (
            <div key={title} className="overflow-hidden rounded-ez shadow-ez">
              <ClassCover title={title} subject={subject} label={exam} />
            </div>
          ))}
        </div>
      </Section>

      <Section title="Feedback">
        <div className="grid gap-4 md:grid-cols-2">
          <EmptyState icon={<BookOpen />} title="No classes yet" body="Find a class and join it. Your classes will be waiting here." action={<Button>Browse classes</Button>} />
          <Card className="flex flex-col gap-3">
            <Skeleton className="h-36" />
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-4 w-1/3" />
          </Card>
        </div>
        <div className="flex flex-wrap gap-3">
          <DialogDemo />
          <ToastDemo />
        </div>
      </Section>
    </Container>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-5">
      <h2 className="border-b border-border pb-3 font-display text-2xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}
