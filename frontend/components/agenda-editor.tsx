"use client";

import { ClipboardPaste, LoaderCircle, Plus, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  useFieldArray,
  useWatch,
  type FieldPath,
  type UseFormReturn,
} from "react-hook-form";
import { z } from "zod";

import { inputClass } from "@/components/auth-layout";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  itemInputSchema,
  type Agenda,
  type AiSuggestion,
  type ParsedAgenda,
} from "@/lib/api";
import { MAX_PASTE_CHARS, ParseError, parseAgenda } from "@/lib/parser";
import { cn } from "@/lib/utils";

/* --- the form's shape: strings, as the inputs hold them --- */

const wholeNumber = (max: number) =>
  z
    .string()
    .refine(
      (v) =>
        v.trim() === "" || (/^\d+$/.test(v.trim()) && +v >= 1 && +v <= max),
      `A whole number from 1 to ${max}`,
    );
const required = (what: string, max: number) =>
  z
    .string()
    .max(max, `${what} is too long`)
    .refine((v) => v.trim() !== "", `${what} is required`);

export const agendaFormSchema = z.object({
  starts_at: z.string(), // datetime-local, "" for none
  duration_minutes: wholeNumber(600),
  items: z
    .array(
      z.object({
        topic: required("Topic", 300),
        owner: z.string().max(120, "Too long"),
        minutes: wholeNumber(480),
      }),
    )
    .max(50, "At most 50 topics"),
  action_items: z
    .array(
      z.object({
        task: required("Task", 300),
        owner: z.string().max(120, "Too long"),
        due: z.string(), // date input, "" for none
      }),
    )
    .max(50, "At most 50 action items"),
});

/** The task dialog's whole form: the task, and its agenda when it has one. */
export const taskFormSchema = itemInputSchema.extend({
  agenda: agendaFormSchema,
});

export type AgendaForm = z.infer<typeof agendaFormSchema>;
export type TaskForm = z.infer<typeof taskFormSchema>;

export const emptyTopic = () => ({ topic: "", owner: "", minutes: "" });
export const emptyActionItem = () => ({ task: "", owner: "", due: "" });
export const emptyAgendaForm = (): AgendaForm => ({
  starts_at: "",
  duration_minutes: "",
  items: [],
  action_items: [],
});

const pad = (n: number) => String(n).padStart(2, "0");

/** ISO 8601 (any offset) to the user's wall clock, as a datetime-local input wants. */
function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** The wall clock back to ISO 8601, with the offset the user is on at that time. */
function fromLocalInput(local: string): string | null {
  if (!local) return null;
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return null;
  const offset = -d.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const abs = Math.abs(offset);
  return `${toLocalInput(d.toISOString())}:00${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

const text = (v: string | null) => v ?? "";
const number = (v: number | null) => (v === null ? "" : String(v));
const orNull = (v: string) => (v.trim() === "" ? null : v.trim());
const intOrNull = (v: string) => (v.trim() === "" ? null : Number(v));

export function agendaToForm(agenda: Agenda | ParsedAgenda): AgendaForm {
  return {
    starts_at: toLocalInput(agenda.starts_at),
    duration_minutes: number(agenda.duration_minutes),
    items: agenda.items.map((i) => ({
      topic: i.topic,
      owner: text(i.owner),
      minutes: number(i.minutes),
    })),
    action_items: agenda.action_items.map((a) => ({
      task: a.task,
      owner: text(a.owner),
      due: text(a.due),
    })),
  };
}

export function formToAgenda(form: AgendaForm): Agenda {
  return {
    starts_at: fromLocalInput(form.starts_at),
    duration_minutes: intOrNull(form.duration_minutes),
    items: form.items.map((i) => ({
      topic: i.topic.trim(),
      owner: orNull(i.owner),
      minutes: intOrNull(i.minutes),
    })),
    action_items: form.action_items.map((a) => ({
      task: a.task.trim(),
      owner: orNull(a.owner),
      due: orNull(a.due),
    })),
  };
}

/* --- "suggested" marks --- */

/** A field the model filled and the user has not changed yet. */
export function useSuggested(
  form: UseFormReturn<TaskForm>,
  suggestion: AiSuggestion | null,
) {
  // Subscribes to dirtiness and values, so marks drop as soon as a field changes.
  const { dirtyFields } = form.formState;
  const values = useWatch({ control: form.control });
  void dirtyFields;
  void values;
  return (path: FieldPath<TaskForm>) => {
    if (!suggestion) return false;
    const value = form.getValues(path);
    return (
      typeof value === "string" &&
      value.trim() !== "" &&
      !form.getFieldState(path, form.formState).isDirty
    );
  };
}

export function SuggestedBadge() {
  return (
    <Badge variant="info" className="ml-auto gap-1 font-normal">
      <Sparkles data-icon="inline-start" />
      suggested
    </Badge>
  );
}

/** An input inside a row, marked when the model filled it. */
function RowInput({
  suggested,
  className,
  wide,
  ...props
}: React.ComponentProps<typeof Input> & {
  suggested: boolean;
  /** The row's main field: a line of its own on a phone. */
  wide?: boolean;
}) {
  return (
    <div className={cn("relative min-w-0", wide && "max-sm:col-span-3")}>
      <Input
        {...props}
        data-suggested={suggested || undefined}
        className={cn(
          inputClass,
          "h-9 w-full",
          suggested && "border-tint-blue-foreground/30 bg-tint-blue/40 pr-7",
          className,
        )}
      />
      {suggested && (
        <Sparkles
          aria-label="suggested"
          className="pointer-events-none absolute top-1/2 right-2 size-3.5 -translate-y-1/2 text-tint-blue-foreground"
        />
      )}
    </div>
  );
}

/* --- the paste box --- */

type PasteProps = {
  onParsed: (suggestion: AiSuggestion) => void;
  onClose: () => void;
  /** "Type it by hand": the way out of every error. */
  onManual: () => void;
};

export function AgendaPaste({ onParsed, onClose, onManual }: PasteProps) {
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<ParseError | null>(null);
  const controller = useRef<AbortController | null>(null);

  // A closed dialog must not leave a paid request running.
  useEffect(() => () => controller.current?.abort(), []);

  useEffect(() => {
    if (!pending) return;
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      500,
    );
    return () => clearInterval(timer);
  }, [pending]);

  const tooLong = value.length > MAX_PASTE_CHARS;

  async function parse() {
    controller.current = new AbortController();
    setPending(true);
    setElapsed(0);
    setError(null);
    try {
      onParsed(await parseAgenda(value, controller.current.signal));
    } catch (e) {
      const failure =
        e instanceof ParseError ? e : new ParseError("failed", String(e));
      if (failure.kind !== "cancelled") setError(failure);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid gap-3 rounded-xl border border-dashed border-border bg-muted/40 p-3">
      <Field data-invalid={tooLong}>
        <FieldLabel htmlFor="paste-agenda">Paste an agenda</FieldLabel>
        <Textarea
          id="paste-agenda"
          rows={5}
          value={value}
          disabled={pending}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Paste an email, a chat message or notes: “Mon 10:00, pricing sync, 45 min. 1) new Pro plans — Olena, 15 min…”"
          className="rounded-lg border-input bg-card px-3 focus-visible:bg-card"
        />
        <p
          className={cn(
            "text-xs text-muted-foreground tabular-nums",
            tooLong && "text-destructive",
          )}
        >
          {value.length.toLocaleString("en")} /{" "}
          {MAX_PASTE_CHARS.toLocaleString("en")} characters
        </p>
      </Field>

      {error && (
        <Alert variant="destructive" role="alert">
          <AlertDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{error.message}</span>
            <button
              type="button"
              onClick={onManual}
              className="cursor-pointer font-medium underline underline-offset-2 hover:no-underline"
            >
              Type it by hand
            </button>
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-center justify-end gap-2">
        {pending ? (
          <>
            <span
              role="status"
              className="mr-auto flex items-center gap-2 text-sm text-muted-foreground"
            >
              <LoaderCircle className="size-4 animate-spin" aria-hidden />
              Reading the agenda… {elapsed > 0 && `${elapsed} s`}
            </span>
            <Button
              type="button"
              variant="outline"
              aria-label="Cancel parsing"
              onClick={() => controller.current?.abort()}
            >
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button type="button" variant="ghost" onClick={onClose}>
              Close
            </Button>
            <Button
              type="button"
              onClick={parse}
              disabled={value.trim() === "" || tooLong}
            >
              <Sparkles data-icon="inline-start" className="size-4" />
              Parse
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

/* --- the agenda fields --- */

type FieldsProps = {
  form: UseFormReturn<TaskForm>;
  suggestion: AiSuggestion | null;
  isSuggested: (path: FieldPath<TaskForm>) => boolean;
  onRemove: () => void;
  /** Present when the parser is deployed. */
  onPasteAgain?: () => void;
};

function modelName(model: string): string {
  const known: Record<string, string> = {
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": "Claude Haiku 4.5",
    "us.anthropic.claude-sonnet-4-6": "Claude Sonnet 4.6",
    "anthropic.claude-opus-5-5": "Claude Opus 5.5",
    "anthropic.claude-haiku-5-5": "Claude Haiku 5.5",
  };
  return known[model] ?? model;
}

export function AgendaFields({
  form,
  suggestion,
  isSuggested,
  onRemove,
  onPasteAgain,
}: FieldsProps) {
  const topics = useFieldArray({ control: form.control, name: "agenda.items" });
  const actions = useFieldArray({
    control: form.control,
    name: "agenda.action_items",
  });
  const errors = form.formState.errors.agenda;

  return (
    <section aria-labelledby="agenda-heading" className="grid gap-4">
      <div className="flex items-center gap-2">
        <h3 id="agenda-heading" className="text-sm font-semibold">
          Agenda
        </h3>
        <div className="ml-auto flex gap-1">
          {onPasteAgain && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={onPasteAgain}
            >
              <ClipboardPaste data-icon="inline-start" className="size-4" />
              Paste again
            </Button>
          )}
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="text-muted-foreground"
            onClick={onRemove}
          >
            Remove agenda
          </Button>
        </div>
      </div>

      {suggestion && (
        <div className="rounded-lg bg-tint-blue/50 px-3 py-2 text-sm text-tint-blue-foreground">
          <p className="flex items-start gap-2">
            <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              Suggested by {modelName(suggestion.model)} (
              {suggestion.prompt_version}). Check the marked fields, correct
              what is wrong, then save. Nothing is saved until you do.
            </span>
          </p>
          <details className="mt-1 ml-6">
            <summary className="cursor-pointer text-xs font-medium hover:underline">
              What the model returned
            </summary>
            <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-card p-2 font-mono text-[11px] leading-relaxed text-foreground">
              {JSON.stringify(suggestion.agenda, null, 2)}
            </pre>
          </details>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="agenda-starts-at">
            Starts at
            {isSuggested("agenda.starts_at") && <SuggestedBadge />}
          </FieldLabel>
          <Input
            id="agenda-starts-at"
            type="datetime-local"
            className={inputClass}
            {...form.register("agenda.starts_at")}
          />
        </Field>
        <Field data-invalid={Boolean(errors?.duration_minutes)}>
          <FieldLabel htmlFor="agenda-duration">
            Duration, minutes
            {isSuggested("agenda.duration_minutes") && <SuggestedBadge />}
          </FieldLabel>
          <Input
            id="agenda-duration"
            inputMode="numeric"
            className={inputClass}
            {...form.register("agenda.duration_minutes")}
          />
          {errors?.duration_minutes && (
            <FieldError errors={[errors.duration_minutes]} />
          )}
        </Field>
      </div>

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Topics</legend>
        {topics.fields.length === 0 && (
          <p className="text-sm text-muted-foreground">No topics yet.</p>
        )}
        {topics.fields.map((row, index) => {
          const rowErrors = errors?.items?.[index];
          return (
            <div key={row.id} className="grid gap-1">
              <div className="grid grid-cols-[1fr_5rem_auto] items-center gap-2 sm:grid-cols-[minmax(0,1fr)_9rem_5rem_auto]">
                <RowInput
                  aria-label={`Topic ${index + 1}`}
                  aria-invalid={Boolean(rowErrors?.topic)}
                  placeholder="Topic"
                  wide
                  suggested={isSuggested(`agenda.items.${index}.topic`)}
                  {...form.register(`agenda.items.${index}.topic`)}
                />
                <RowInput
                  aria-label={`Owner of topic ${index + 1}`}
                  placeholder="Owner"
                  suggested={isSuggested(`agenda.items.${index}.owner`)}
                  {...form.register(`agenda.items.${index}.owner`)}
                />
                <RowInput
                  aria-label={`Minutes for topic ${index + 1}`}
                  aria-invalid={Boolean(rowErrors?.minutes)}
                  placeholder="Min"
                  inputMode="numeric"
                  suggested={isSuggested(`agenda.items.${index}.minutes`)}
                  {...form.register(`agenda.items.${index}.minutes`)}
                />
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove topic ${index + 1}`}
                  onClick={() => topics.remove(index)}
                >
                  <X className="size-4" />
                </Button>
              </div>
              {(rowErrors?.topic || rowErrors?.minutes) && (
                <FieldError
                  errors={[rowErrors.topic, rowErrors.minutes].filter(
                    (e) => e !== undefined,
                  )}
                />
              )}
            </div>
          );
        })}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="w-fit text-muted-foreground"
          onClick={() => topics.append(emptyTopic())}
        >
          <Plus data-icon="inline-start" className="size-4" />
          Add topic
        </Button>
      </fieldset>

      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Action items</legend>
        {actions.fields.map((row, index) => {
          const rowErrors = errors?.action_items?.[index];
          return (
            <div key={row.id} className="grid gap-1">
              <div className="grid grid-cols-[1fr_9.5rem_auto] items-center gap-2 sm:grid-cols-[minmax(0,1fr)_9rem_9.5rem_auto]">
                <RowInput
                  aria-label={`Action item ${index + 1}`}
                  aria-invalid={Boolean(rowErrors?.task)}
                  placeholder="Task"
                  wide
                  suggested={isSuggested(`agenda.action_items.${index}.task`)}
                  {...form.register(`agenda.action_items.${index}.task`)}
                />
                <RowInput
                  aria-label={`Owner of action item ${index + 1}`}
                  placeholder="Owner"
                  suggested={isSuggested(`agenda.action_items.${index}.owner`)}
                  {...form.register(`agenda.action_items.${index}.owner`)}
                />
                <RowInput
                  aria-label={`Due date of action item ${index + 1}`}
                  type="date"
                  suggested={isSuggested(`agenda.action_items.${index}.due`)}
                  {...form.register(`agenda.action_items.${index}.due`)}
                />
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove action item ${index + 1}`}
                  onClick={() => actions.remove(index)}
                >
                  <X className="size-4" />
                </Button>
              </div>
              {rowErrors?.task && <FieldError errors={[rowErrors.task]} />}
            </div>
          );
        })}
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="w-fit text-muted-foreground"
          onClick={() => actions.append(emptyActionItem())}
        >
          <Plus data-icon="inline-start" className="size-4" />
          Add action item
        </Button>
      </fieldset>
    </section>
  );
}
