import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "../api/client";
import type { EventCategory, EventListResponse } from "../types/event";

type Domain = "events" | "places" | "people" | "organizers";
/** Discovery owns cancellation and result identity independently of screen composition. */
export function useDiscoveryResults({
  domain,
  term,
  category,
  freeOnly,
  token,
}: {
  domain: Domain;
  term: string;
  category: EventCategory | null;
  freeOnly: boolean;
  token: string | null;
}) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const request = useRef(0);
  const abort = useRef<AbortController | null>(null);
  const load = useCallback(
    async (append = false) => {
      const id = ++request.current;
      abort.current?.abort();
      const controller = new AbortController();
      abort.current = controller;
      const signal = controller.signal;
      const offset = append ? items.length : 0;
      setLoading(true);
      setError("");
      try {
        let result: any[];
        if (domain === "events") {
          if (term)
            result = await apiRequest<any[]>("/events/search", {
              signal,
              params: { q: term, limit: 50 },
            });
          else
            result = (
              await apiRequest<EventListResponse>("/events", {
                signal,
                params: {
                  category: category || undefined,
                  free_only: freeOnly || undefined,
                  offset,
                  limit: 20,
                },
              })
            ).items;
        } else if (domain === "places")
          result = await apiRequest<any[]>("/community/places", {
            signal,
            params: { q: term, offset },
          });
        else if (domain === "people")
          result = token
            ? await apiRequest<any[]>("/community/people", {
                auth: true,
                signal,
                params: { q: term, offset, limit: 20 },
              })
            : [];
        else
          result = await apiRequest<any[]>("/community/organizations", {
            signal,
            params: { q: term },
          });
        if (id === request.current) {
          setItems((current) => (append ? [...current, ...result] : result));
          setMore(
            ((domain === "events" && !term) || domain === "people") &&
              result.length === 20,
          );
        }
      } catch (e: any) {
        if (id === request.current) setError(e.message);
      } finally {
        if (id === request.current) setLoading(false);
      }
    },
    [category, freeOnly, domain, items.length, term, token],
  );
  useEffect(() => {
    setItems([]);
    void load(false);
  }, [domain, term, category, freeOnly, token]);
  useEffect(
    () => () => {
      ++request.current;
      abort.current?.abort();
    },
    [],
  );

  return { items, loading, error, more, load };
}
