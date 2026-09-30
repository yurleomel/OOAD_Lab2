import Link from "next/link";

import { BrandMark } from "@/components/brand-mark";
import { Skeleton } from "@/components/ui/skeleton";

/** White, bordered fields for the auth cards and the task dialog. */
export const inputClass =
  "h-10 rounded-lg border-input bg-card px-3 focus-visible:bg-card";

/** The signed-out pages: a soft gradient backdrop with one card in the middle. */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col auth-backdrop">
      <header className="flex h-13 shrink-0 items-center px-3">
        <Link
          href="/"
          className="flex items-center gap-2.5 rounded-lg py-1.5 pr-2.5 pl-1.5 text-[15px] font-semibold transition-colors hover:bg-black/5"
        >
          <BrandMark />
          Peach
        </Link>
      </header>
      <main className="grid flex-1 place-items-center px-4 py-10">
        {children}
      </main>
    </div>
  );
}

export function AuthCard({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="w-full max-w-[420px] rounded-[18px] bg-card px-6 pt-8 pb-7 shadow-notion-md sm:px-8">
      <BrandMark className="mb-5 size-10 rounded-xl text-xl" />
      <h1 className="text-[26px] leading-tight font-extrabold">{title}</h1>
      {subtitle && (
        <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
      )}
      {children && <div className="mt-6">{children}</div>}
      {footer && (
        <p className="mt-5 text-center text-sm text-muted-foreground">
          {footer}
        </p>
      )}
    </div>
  );
}

export function AuthCardSkeleton() {
  return (
    <div className="w-full max-w-[420px] rounded-[18px] bg-card px-8 pt-8 pb-7 shadow-notion-md">
      <Skeleton className="mb-5 size-10 rounded-xl" />
      <Skeleton className="h-7 w-2/3" />
      <Skeleton className="mt-6 h-10" />
      <Skeleton className="mt-4 h-10" />
    </div>
  );
}

/** A link inside auth copy: the accent colour, underlined on hover. */
export function AuthLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className="font-semibold text-primary hover:underline">
      {children}
    </Link>
  );
}

/** Shown instead of a form when the build carries no Cognito pool ids. */
export function SignInNotConfigured() {
  return (
    <AuthCard
      title="Sign-in is not set up"
      subtitle="This build has no Cognito user pool to sign in against."
    >
      <p className="text-sm leading-relaxed text-muted-foreground">
        Run <code>make deploy-cognito</code>, which writes the pool ids to{" "}
        <code>.env</code>, then rebuild the frontend with{" "}
        <code>docker compose up --build</code>.
      </p>
    </AuthCard>
  );
}
