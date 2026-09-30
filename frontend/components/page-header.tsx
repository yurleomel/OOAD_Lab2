import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type Props = {
  /** Drawn white on the accent gradient, in front of the title. */
  icon: LucideIcon;
  title: string;
  /** Quiet text after the title, e.g. a count. */
  meta?: React.ReactNode;
  /** Rendered at the trailing edge of the title row. */
  action?: React.ReactNode;
  /** A tab strip under the title; without one the header closes with padding. */
  children?: React.ReactNode;
  className?: string;
};

export function PageHeader({
  icon: Icon,
  title,
  meta,
  action,
  children,
  className,
}: Props) {
  return (
    <header
      className={cn(
        "shrink-0 border-b border-border px-4 pt-4 sm:px-6",
        !children && "pb-4",
        className,
      )}
    >
      <div className="flex min-h-9 flex-wrap items-center gap-x-3 gap-y-2">
        <span
          aria-hidden
          className="grid size-7 place-items-center rounded-lg bg-accent-gradient text-white"
        >
          <Icon className="size-4" strokeWidth={2.4} />
        </span>
        <h1 className="text-xl font-bold">{title}</h1>
        {meta && <span className="text-sm text-muted-foreground">{meta}</span>}
        {action && <div className="ml-auto">{action}</div>}
      </div>
      {children}
    </header>
  );
}
