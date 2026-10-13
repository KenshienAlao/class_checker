"use client";

import * as React from "react";
import Link from "next/link";

import { ROUTES } from "@/config/routes.config";
import { useLogoutMutation } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

import {
  ArrowBackIcon,
  ChevronRightIcon,
  KeyIcon,
  LogoutIcon,
  MailIcon,
  PersonIcon,
  PhoneIcon,
  SchoolIcon,
  ShieldCheckIcon,
  Spinner,
  SwitchAccountIcon,
} from "@/components/icons";

// Placeholder profile data. Replace with session/user query when ready.
const profile = {
  name: "Teacher User",
  email: "teacher@example.com",
  phone: "+63 912 345 6789",
  school: "Sample National High School",
  image: null as string | null,
};

function getInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0];
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

function Avatar({ name, image }: { name: string; image: string | null }) {
  return (
    <div className="flex size-24 shrink-0 items-center justify-center overflow-hidden rounded-full border border-border bg-muted text-3xl font-semibold text-muted-foreground sm:size-28">
      {image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={image}
          alt=""
          width={112}
          height={112}
          className="size-full object-cover"
        />
      ) : (
        <span aria-hidden="true">{getInitials(name)}</span>
      )}
    </div>
  );
}

type RowProps = {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value?: string;
  href?: string;
  onClick?: () => void;
  disabled?: boolean;
  pending?: boolean;
  destructive?: boolean;
};

const rowBase =
  "flex min-h-14 w-full items-center gap-4 px-4 py-3 text-left sm:px-5";
const rowInteractive =
  "cursor-pointer transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none";

function Row({
  icon: Icon,
  label,
  value,
  href,
  onClick,
  disabled,
  pending,
  destructive,
}: RowProps) {
  const content = (
    <>
      {pending ? (
        <Spinner className="size-5 shrink-0" />
      ) : (
        <Icon
          className={cn(
            "size-5 shrink-0",
            destructive ? "text-destructive" : "text-muted-foreground",
          )}
        />
      )}
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            "block truncate text-sm",
            destructive
              ? "font-medium text-destructive"
              : "text-muted-foreground",
          )}
        >
          {label}
        </span>
        {value && (
          <span className="block truncate text-sm font-medium text-foreground sm:text-base">
            {value}
          </span>
        )}
      </span>
      {(href || onClick) && !destructive && (
        <ChevronRightIcon className="size-5 shrink-0 text-muted-foreground" />
      )}
    </>
  );

  if (href) {
    return (
      <Link href={href} className={cn(rowBase, rowInteractive)}>
        {content}
      </Link>
    );
  }

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className={cn(rowBase, rowInteractive)}
      >
        {content}
      </button>
    );
  }

  return <div className={rowBase}>{content}</div>;
}

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <div className="px-1">
        <h2 id={id} className="text-base font-semibold text-foreground">
          {title}
        </h2>
        {description && (
          <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      <ul className="divide-y divide-border overflow-hidden rounded-xl border bg-card shadow-sm">
        {React.Children.map(children, (child) => (
          <li>{child}</li>
        ))}
      </ul>
    </section>
  );
}

export default function Settings() {
  const { mutate, isPending, error } = useLogoutMutation();

  const notice = error
    ? error instanceof Error
      ? error.message
      : "Something went wrong."
    : null;

  return (
    <main className="min-h-dvh bg-background px-4 py-6 sm:px-6 sm:py-10">
      <div className="mx-auto w-full max-w-2xl space-y-8">
        <header className="space-y-4">
          <Link
            href={ROUTES.DASHBOARD}
            className="inline-flex items-center gap-2 rounded-sm text-sm font-medium text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none"
          >
            <ArrowBackIcon className="size-5" />
            Back to overview
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            Settings
          </h1>
        </header>

        <section
          aria-label="Account summary"
          className="flex flex-col items-center rounded-xl border bg-card px-4 py-8 text-center shadow-sm sm:px-8"
        >
          <Avatar name={profile.name} image={profile.image} />
          <p className="mt-4 max-w-full truncate text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            {profile.name}
          </p>
          <p className="mt-1 max-w-full truncate text-sm text-muted-foreground sm:text-base">
            {profile.email}
          </p>
        </section>

        <Section
          id="personal-info"
          title="Personal info"
          description="Your basic details and how we can reach you."
        >
          <Row icon={PersonIcon} label="Name" value={profile.name} />
          <Row icon={MailIcon} label="Email" value={profile.email} />
          <Row icon={PhoneIcon} label="Phone" value={profile.phone} />
          <Row icon={SchoolIcon} label="School" value={profile.school} />
        </Section>

        <Section
          id="security"
          title="Security"
          description="Keep your account protected."
        >
          <Row
            icon={KeyIcon}
            label="Password"
            value="Last changed 3 months ago"
          />
          <Row
            icon={ShieldCheckIcon}
            label="Two-step verification"
            value="Off"
          />
        </Section>

        <Section id="accounts" title="Accounts">
          <Row
            icon={SwitchAccountIcon}
            label="Switch account"
            href={ROUTES.AUTH.SIGNIN}
          />
          <Row
            icon={LogoutIcon}
            label={isPending ? "Logging out..." : "Log out"}
            onClick={() => mutate()}
            disabled={isPending}
            pending={isPending}
            destructive
          />
        </Section>

        {notice && (
          <p
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            {notice}
          </p>
        )}
      </div>
    </main>
  );
}
