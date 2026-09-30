"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
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
  authConfigured,
  confirmSignUp,
  googleEnabled,
  resendCode,
  signIn,
  signUp,
} from "@/lib/auth";

const detailsSchema = z.object({
  name: z.string().trim().min(1, "Enter your name").max(120, "Too long"),
  email: z.email("Enter a valid email address"),
  // Mirrors the pool's policy, so the common mistakes never reach Cognito.
  password: z
    .string()
    .min(8, "Use at least 8 characters")
    .regex(/\d/, "Include at least one number"),
});

const codeSchema = z.object({
  code: z
    .string()
    .trim()
    .regex(/^\d{6}$/, "Enter the 6-digit code"),
});

const submitClass =
  "mt-1 h-10 w-full cursor-pointer rounded-lg text-[15px] font-semibold";

/**
 * Two steps on one route: the details, then the emailed code. The step and the
 * address live in the URL, so a reload - or arriving from the log-in page with
 * an unconfirmed account - lands on the right one.
 */
export function SignUpForm() {
  const params = useSearchParams();
  const router = useRouter();
  // Kept only in memory, so a confirmed account can be signed in straight away.
  const [password, setPassword] = useState<string | null>(null);
  const email = params.get("email") ?? "";

  if (!authConfigured) return <SignInNotConfigured />;

  if (params.get("step") === "confirm" && email) {
    return <ConfirmStep email={email} password={password} />;
  }
  return (
    <DetailsStep
      onCreated={(address, secret) => {
        setPassword(secret);
        router.replace(
          `/signup?step=confirm&email=${encodeURIComponent(address)}`,
        );
      }}
    />
  );
}

function DetailsStep({
  onCreated,
}: {
  onCreated: (email: string, password: string) => void;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof detailsSchema>>({
    resolver: zodResolver(detailsSchema),
    defaultValues: { name: "", email: "", password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit(values: z.infer<typeof detailsSchema>) {
    setError(null);
    try {
      const { confirmed } = await signUp(values);
      if (confirmed) {
        await signIn(values.email, values.password);
        router.replace("/home");
      } else {
        onCreated(values.email, values.password);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  return (
    <AuthCard
      title="Create your account"
      subtitle="Start a board of your own."
      footer={
        <>
          Already have an account? <AuthLink href="/">Log in</AuthLink>
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
        <Field data-invalid={Boolean(errors.name)}>
          <FieldLabel htmlFor="name">Name</FieldLabel>
          <Input
            id="name"
            autoComplete="name"
            className={inputClass}
            aria-invalid={Boolean(errors.name)}
            {...form.register("name")}
          />
          {errors.name && <FieldError errors={[errors.name]} />}
        </Field>
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
            autoComplete="new-password"
            placeholder="At least 8 characters, one number"
            className={inputClass}
            aria-invalid={Boolean(errors.password)}
            {...form.register("password")}
          />
          {errors.password && <FieldError errors={[errors.password]} />}
        </Field>
        <Button
          type="submit"
          size="lg"
          className={submitClass}
          disabled={isSubmitting}
        >
          {isSubmitting ? "Creating account..." : "Create account"}
        </Button>
      </form>
      {googleEnabled && <GoogleSignIn onError={setError} />}
    </AuthCard>
  );
}

function ConfirmStep({
  email,
  password,
}: {
  email: string;
  password: string | null;
}) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const form = useForm<z.infer<typeof codeSchema>>({
    resolver: zodResolver(codeSchema),
    defaultValues: { code: "" },
  });
  const { errors, isSubmitting } = form.formState;

  async function onSubmit({ code }: z.infer<typeof codeSchema>) {
    setError(null);
    try {
      await confirmSignUp(email, code);
      if (password) {
        await signIn(email, password);
        router.replace("/home");
      } else {
        toast.success("Email confirmed. Log in to continue.");
        router.replace("/");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }

  async function resend() {
    setResending(true);
    try {
      await resendCode(email);
      toast.success(`A new code is on its way to ${email}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setResending(false);
    }
  }

  return (
    <AuthCard
      title="Check your email"
      subtitle={
        <>
          We sent a 6-digit code to{" "}
          <span className="font-medium text-foreground">{email}</span>.
        </>
      }
      footer={
        <>
          Wrong address? <AuthLink href="/signup">Start again</AuthLink>
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
        <Field data-invalid={Boolean(errors.code)}>
          <FieldLabel htmlFor="code">Confirmation code</FieldLabel>
          <Input
            id="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="123456"
            className={`${inputClass} tracking-[0.3em]`}
            aria-invalid={Boolean(errors.code)}
            {...form.register("code")}
          />
          {errors.code && <FieldError errors={[errors.code]} />}
        </Field>
        <Button
          type="submit"
          size="lg"
          className={submitClass}
          disabled={isSubmitting}
        >
          {isSubmitting ? "Confirming..." : "Confirm email"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="cursor-pointer text-muted-foreground"
          onClick={resend}
          disabled={resending}
        >
          {resending ? "Sending..." : "Send a new code"}
        </Button>
      </form>
    </AuthCard>
  );
}
