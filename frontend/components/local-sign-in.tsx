"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { AuthCard, inputClass } from "@/components/auth-layout";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { signInLocally } from "@/lib/auth";

const schema = z.object({
  email: z.email("Enter a valid email address"),
  name: z.string().trim().max(120, "Too long"),
});

type Values = z.infer<typeof schema>;

function LocalBadge() {
  return (
    <span className="mb-3 inline-flex h-6 items-center rounded-md bg-primary/10 px-2 text-xs font-semibold tracking-wide text-primary uppercase">
      Local development
    </span>
  );
}

/**
 * Sign-in for a build without a Cognito pool - `docker compose up` on a fresh
 * checkout. The signed-in redirect is SignInForm's; this only stores a session.
 */
export function LocalSignInForm() {
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", name: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit({ email, name }: Values) {
    setError(null);
    try {
      await signInLocally(email, name);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <AuthCard
      title="Welcome to Lanora"
      subtitle="No Cognito and no password here: use any email. The same email brings back the same board."
    >
      <LocalBadge />
      <form
        noValidate
        onSubmit={form.handleSubmit(onSubmit)}
        className="grid gap-4"
      >
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <Field data-invalid={Boolean(errors.email)}>
          <FieldLabel htmlFor="email">Email</FieldLabel>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            className={inputClass}
            aria-invalid={Boolean(errors.email)}
            {...form.register("email")}
          />
          {errors.email && <FieldError errors={[errors.email]} />}
        </Field>
        <Field data-invalid={Boolean(errors.name)}>
          <FieldLabel htmlFor="name">
            Name{" "}
            <span className="font-normal text-muted-foreground">
              (optional)
            </span>
          </FieldLabel>
          <Input
            id="name"
            autoComplete="name"
            className={inputClass}
            aria-invalid={Boolean(errors.name)}
            {...form.register("name")}
          />
          {errors.name && <FieldError errors={[errors.name]} />}
        </Field>
        <Button
          type="submit"
          size="lg"
          className="mt-1 h-10 w-full cursor-pointer rounded-lg text-[15px] font-semibold"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Signing in..." : "Continue"}
        </Button>
      </form>
    </AuthCard>
  );
}

/** /signup in a build without a Cognito pool: there is nothing to sign up for. */
export function LocalSignUpNotice() {
  return (
    <AuthCard
      title="No sign-up needed"
      subtitle="Locally, any email signs straight in and gets its own board."
    >
      <LocalBadge />
      <Button
        asChild
        size="lg"
        className="h-10 w-full rounded-lg text-[15px] font-semibold"
      >
        <Link href="/">Continue to sign in</Link>
      </Button>
    </AuthCard>
  );
}
