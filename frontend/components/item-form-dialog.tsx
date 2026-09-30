"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import { inputClass } from "@/components/auth-layout";
import { StatusIcon } from "@/components/status-icon";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  itemInputSchema,
  itemStatuses,
  type Item,
  type ItemInput,
  type ItemStatus,
} from "@/lib/api";
import { statusMeta } from "@/lib/item-status";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Present when editing, absent when creating. */
  item?: Item | null;
  /** Column a new card starts in. */
  defaultStatus?: ItemStatus;
  /** Shown only when editing; the caller owns the confirmation. */
  onDelete?: (item: Item) => void;
};

export function ItemFormDialog({
  open,
  onOpenChange,
  item,
  defaultStatus = "todo",
  onDelete,
}: Props) {
  const queryClient = useQueryClient();
  const isEditing = Boolean(item);

  const form = useForm<ItemInput>({
    resolver: zodResolver(itemInputSchema),
    defaultValues: { name: "", description: "", status: defaultStatus },
  });

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: item?.name ?? "",
      description: item?.description ?? "",
      status: item?.status ?? defaultStatus,
    });
  }, [open, item, defaultStatus, form]);

  const mutation = useMutation({
    mutationFn: (values: ItemInput) =>
      item ? api.updateItem(item.id, values) : api.createItem(values),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["items"] });
      toast.success(isEditing ? "Task updated" : "Task created");
      onOpenChange(false);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-5 rounded-2xl p-6 sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-lg font-bold">
            {isEditing ? "Edit task" : "New task"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Change the details or move it to another status."
              : "Add a task to your board."}
          </DialogDescription>
        </DialogHeader>

        <form
          className="grid gap-4"
          onSubmit={form.handleSubmit((values) => mutation.mutate(values))}
        >
          <Field data-invalid={Boolean(form.formState.errors.name)}>
            <FieldLabel htmlFor="name">Title</FieldLabel>
            <Input
              id="name"
              autoComplete="off"
              className={inputClass}
              {...form.register("name")}
            />
            {form.formState.errors.name && (
              <FieldError errors={[form.formState.errors.name]} />
            )}
          </Field>

          <Field>
            <FieldLabel id="status-label">Status</FieldLabel>
            <Controller
              control={form.control}
              name="status"
              render={({ field }) => (
                <div
                  role="radiogroup"
                  aria-labelledby="status-label"
                  className="flex flex-wrap gap-2"
                >
                  {itemStatuses.map((status) => {
                    const meta = statusMeta[status];
                    const selected = field.value === status;
                    return (
                      <button
                        key={status}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        onClick={() => field.onChange(status)}
                        className={cn(
                          "inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg border px-3 text-sm font-medium transition",
                          selected
                            ? "border-primary/50 bg-primary/5 text-foreground ring-2 ring-primary/15"
                            : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
                        )}
                      >
                        <StatusIcon status={status} />
                        {meta.label}
                      </button>
                    );
                  })}
                </div>
              )}
            />
          </Field>

          <Field data-invalid={Boolean(form.formState.errors.description)}>
            <FieldLabel htmlFor="description">Description</FieldLabel>
            <Textarea
              id="description"
              rows={4}
              placeholder="Add more detail..."
              className="rounded-lg border-input bg-card px-3 focus-visible:bg-card"
              {...form.register("description")}
            />
            {form.formState.errors.description && (
              <FieldError errors={[form.formState.errors.description]} />
            )}
          </Field>

          <DialogFooter className="-mx-6 -mb-6 rounded-b-2xl px-6 sm:justify-between">
            {item && onDelete ? (
              <Button
                type="button"
                size="lg"
                variant="ghost"
                className="text-destructive hover:text-destructive"
                onClick={() => onDelete(item)}
                disabled={mutation.isPending}
              >
                <Trash2 data-icon="inline-start" className="size-4" />
                Delete
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button
                type="button"
                size="lg"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" size="lg" disabled={mutation.isPending}>
                {mutation.isPending
                  ? "Saving..."
                  : isEditing
                    ? "Save changes"
                    : "Create"}
              </Button>
            </div>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
