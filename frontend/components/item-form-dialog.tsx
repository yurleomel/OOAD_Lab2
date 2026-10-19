"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ClipboardPaste, ListPlus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";

import {
  AgendaFields,
  AgendaPaste,
  agendaToForm,
  emptyAgendaForm,
  emptyTopic,
  formToAgenda,
  SuggestedBadge,
  taskFormSchema,
  useSuggested,
  type TaskForm,
} from "@/components/agenda-editor";
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
  itemStatuses,
  type AiSuggestion,
  type Item,
  type ItemPayload,
  type ItemStatus,
} from "@/lib/api";
import { statusMeta } from "@/lib/item-status";
import { parserUrl } from "@/lib/parser";
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

  const form = useForm<TaskForm>({
    resolver: zodResolver(taskFormSchema),
    defaultValues: {
      name: "",
      description: "",
      status: defaultStatus,
      agenda: emptyAgendaForm(),
    },
  });

  // The agenda section: off, a paste box, or the fields. The suggestion is the
  // parser's last answer, until the agenda is removed or the dialog closes.
  const [hasAgenda, setHasAgenda] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [suggestion, setSuggestion] = useState<AiSuggestion | null>(null);
  const [nameSuggested, setNameSuggested] = useState(false);
  const isSuggested = useSuggested(form, suggestion);
  const canPaste = parserUrl() !== "";

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: item?.name ?? "",
      description: item?.description ?? "",
      status: item?.status ?? defaultStatus,
      agenda: item?.agenda ? agendaToForm(item.agenda) : emptyAgendaForm(),
    });
  }, [open, item, defaultStatus, form]);

  // Each opening starts the agenda section afresh - adjusted while rendering,
  // as React recommends for state that follows a prop.
  const session = open ? (item?.id ?? "new") : null;
  // null first, so a dialog that mounts already open is set up too.
  const [lastSession, setLastSession] = useState<string | null>(null);
  if (session !== lastSession) {
    setLastSession(session);
    setHasAgenda(Boolean(item?.agenda));
    setPasting(false);
    setSuggestion(null);
    setNameSuggested(false);
  }

  function applySuggestion(result: AiSuggestion) {
    const current = form.getValues();
    // The title fills an empty name only: a name the user typed wins.
    const title = result.agenda.title?.trim().slice(0, 120) ?? "";
    const takeTitle = current.name.trim() === "" && title !== "";
    // A reset makes the suggestion the baseline, so a field counts as checked
    // ("suggested" mark gone) as soon as the user changes it.
    form.reset({
      ...current,
      name: takeTitle ? title : current.name,
      agenda: agendaToForm(result.agenda),
    });
    setNameSuggested(takeTitle);
    setSuggestion(result);
    setHasAgenda(true);
    setPasting(false);
  }

  function typeByHand() {
    setPasting(false);
    setHasAgenda(true);
    if (form.getValues("agenda.items").length === 0) {
      form.setValue("agenda.items", [emptyTopic()]);
    }
  }

  function removeAgenda() {
    form.setValue("agenda", emptyAgendaForm());
    setHasAgenda(false);
    setSuggestion(null);
    setNameSuggested(false);
  }

  const mutation = useMutation({
    mutationFn: ({ agenda, ...task }: TaskForm) => {
      const payload: ItemPayload = task;
      // The agenda only when there is one, or to remove the one that was there.
      if (hasAgenda) payload.agenda = formToAgenda(agenda);
      else if (item?.agenda) payload.agenda = null;
      if (hasAgenda && suggestion) payload.ai_suggestion = suggestion;
      return item ? api.updateItem(item.id, payload) : api.createItem(payload);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["items"] });
      toast.success(isEditing ? "Task updated" : "Task created");
      onOpenChange(false);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "max-h-[92dvh] gap-5 overflow-y-auto rounded-2xl p-6 sm:max-w-lg",
          (hasAgenda || pasting) && "sm:max-w-2xl",
        )}
      >
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
            <FieldLabel htmlFor="name">
              Title
              {nameSuggested && isSuggested("name") && <SuggestedBadge />}
            </FieldLabel>
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

          {pasting ? (
            <AgendaPaste
              onParsed={applySuggestion}
              onClose={() => setPasting(false)}
              onManual={typeByHand}
            />
          ) : hasAgenda ? (
            <AgendaFields
              form={form}
              suggestion={suggestion}
              isSuggested={isSuggested}
              onRemove={removeAgenda}
              onPasteAgain={canPaste ? () => setPasting(true) : undefined}
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              {canPaste && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setPasting(true)}
                >
                  <ClipboardPaste data-icon="inline-start" className="size-4" />
                  Paste an agenda
                </Button>
              )}
              <Button type="button" variant="ghost" onClick={typeByHand}>
                <ListPlus data-icon="inline-start" className="size-4" />
                Add agenda
              </Button>
            </div>
          )}

          <DialogFooter className="sticky -bottom-6 z-10 -mx-6 -mb-6 rounded-b-2xl px-6 sm:justify-between">
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
