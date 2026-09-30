"use client";

import { ChevronDown, Plus } from "lucide-react";
import { useState } from "react";

import { ItemsHeader } from "@/components/items-header";
import { StatusIcon, StatusPill } from "@/components/status-icon";
import { useTaskDialogs } from "@/components/task-dialogs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { itemStatuses, type ItemStatus } from "@/lib/api";
import { statusMeta } from "@/lib/item-status";
import { useItems } from "@/lib/use-items";
import { cn } from "@/lib/utils";

const columns =
  "grid grid-cols-[minmax(0,1fr)_6rem] sm:grid-cols-[minmax(0,1fr)_8rem_8rem]";

function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/** The same tasks as the board, grouped by status into collapsible sections. */
export function ItemList() {
  const { openCreate, openEdit } = useTaskDialogs();
  const { data, isPending, isError, error, refetch } = useItems();
  const [collapsed, setCollapsed] = useState<Record<ItemStatus, boolean>>({
    todo: false,
    in_progress: false,
    done: false,
  });

  return (
    <>
      <ItemsHeader />

      <div className="min-h-0 flex-1 overflow-auto px-2 pb-8 sm:px-5">
        {isError && (
          <Alert variant="destructive" className="mt-4">
            <AlertTitle>Could not load tasks</AlertTitle>
            <AlertDescription className="flex items-center gap-4">
              <span>{(error as Error).message}</span>
              <Button size="sm" variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {!isError && (
          <div
            className={cn(
              columns,
              "border-b border-border py-3 pr-3 pl-11 text-[13px] text-muted-foreground",
            )}
          >
            <span>Name</span>
            <span>Created</span>
            <span className="hidden sm:block">Updated</span>
          </div>
        )}

        {isPending &&
          Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="mx-3 mt-4 h-8" />
          ))}

        {data &&
          itemStatuses.map((status) => {
            const rows = data.items.filter((item) => item.status === status);
            const open = !collapsed[status];
            return (
              <section
                key={status}
                id={`status-${status}`}
                aria-label={statusMeta[status].label}
                className="scroll-mt-4 pt-4"
              >
                <div className="flex items-center gap-2.5 pb-2 pl-1.5">
                  <button
                    type="button"
                    aria-expanded={open}
                    aria-label={`${open ? "Collapse" : "Expand"} ${statusMeta[status].label}`}
                    onClick={() =>
                      setCollapsed((current) => ({
                        ...current,
                        [status]: open,
                      }))
                    }
                    className="grid size-6 cursor-pointer place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    <ChevronDown
                      className={cn(
                        "size-4 transition-transform",
                        !open && "-rotate-90",
                      )}
                    />
                  </button>
                  <StatusPill status={status} />
                  <span className="text-sm font-medium text-muted-foreground tabular-nums">
                    {rows.length}
                  </span>
                </div>

                {open && (
                  <>
                    {rows.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        aria-label={`Edit ${item.name}`}
                        onClick={() => openEdit(item)}
                        className={cn(
                          columns,
                          "h-11 w-full cursor-pointer items-center border-b border-border/60 pr-3 pl-10 text-left transition-colors hover:bg-muted",
                        )}
                      >
                        <span className="flex min-w-0 items-center gap-2.5 font-medium">
                          <StatusIcon status={item.status} />
                          <span
                            className={cn(
                              "truncate",
                              item.status === "done" && "text-muted-foreground",
                            )}
                          >
                            {item.name}
                          </span>
                        </span>
                        <span className="text-[13px] text-muted-foreground tabular-nums">
                          {shortDate(item.created_at)}
                        </span>
                        <span className="hidden text-[13px] text-muted-foreground tabular-nums sm:block">
                          {shortDate(item.updated_at)}
                        </span>
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => openCreate(status)}
                      className="flex h-11 w-full cursor-pointer items-center gap-2.5 border-b border-border/60 pl-10 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <Plus className="size-4" />
                      Add task
                    </button>
                  </>
                )}
              </section>
            );
          })}
      </div>
    </>
  );
}
