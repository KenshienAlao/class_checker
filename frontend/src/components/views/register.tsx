"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ROUTES } from "@/config/routes.config";
import { useRegisterMutation } from "@/hooks/use-auth";
import { fieldErrors } from "@/lib/form";
import { cn } from "@/lib/utils";
import { SignupSchema } from "@/validation/auth.validation";

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
      <path d="M6.61 6.61A13.53 13.53 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
      <line x1="2" x2="22" y1="2" y2="22" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className="size-4 animate-spin motion-reduce:animate-none"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth={4}
        className="opacity-25"
      />
      <path
        d="M4 12a8 8 0 0 1 8-8"
        stroke="currentColor"
        strokeWidth={4}
        strokeLinecap="round"
        className="opacity-75"
      />
    </svg>
  );
}

const fieldInvalid = "border-destructive focus-visible:ring-destructive";

export function Register() {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [show, setShow] = useState(false);
  const { mutate, isPending, error, reset } = useRegisterMutation();

  const notice = error
    ? error instanceof Error
      ? error.message
      : "Something went wrong."
    : null;

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    const formData = new FormData(e.currentTarget);
    const parsed = SignupSchema.safeParse({
      name: formData.get("name"),
      email: formData.get("email"),
      password: formData.get("password"),
      confirm: formData.get("confirm"),
    });

    if (!parsed.success) {
      setErrors(fieldErrors(parsed.error));
      return;
    }

    setErrors({});
    reset();
    mutate(parsed.data);
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background px-4 py-8 sm:px-6 sm:py-12">
      <div className="w-full max-w-md">
        <div className="sm:rounded-xl sm:border sm:bg-card sm:p-8 sm:shadow-sm">
          <header className="space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              Create your account
            </h1>
            <p className="text-sm text-muted-foreground sm:text-base">
              Enter your details to get started.
            </p>
          </header>

          <form
            onSubmit={handleSubmit}
            noValidate
            aria-busy={isPending}
            className="mt-8 space-y-4"
          >
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                name="name"
                type="text"
                autoComplete="name"
                aria-invalid={!!errors.name}
                aria-describedby={errors.name ? "name-error" : undefined}
                className={cn("h-11 sm:h-10", errors.name && fieldInvalid)}
              />
              {errors.name && (
                <p
                  id="name-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.name}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                autoCapitalize="none"
                spellCheck={false}
                placeholder="you@school.edu"
                aria-invalid={!!errors.email}
                aria-describedby={errors.email ? "email-error" : undefined}
                className={cn("h-11 sm:h-10", errors.email && fieldInvalid)}
              />
              {errors.email && (
                <p
                  id="email-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.email}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={show ? "text" : "password"}
                  autoComplete="new-password"
                  aria-invalid={!!errors.password}
                  aria-describedby={
                    errors.password ? "password-error" : undefined
                  }
                  className={cn(
                    "h-11 pr-11 sm:h-10",
                    errors.password && fieldInvalid,
                  )}
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  aria-label={show ? "Hide passwords" : "Show passwords"}
                  aria-pressed={show}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-md text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none sm:w-10"
                >
                  {show ? (
                    <EyeOffIcon className="size-4" />
                  ) : (
                    <EyeIcon className="size-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p
                  id="password-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.password}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm">Confirm password</Label>
              <Input
                id="confirm"
                name="confirm"
                type={show ? "text" : "password"}
                autoComplete="new-password"
                aria-invalid={!!errors.confirm}
                aria-describedby={errors.confirm ? "confirm-error" : undefined}
                className={cn("h-11 sm:h-10", errors.confirm && fieldInvalid)}
              />
              {errors.confirm && (
                <p
                  id="confirm-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.confirm}
                </p>
              )}
            </div>

            {notice && (
              <p
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {notice}
              </p>
            )}

            <Button
              type="submit"
              className="h-11 w-full sm:h-10"
              disabled={isPending}
            >
              {isPending ? (
                <>
                  <Spinner />
                  Creating account...
                </>
              ) : (
                "Create account"
              )}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link
            href={ROUTES.AUTH.SIGNIN}
            className="rounded-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Log in
          </Link>
        </p>
      </div>
    </main>
  );
}
