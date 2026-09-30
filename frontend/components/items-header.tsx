"use client";

import { ListChecks, Plus, SquareKanban, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { useTaskDialogs } from "@/components/task-dialogs";
import { Button } from "@/components/ui/button";
import { useItems } from "@/lib/use-items";
import { cn } from "@/lib/utils";

const views: { href: string; label: string; Icon: LucideIcon; tint: string }[] =
  [
    {
      href: "/items",
      label: "Board",
      Icon: SquareKanban,
      tint: "bg-status-progress",
    },
    {
      href: "/items/list",
      label: "List",
      Icon: ListChecks,
      tint: "bg-chart-1",
    },
  ];

/** Title, task count, "New task", and the Board / List view tabs. */
export function ItemsHeader() {
  const { data } = useItems();
  const { openCreate } = useTaskDialogs();
  const pathname = usePathname() ?? "";

  return (
    <PageHeader
      icon={SquareKanban}
      title="Board"
      meta={
        data ? `${data.total} task${data.total === 1 ? "" : "s"}` : "Loading..."
      }
      action={
        <Button size="lg" onClick={() => openCreate("todo")}>
          <Plus data-icon="inline-start" className="size-4" />
          New task
        </Button>
      }
    >
      <nav aria-label="Views" className="mt-3 -mb-px flex gap-1">
        {views.map(({ href, label, Icon, tint }) => {
          const active = pathname.replace(/\/$/, "") === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2 rounded-t-lg border-b-2 px-2.5 pt-2 pb-2.5 text-sm font-medium transition-colors",
                active
                  ? "border-primary font-semibold text-foreground"
                  : "border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "grid size-4.5 place-items-center rounded-[5px] text-white",
                  tint,
                )}
              >
                <Icon className="size-3" strokeWidth={2.6} />
              </span>
              {label}
            </Link>
          );
        })}
      </nav>
    </PageHeader>
  );
}
