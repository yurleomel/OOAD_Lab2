import { Suspense } from "react";

import { AuthCardSkeleton, AuthLayout } from "@/components/auth-layout";
import { SignUpForm } from "@/components/sign-up-form";

export const metadata = { title: "Create an account | Peach" };

export default function SignUpPage() {
  return (
    <AuthLayout>
      {/* The step comes from the query string, which the static export only
          knows in the browser. */}
      <Suspense fallback={<AuthCardSkeleton />}>
        <SignUpForm />
      </Suspense>
    </AuthLayout>
  );
}
