import { useQuery } from "@tanstack/react-query";

import { api, type ItemList } from "@/lib/api";

/** The API's largest page. */
const PAGE_SIZE = 100;

/** Every task, paged through: the board, list, sidebar and dashboard all count the whole set. */
export async function fetchAllItems(): Promise<ItemList> {
  const first = await api.listItems({ limit: PAGE_SIZE, offset: 0 });
  const items = [...first.items];
  while (items.length < first.total) {
    const page = await api.listItems({
      limit: PAGE_SIZE,
      offset: items.length,
    });
    if (page.items.length === 0) break;
    items.push(...page.items);
  }
  return { items, total: first.total };
}

/** One shared cache entry; mutations update or invalidate ["items"]. */
export function useItems() {
  return useQuery({ queryKey: ["items"], queryFn: fetchAllItems });
}
