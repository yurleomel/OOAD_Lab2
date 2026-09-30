import type { ItemStatus } from "@/lib/api";
import { statusMeta } from "@/lib/item-status";
import { cn } from "@/lib/utils";

/** The round status mark in front of a task: dashed, part-filled, or ticked. */
export function StatusIcon({
  status,
  className,
}: {
  status: ItemStatus;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden
      className={cn("size-4 shrink-0", statusMeta[status].text, className)}
    >
      {status === "todo" && (
        <circle
          cx="8"
          cy="8"
          r="6.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeDasharray="2.6 2.2"
        />
      )}
      {status === "in_progress" && (
        <>
          <circle
            cx="8"
            cy="8"
            r="6.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <path d="M8 8V1.5A6.5 6.5 0 0 1 14.5 8z" fill="currentColor" />
        </>
      )}
      {status === "done" && (
        <>
          <circle cx="8" cy="8" r="7.5" fill="currentColor" />
          <path
            d="m4.8 8.2 2.2 2.2 4.2-4.4"
            fill="none"
            stroke="white"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      )}
    </svg>
  );
}

/** The solid, upper-case status label that heads a column or a list group. */
export function StatusPill({
  status,
  className,
}: {
  status: ItemStatus;
  className?: string;
}) {
  const { label, Icon, pill } = statusMeta[status];
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-md pr-2 pl-1.5 text-xs font-semibold tracking-wide text-white uppercase",
        pill,
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5" strokeWidth={2.5} />
      {label}
    </span>
  );
}
