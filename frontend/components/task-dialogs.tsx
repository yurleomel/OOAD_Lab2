"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useMemo, useState } from "react";
import { toast } from "sonner";

import { ItemFormDialog } from "@/components/item-form-dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { api, type Item, type ItemStatus } from "@/lib/api";

type TaskDialogs = {
  /** Open the "New task" dialog, starting in the given status. */
  openCreate: (status?: ItemStatus) => void;
  openEdit: (item: Item) => void;
};

const TaskDialogsContext = createContext<TaskDialogs | null>(null);

/**
 * One create/edit dialog and one delete confirmation for the whole signed-in
 * area, so the sidebar, the board, the list and the dashboard all open the same
 * ones.
 */
export function TaskDialogsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Item | null>(null);
  const [newStatus, setNewStatus] = useState<ItemStatus>("todo");
  const [pendingDelete, setPendingDelete] = useState<Item | null>(null);

  const remove = useMutation({
    mutationFn: (item: Item) => api.deleteItem(item.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["items"] });
      toast.success("Task deleted");
      setFormOpen(false);
    },
    onError: (error: Error) => toast.error(error.message),
    onSettled: () => setPendingDelete(null),
  });

  const value = useMemo<TaskDialogs>(
    () => ({
      openCreate: (status = "todo") => {
        setEditing(null);
        setNewStatus(status);
        setFormOpen(true);
      },
      openEdit: (item) => {
        setEditing(item);
        setFormOpen(true);
      },
    }),
    [],
  );

  return (
    <TaskDialogsContext.Provider value={value}>
      {children}

      <ItemFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        item={editing}
        defaultStatus={newStatus}
        onDelete={setPendingDelete}
      />

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this task?</AlertDialogTitle>
            <AlertDialogDescription>
              &quot;{pendingDelete?.name}&quot; will be removed permanently.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => pendingDelete && remove.mutate(pendingDelete)}
              disabled={remove.isPending}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </TaskDialogsContext.Provider>
  );
}

export function useTaskDialogs(): TaskDialogs {
  const dialogs = useContext(TaskDialogsContext);
  if (!dialogs) {
    throw new Error("useTaskDialogs must be used inside TaskDialogsProvider");
  }
  return dialogs;
}
