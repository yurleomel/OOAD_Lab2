"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { startGoogleSignIn } from "@/lib/auth";

/** "OR" and the Google button; the caller renders it only when Google is enabled. */
export function GoogleSignIn({
  onError,
}: {
  onError: (message: string) => void;
}) {
  const [leaving, setLeaving] = useState(false);

  return (
    <>
      <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground before:h-px before:flex-1 before:bg-border after:h-px after:flex-1 after:bg-border">
        OR
      </div>
      <Button
        type="button"
        variant="outline"
        size="lg"
        className="h-10 w-full cursor-pointer rounded-lg text-[15px]"
        disabled={leaving}
        onClick={() => {
          setLeaving(true);
          startGoogleSignIn().catch((error: Error) => {
            setLeaving(false);
            onError(error.message);
          });
        }}
      >
        <svg viewBox="0 0 24 24" aria-hidden className="size-4.5">
          <path
            fill="#4285F4"
            d="M22.5 12.3c0-.8-.1-1.5-.2-2.2H12v4.2h5.9a5 5 0 0 1-2.2 3.3v2.7h3.6c2-1.9 3.2-4.7 3.2-8z"
          />
          <path
            fill="#34A853"
            d="M12 23c3 0 5.5-1 7.3-2.7l-3.6-2.7c-1 .7-2.2 1.1-3.7 1.1-2.9 0-5.3-1.9-6.2-4.5H2.1v2.8A11 11 0 0 0 12 23z"
          />
          <path
            fill="#FBBC05"
            d="M5.8 14.2a6.6 6.6 0 0 1 0-4.3V7.1H2.1a11 11 0 0 0 0 9.9z"
          />
          <path
            fill="#EA4335"
            d="M12 5.4c1.6 0 3.1.6 4.2 1.6l3.2-3.2A11 11 0 0 0 2.1 7.1l3.7 2.8C6.7 7.3 9.1 5.4 12 5.4z"
          />
        </svg>
        Continue with Google
      </Button>
    </>
  );
}
