"use client";

import { House, LogOut, Plus, SquareKanban } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { BrandMark } from "@/components/brand-mark";
import { StatusIcon } from "@/components/status-icon";
import { TaskDialogsProvider, useTaskDialogs } from "@/components/task-dialogs";
import { itemStatuses } from "@/lib/api";
import { hostedLogoutUrl, signOut, useSession } from "@/lib/auth";
import { statusMeta } from "@/lib/item-status";
import { useItems } from "@/lib/use-items";
import { cn } from "@/lib/utils";

const destinations = [
  { href: "/home", label: "Home", Icon: House },
  { href: "/items", label: "Board", Icon: SquareKanban },
];

function useLogOut() {
  const router = useRouter();
  return () => {
    signOut();
    const logoutUrl = hostedLogoutUrl();
    if (logoutUrl) window.location.assign(logoutUrl);
    else router.replace("/");
  };
}

/** The signed-in workspace: grey backdrop, black icon rail, white sidebar and page. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <TaskDialogsProvider>
      <div className="flex h-dvh flex-col">
        <TopBar />
        <div className="flex min-h-0 flex-1 gap-2 px-2 pb-2">
          <Rail />
          <Sidebar />
          <main className="panel flex min-w-0 flex-1 flex-col overflow-hidden">
            {children}
          </main>
        </div>
      </div>
    </TaskDialogsProvider>
  );
}

function TopBar() {
  const pathname = usePathname() ?? "";
  const session = useSession();
  const logOut = useLogOut();

  return (
    <header className="flex h-13 shrink-0 items-center gap-3 px-3">
      <Link
        href="/home"
        className="flex items-center gap-2.5 rounded-lg py-1.5 pr-2.5 pl-1.5 text-[15px] font-semibold transition-colors hover:bg-black/5"
      >
        <BrandMark />
        Lanora
      </Link>

      {/* Below lg the sidebar is gone, so its two destinations move up here. */}
      <nav className="flex items-center gap-1 lg:hidden">
        {destinations.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            aria-current={pathname.startsWith(href) ? "page" : undefined}
            className={cn(
              "rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors",
              pathname.startsWith(href)
                ? "bg-black/5 text-foreground"
                : "text-muted-foreground hover:bg-black/5 hover:text-foreground",
            )}
          >
            {label}
          </Link>
        ))}
      </nav>

      {session && (
        <div className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          <span
            aria-hidden
            className="grid size-7 place-items-center rounded-full bg-accent-gradient text-xs font-semibold text-white"
          >
            {session.name.charAt(0).toUpperCase()}
          </span>
          <span className="hidden sm:inline">{session.email}</span>
          <button
            type="button"
            onClick={logOut}
            aria-label="Log out"
            className="grid size-8 cursor-pointer place-items-center rounded-lg transition-colors hover:bg-black/5 hover:text-foreground md:hidden"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      )}
    </header>
  );
}

function Rail() {
  const pathname = usePathname() ?? "";
  const logOut = useLogOut();
  const railItem =
    "grid size-10 cursor-pointer place-items-center rounded-xl text-rail-foreground transition hover:bg-rail-hover hover:text-white";

  return (
    <nav
      aria-label="Main"
      className="hidden w-15 shrink-0 flex-col items-center gap-2.5 rounded-2xl bg-rail py-3.5 md:flex"
    >
      {destinations.map(({ href, label, Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            title={label}
            aria-label={label}
            aria-current={active ? "page" : undefined}
            className={cn(
              railItem,
              active &&
                "bg-accent-gradient text-white shadow-[0_0_18px_rgb(102_71_240/0.75),0_0_4px_rgb(0_145_255/0.6)] hover:bg-accent-gradient",
            )}
          >
            <Icon className="size-5" />
          </Link>
        );
      })}
      <span className="flex-1" />
      <button
        type="button"
        title="Log out"
        aria-label="Log out"
        onClick={logOut}
        className={railItem}
      >
        <LogOut className="size-5" />
      </button>
    </nav>
  );
}

function Sidebar() {
  const pathname = usePathname() ?? "";
  const { openCreate } = useTaskDialogs();
  const { data } = useItems();

  const count = (status: string) =>
    data?.items.filter((item) => item.status === status).length ?? 0;
  const done = count("done");
  const percent = data?.total ? Math.round((done / data.total) * 100) : 0;

  const navItem =
    "flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[15px] text-foreground/85 transition-colors hover:bg-muted";

  return (
    <aside className="panel hidden w-61 shrink-0 flex-col gap-0.5 px-2.5 py-3.5 lg:flex">
      <div className="flex items-center justify-between pt-1 pr-0.5 pb-3 pl-2">
        <h2 className="text-xl font-bold">Workspace</h2>
        <button
          type="button"
          onClick={() => openCreate("todo")}
          className="flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 text-sm font-medium shadow-notion-xs transition-colors hover:bg-muted"
        >
          <Plus className="size-4" />
          Task
        </button>
      </div>

      {destinations.map(({ href, label, Icon }) => {
        const active = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              navItem,
              active && "bg-accent font-semibold text-foreground",
            )}
          >
            <Icon className="size-5" strokeWidth={1.8} />
            {label}
            {href === "/items" && data && (
              <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                {data.total}
              </span>
            )}
          </Link>
        );
      })}

      <p className="px-2.5 pt-5 pb-1.5 text-[13px] font-medium text-muted-foreground">
        Statuses
      </p>
      {itemStatuses.map((status) => (
        <Link
          key={status}
          href={`/items/list#status-${status}`}
          className={navItem}
        >
          <StatusIcon status={status} className="size-5" />
          {statusMeta[status].label}
          {data && (
            <span className="ml-auto text-xs text-muted-foreground tabular-nums">
              {count(status)}
            </span>
          )}
        </Link>
      ))}

      {data && data.total > 0 && (
        <div className="mt-auto border-t border-border/70 px-2.5 pt-3">
          <p className="text-xs text-muted-foreground">{percent}% done</p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-accent">
            <div
              className="h-full rounded-full bg-accent-gradient"
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>
      )}
    </aside>
  );
}
