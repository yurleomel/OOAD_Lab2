"use client";

import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { AuthCard } from "@/components/auth-layout";
import { Button } from "@/components/ui/button";
import { hostedSignInConfigured, startHostedSignIn } from "@/lib/auth";

/** /login: hands the browser to Cognito's managed login page straight away.
 *  The PKCE verifier and state are saved here first, so the callback accepts the code. */
export function HostedLogin() {
  const [error, setError] = useState<string | null>(null);
  // Strict Mode runs effects twice; one redirect is enough.
  const started = useRef(false);

  useEffect(() => {
    if (!hostedSignInConfigured || started.current) return;
    started.current = true;
    startHostedSignIn().catch((caught: Error) => setError(caught.message));
  }, []);

  if (!hostedSignInConfigured || error) {
    return (
      <AuthCard
        title="Sign-in is unavailable"
        subtitle={error ?? "This build has no Cognito user pool configured."}
      >
        <Button
          asChild
          size="lg"
          className="h-10 w-full rounded-lg text-[15px] font-semibold"
        >
          <Link href="/">Back to log in</Link>
        </Button>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Signing you in" subtitle="Opening the sign-in page...">
      <LoaderCircle
        aria-label="Loading"
        className="mx-auto size-6 animate-spin text-muted-foreground"
      />
    </AuthCard>
  );
}
