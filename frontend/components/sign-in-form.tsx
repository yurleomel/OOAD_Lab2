"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  AuthCard,
  AuthLink,
  inputClass,
  SignInNotConfigured,
} from "@/components/auth-layout";
import { GoogleSignIn } from "@/components/google-button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  AuthError,
  authConfigured,
  googleEnabled,
  resendCode,
  signIn,
  useSession,
} from "@/lib/auth";

const schema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

type Values = z.infer<typeof schema>;

export function SignInForm() {
  const router = useRouter();
  const session = useSession();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  // Already signed in - in this tab, or by the submit below.
  useEffect(() => {
    if (session) router.replace("/home");
  }, [session, router]);

  if (!authConfigured) return <SignInNotConfigured />;

  async function onSubmit({ email, password }: Values) {
    setError(null);
    try {
      await signIn(email, password);
    } catch (caught) {
      if (
        caught instanceof AuthError &&
        caught.code === "UserNotConfirmedException"
      ) {
        // They signed up but never entered the code; send a fresh one.
        await resendCode(email).catch(() => {});
        router.push(`/signup?step=confirm&email=${encodeURIComponent(email)}`);
        return;
      }
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Log in to your Peach board."
      footer={
        <>
          New here? <AuthLink href="/signup">Create an account</AuthLink>
        </>
      }
    >
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
        <Field data-invalid={Boolean(errors.password)}>
          <FieldLabel htmlFor="password">Password</FieldLabel>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            placeholder="Enter your password"
            className={inputClass}
            aria-invalid={Boolean(errors.password)}
            {...form.register("password")}
          />
          {errors.password && <FieldError errors={[errors.password]} />}
        </Field>
        <Button
          type="submit"
          size="lg"
          className="mt-1 h-10 w-full cursor-pointer rounded-lg text-[15px] font-semibold"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Logging in..." : "Log in"}
        </Button>
      </form>
      {googleEnabled && <GoogleSignIn onError={setError} />}
    </AuthCard>
  );
}
