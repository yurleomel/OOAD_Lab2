"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { useSession } from "@/lib/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 },
        },
      }),
  );

  // Cached tasks belong to whoever fetched them. When that person signs out -
  // or another one signs in, in this tab or another - drop them all, or the
  // next person would see someone else's board until the refetch.
  const sub = useSession()?.sub ?? null;
  const previousSub = useRef(sub);
  useEffect(() => {
    if (previousSub.current && previousSub.current !== sub) {
      queryClient.clear();
    }
    previousSub.current = sub;
  }, [sub, queryClient]);

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
