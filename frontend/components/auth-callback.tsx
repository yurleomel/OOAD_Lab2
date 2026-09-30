"use client";

import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AuthCard } from "@/components/auth-layout";
import { Button } from "@/components/ui/button";
import { completeGoogleSignIn } from "@/lib/auth";

/** Where the hosted domain sends the browser back after Google. */
export function AuthCallback() {
  const params = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  // An authorization code works once; Strict Mode must not spend it twice.
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    completeGoogleSignIn(new URLSearchParams(params.toString()))
      .then(() => router.replace("/home"))
      .catch((caught: Error) => setError(caught.message));
  }, [params, router]);

  if (error) {
    return (
      <AuthCard title="Google sign-in failed" subtitle={error}>
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
    <AuthCard
      title="Signing you in"
      subtitle="Finishing sign-in with Google..."
    >
      <LoaderCircle
        aria-label="Loading"
        className="mx-auto size-6 animate-spin text-muted-foreground"
      />
    </AuthCard>
  );
}
