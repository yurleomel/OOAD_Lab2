"use client";

import { LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useHydrated, useSession } from "@/lib/auth";

/**
 * Sends signed-out visitors to the log-in page. A convenience, not a boundary:
 * the static export has no server to refuse a page, and the API answers nothing
 * without a valid token anyway.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const hydrated = useHydrated();
  const session = useSession();
  const router = useRouter();
  const signedOut = hydrated && !session;

  useEffect(() => {
    if (signedOut) router.replace("/");
  }, [signedOut, router]);

  if (!session) {
    return (
      <div className="grid h-dvh place-items-center" aria-busy>
        <LoaderCircle
          aria-label="Loading"
          className="size-6 animate-spin text-muted-foreground"
        />
      </div>
    );
  }
  return children;
}
