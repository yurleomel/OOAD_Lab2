"use client";

import { ArrowRight, House, Plus, SquareKanban } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { StatusIcon, StatusPill } from "@/components/status-icon";
import { useTaskDialogs } from "@/components/task-dialogs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { itemStatuses, type Item, type ItemStatus } from "@/lib/api";
import { useSession } from "@/lib/auth";
import { statusMeta } from "@/lib/item-status";
import { useItems } from "@/lib/use-items";
import { cn } from "@/lib/utils";

/** Monday 00:00, local time, of the week `now` falls in. */
function startOfWeek(now: Date): Date {
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  return start;
}

const newestFirst = (a: Item, b: Item) =>
  Date.parse(b.updated_at) - Date.parse(a.updated_at);

/** Everything the dashboard shows, derived from the task list alone. */
export function summarize(items: Item[], now = new Date()) {
  const counts: Record<ItemStatus, number> = {
    todo: 0,
    in_progress: 0,
    done: 0,
  };
  for (const item of items) counts[item.status] += 1;

  const total = items.length;
  const weekStart = startOfWeek(now).getTime();
  return {
    total,
    counts,
    donePercent: total ? Math.round((counts.done / total) * 100) : 0,
    addedThisWeek: items.filter(
      (item) => Date.parse(item.created_at) >= weekStart,
    ).length,
    // There is no completed_at: a done task last touched this week counts.
    completedThisWeek: items.filter(
      (item) =>
        item.status === "done" && Date.parse(item.updated_at) >= weekStart,
    ).length,
    inProgress: items
      .filter((item) => item.status === "in_progress")
      .sort(newestFirst)
      .slice(0, 5),
    recentlyDone: items
      .filter((item) => item.status === "done")
      .sort(newestFirst)
      .slice(0, 5),
  };
}

function greeting(now: Date) {
  const hour = now.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const plural = (n: number) => `${n} task${n === 1 ? "" : "s"}`;

export function TaskDashboard() {
  const session = useSession();
  const { openCreate } = useTaskDialogs();
  const { data, isPending, isError, error, refetch } = useItems();
  const firstName = session?.name.split(" ")[0];
  const now = new Date();

  return (
    <>
      <PageHeader
        icon={House}
        title={firstName ? `${greeting(now)}, ${firstName}` : greeting(now)}
        action={
          <Button size="lg" variant="outline" asChild>
            <Link href="/items">
              <SquareKanban data-icon="inline-start" className="size-4" />
              Open board
            </Link>
          </Button>
        }
      />

      <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-5">
        {isPending && (
          <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
            <Skeleton className="h-40 rounded-xl sm:col-span-2" />
            <Skeleton className="h-40 rounded-xl" />
            <Skeleton className="h-40 rounded-xl" />
            <Skeleton className="h-28 rounded-xl sm:col-span-2" />
            <Skeleton className="h-28 rounded-xl sm:col-span-2" />
          </div>
        )}

        {isError && (
          <Alert variant="destructive">
            <AlertTitle>Could not load tasks</AlertTitle>
            <AlertDescription className="flex items-center gap-4">
              <span>{(error as Error).message}</span>
              <Button size="sm" variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {data && data.total === 0 && (
          <div className="mx-auto mt-10 flex max-w-md flex-col items-center rounded-2xl border border-dashed border-border px-8 py-12 text-center">
            <span className="grid size-12 place-items-center rounded-2xl bg-accent-gradient text-white">
              <SquareKanban className="size-6" />
            </span>
            <h2 className="mt-5 text-lg font-bold">No tasks yet</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Add your first task and your progress will show up here.
            </p>
            <Button size="lg" className="mt-6" onClick={() => openCreate()}>
              <Plus data-icon="inline-start" className="size-4" />
              Create a task
            </Button>
          </div>
        )}

        {data && data.total > 0 && (
          <Overview summary={summarize(data.items, now)} />
        )}
      </div>
    </>
  );
}

function Tile({
  title,
  action,
  className,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className={cn("rounded-xl border border-border bg-card p-4", className)}
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-bold tracking-normal">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Overview({ summary }: { summary: ReturnType<typeof summarize> }) {
  const { openEdit } = useTaskDialogs();
  const viewAll = (status: ItemStatus) => (
    <Link
      href={`/items/list#status-${status}`}
      className="text-xs font-medium text-primary hover:underline"
    >
      View all
    </Link>
  );

  return (
    <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4">
      <Tile
        title="Progress"
        className="border-[#e4defc] bg-wash-gradient sm:col-span-2 dark:border-border"
      >
        <p className="flex items-baseline gap-2">
          <span className="font-heading text-5xl leading-none font-extrabold tracking-tight tabular-nums">
            {summary.donePercent}%
          </span>
          <span className="text-sm text-muted-foreground">
            of your tasks are done
          </span>
        </p>
        <div
          role="progressbar"
          aria-label="Tasks done"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={summary.donePercent}
          className="mt-4 h-2.5 overflow-hidden rounded-full bg-card"
        >
          <div
            className="h-full rounded-full bg-accent-gradient"
            style={{ width: `${summary.donePercent}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {summary.counts.done} of {plural(summary.total)}
        </p>
      </Tile>

      {(["in_progress", "todo"] as const).map((status) => (
        <Link
          key={status}
          href={`/items/list#status-${status}`}
          className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 transition hover:border-primary/40 hover:shadow-card-hover"
        >
          <StatusPill status={status} className="self-start" />
          <span className="font-heading text-4xl leading-none font-extrabold tabular-nums">
            {summary.counts[status]}
          </span>
          <span className="flex items-center gap-1 text-[13px] text-muted-foreground">
            Show in list <ArrowRight className="size-3.5" />
          </span>
        </Link>
      ))}

      <Tile title="By status" className="sm:col-span-2">
        <StatusBar counts={summary.counts} total={summary.total} />
      </Tile>

      <Tile title="This week" className="sm:col-span-2">
        <dl className="flex gap-10">
          {[
            ["added", summary.addedThisWeek],
            ["completed", summary.completedThisWeek],
          ].map(([label, value]) => (
            <div key={label} className="flex flex-col-reverse gap-1.5">
              <dt className="text-[13px] text-muted-foreground">{label}</dt>
              <dd className="font-heading text-3xl leading-none font-extrabold tabular-nums">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </Tile>

      {(
        [
          [
            "In progress",
            "in_progress",
            summary.inProgress,
            "Nothing in progress right now.",
          ],
          [
            "Recently completed",
            "done",
            summary.recentlyDone,
            "Nothing completed yet.",
          ],
        ] as const
      ).map(([title, status, items, empty]) => (
        <Tile
          key={status}
          title={title}
          action={viewAll(status)}
          className="sm:col-span-2"
        >
          {items.length === 0 ? (
            <p className="py-2 text-sm text-muted-foreground">{empty}</p>
          ) : (
            <ul>
              {items.map((item) => (
                <li
                  key={item.id}
                  className="border-b border-border/60 last:border-0"
                >
                  <button
                    type="button"
                    onClick={() => openEdit(item)}
                    className="flex h-10 w-full cursor-pointer items-center gap-2.5 rounded-md px-1 text-left text-sm font-medium transition-colors hover:bg-muted"
                  >
                    <StatusIcon status={item.status} />
                    <span className="truncate">{item.name}</span>
                    <span className="ml-auto shrink-0 text-xs font-normal text-muted-foreground tabular-nums">
                      {new Date(item.updated_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Tile>
      ))}
    </div>
  );
}

/** One stacked bar: a segment per status, 2px gaps, a tooltip on each. */
function StatusBar({
  counts,
  total,
}: {
  counts: Record<ItemStatus, number>;
  total: number;
}) {
  const share = (n: number) => Math.round((n / total) * 100);
  return (
    <>
      <div className="flex gap-0.5">
        {itemStatuses
          .filter((status) => counts[status] > 0)
          .map((status) => {
            const label = `${statusMeta[status].label}: ${plural(counts[status])}, ${share(counts[status])}%`;
            return (
              // The hit target is taller than the 12px mark it carries.
              <div
                key={status}
                tabIndex={0}
                aria-label={label}
                className="group relative py-2 outline-none"
                style={{ flexGrow: counts[status], flexBasis: 0 }}
              >
                <div
                  className={cn(
                    "h-3 rounded-[4px] transition-opacity group-hover:opacity-85",
                    statusMeta[status].mark,
                  )}
                />
                <span
                  role="tooltip"
                  className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 rounded-md bg-foreground px-2 py-1 text-xs whitespace-nowrap text-background opacity-0 shadow-notion-md transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                >
                  {label}
                </span>
              </div>
            );
          })}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-muted-foreground">
        {itemStatuses.map((status) => (
          <li key={status} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className={cn("size-2.5 rounded-full", statusMeta[status].mark)}
            />
            {statusMeta[status].label}
            <span className="font-semibold text-foreground tabular-nums">
              {counts[status]}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}
