import Link from "next/link";

import { AuthCard, AuthLayout, AuthLink } from "@/components/auth-layout";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Not found | Lanora" };

export default function NotFound() {
  return (
    <AuthLayout>
      <AuthCard
        title="Page not found"
        subtitle="There is nothing at this address."
        footer={
          <>
            Signed out? <AuthLink href="/">Log in</AuthLink>
          </>
        }
      >
        <Button
          asChild
          size="lg"
          className="h-10 w-full rounded-lg text-[15px] font-semibold"
        >
          <Link href="/home">Go to your board</Link>
        </Button>
      </AuthCard>
    </AuthLayout>
  );
}
