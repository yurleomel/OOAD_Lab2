"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlignLeft, CalendarDays, Plus } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import { ItemsHeader } from "@/components/items-header";
import { StatusIcon, StatusPill } from "@/components/status-icon";
import { useTaskDialogs } from "@/components/task-dialogs";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  api,
  itemStatuses,
  type Item,
  type ItemList,
  type ItemStatus,
} from "@/lib/api";
import { statusMeta } from "@/lib/item-status";
import { useItems } from "@/lib/use-items";
import { cn } from "@/lib/utils";

const DRAG_TYPE = "application/x-peach-item";

type DragInfo = {
  id: string;
  from: ItemStatus;
  /** Where inside the card it was grabbed, so we can track the card's footprint. */
  offsetX: number;
  width: number;
};

export function ItemBoard() {
  const queryClient = useQueryClient();
  const { openCreate, openEdit } = useTaskDialogs();
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<ItemStatus | null>(null);
  const drag = useRef<DragInfo | null>(null);
  const columns = useRef<Partial<Record<ItemStatus, HTMLElement | null>>>({});

  const { data, isPending, isError, error, refetch } = useItems();

  const move = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ItemStatus }) =>
      api.updateItem(id, { status }),
    // Move the card immediately; roll back if the API refuses.
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ["items"] });
      const previous = queryClient.getQueryData<ItemList>(["items"]);
      queryClient.setQueryData<ItemList>(["items"], (old) =>
        old
          ? {
              ...old,
              items: old.items.map((it) =>
                it.id === id ? { ...it, status } : it,
              ),
            }
          : old,
      );
      return { previous };
    },
    onError: (err: Error, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["items"], context.previous);
      }
      toast.error(err.message);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["items"] }),
  });

  /** A card counts as over another column as soon as any part of it overlaps
   *  that column; otherwise fall back to whatever column the pointer is in. */
  function targetFor(event: DragEvent): ItemStatus | null {
    const info = drag.current;
    if (!info) return null;
    // Some browsers report 0,0 on the last dragover; keep the previous target.
    if (event.clientX === 0 && event.clientY === 0) return dropTarget;

    const left = event.clientX - info.offsetX;
    const right = left + info.width;
    let best: ItemStatus | null = null;
    let bestOverlap = 0;
    for (const status of itemStatuses) {
      if (status === info.from) continue;
      const rect = columns.current[status]?.getBoundingClientRect();
      if (!rect) continue;
      const overlap = Math.min(right, rect.right) - Math.max(left, rect.left);
      if (overlap > bestOverlap) {
        best = status;
        bestOverlap = overlap;
      }
    }
    if (best) return best;

    const under = (event.target as HTMLElement).closest<HTMLElement>(
      "[data-status]",
    );
    return (under?.dataset.status as ItemStatus | undefined) ?? info.from;
  }

  function handleDragOver(event: DragEvent) {
    if (!drag.current) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    const target = targetFor(event);
    if (target !== dropTarget) setDropTarget(target);
  }

  function handleDrop(event: DragEvent) {
    event.preventDefault();
    const info = drag.current;
    const target = targetFor(event);
    endDrag();
    if (info && target && target !== info.from) {
      move.mutate({ id: info.id, status: target });
    }
  }

  function endDrag() {
    drag.current = null;
    setDraggingId(null);
    setDropTarget(null);
  }

  return (
    <>
      <ItemsHeader />

      {isError ? (
        <div className="p-4 sm:p-6">
          <Alert variant="destructive">
            <AlertTitle>Could not load tasks</AlertTitle>
            <AlertDescription className="flex items-center gap-4">
              <span>{(error as Error).message}</span>
              <Button size="sm" variant="outline" onClick={() => refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      ) : (
        <div
          className="min-h-0 flex-1 overflow-auto p-3 sm:p-4"
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              setDropTarget(null);
            }
          }}
        >
          <div className="grid min-h-full min-w-[720px] grid-cols-3 gap-3">
            {itemStatuses.map((status) => {
              const cards =
                data?.items.filter((item) => item.status === status) ?? [];
              const isTarget = dropTarget === status;
              return (
                <section
                  key={status}
                  aria-label={statusMeta[status].label}
                  data-status={status}
                  ref={(node) => {
                    columns.current[status] = node;
                  }}
                  className={cn(
                    "flex flex-col gap-2 rounded-xl p-2.5 transition-[outline-color]",
                    statusMeta[status].column,
                    "outline-2 -outline-offset-2 outline-transparent outline-dashed",
                    isTarget && "outline-status-progress",
                  )}
                >
                  <header className="flex items-center gap-2 px-0.5 pb-1">
                    <StatusPill status={status} />
                    <span className="text-sm font-medium text-muted-foreground tabular-nums">
                      {data ? cards.length : ""}
                    </span>
                  </header>

                  {isPending && (
                    <>
                      <Skeleton className="h-18 w-full rounded-lg bg-card" />
                      <Skeleton className="h-18 w-full rounded-lg bg-card" />
                    </>
                  )}

                  {cards.map((item) => (
                    <BoardCard
                      key={item.id}
                      item={item}
                      dragging={draggingId === item.id}
                      onOpen={() => openEdit(item)}
                      onDragStart={(event) => {
                        const rect =
                          event.currentTarget.getBoundingClientRect();
                        drag.current = {
                          id: item.id,
                          from: status,
                          offsetX: event.clientX - rect.left,
                          width: rect.width,
                        };
                        event.dataTransfer.setData(DRAG_TYPE, item.id);
                        event.dataTransfer.effectAllowed = "move";
                        setDraggingId(item.id);
                      }}
                      onDragEnd={endDrag}
                    />
                  ))}

                  {data && (
                    <button
                      type="button"
                      onClick={() => openCreate(status)}
                      className="flex h-9 cursor-pointer items-center gap-2 rounded-lg px-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-black/5 hover:text-foreground"
                    >
                      <Plus className="size-4" />
                      Add task
                    </button>
                  )}
                </section>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}

type CardProps = {
  item: Item;
  dragging: boolean;
  onOpen: () => void;
  onDragStart: (event: DragEvent<HTMLDivElement>) => void;
  onDragEnd: () => void;
};

function BoardCard({
  item,
  dragging,
  onOpen,
  onDragStart,
  onDragEnd,
}: CardProps) {
  const done = item.status === "done";
  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      aria-label={`Edit ${item.name}`}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={cn(
        "cursor-pointer rounded-[10px] bg-card px-3 py-2.5 text-left shadow-card transition-shadow select-none",
        "hover:shadow-card-hover focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        "active:cursor-grabbing",
        dragging && "opacity-40",
      )}
    >
      <div className="flex items-start gap-2">
        <StatusIcon status={item.status} className="mt-0.5" />
        <p
          className={cn(
            "text-sm leading-snug font-medium break-words",
            done && "text-muted-foreground line-through",
          )}
        >
          {item.name}
        </p>
      </div>
      {item.description && (
        <p className="mt-1 ml-6 line-clamp-2 text-[13px] leading-relaxed break-words text-muted-foreground">
          {item.description}
        </p>
      )}
      <div className="mt-2 ml-6 flex items-center gap-2.5 text-xs text-muted-foreground">
        {item.description && (
          <AlignLeft aria-label="Has a description" className="size-3.5" />
        )}
        <span className="flex items-center gap-1">
          <CalendarDays aria-hidden className="size-3.5" />
          {new Date(item.created_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })}
        </span>
      </div>
    </div>
  );
}
