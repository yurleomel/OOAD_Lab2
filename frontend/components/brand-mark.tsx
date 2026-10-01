import { cn } from "@/lib/utils";

/** Lanora's own mark: an "L" on the warm brand gradient. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-7 place-items-center rounded-lg bg-brand-gradient font-heading text-sm font-extrabold text-white",
        className,
      )}
    >
      L
    </span>
  );
}
