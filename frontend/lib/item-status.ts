import { Check, CircleDashed, Clock, type LucideIcon } from "lucide-react";

import type { ItemStatus } from "@/lib/api";

/** Labels, pill icons and colour classes, in board column order. */
export const statusMeta: Record<
  ItemStatus,
  {
    label: string;
    Icon: LucideIcon;
    /** Solid fill behind the white pill text. */
    pill: string;
    /** Soft wash for the board column. */
    column: string;
    /** Chart and legend marks. */
    mark: string;
    text: string;
  }
> = {
  todo: {
    label: "To do",
    Icon: CircleDashed,
    pill: "bg-status-todo",
    column: "bg-status-todo-soft",
    mark: "bg-status-todo",
    text: "text-status-todo",
  },
  in_progress: {
    label: "In progress",
    Icon: Clock,
    pill: "bg-status-progress",
    column: "bg-status-progress-soft",
    mark: "bg-status-progress",
    text: "text-status-progress",
  },
  done: {
    label: "Done",
    Icon: Check,
    pill: "bg-status-done",
    column: "bg-status-done-soft",
    mark: "bg-status-done",
    text: "text-status-done",
  },
};
