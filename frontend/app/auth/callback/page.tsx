import { Suspense } from "react";

import { AuthCallback } from "@/components/auth-callback";
import { AuthCardSkeleton, AuthLayout } from "@/components/auth-layout";

export const metadata = { title: "Signing in | Peach" };

export default function AuthCallbackPage() {
  return (
    <AuthLayout>
      <Suspense fallback={<AuthCardSkeleton />}>
        <AuthCallback />
      </Suspense>
    </AuthLayout>
  );
}
