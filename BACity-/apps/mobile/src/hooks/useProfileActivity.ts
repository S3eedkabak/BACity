import { useEffect, useRef, useState } from "react";
import { apiRequest } from "../api/client";
import { getProfileHistory } from "../api/community";

/** A stale activity response cannot replace another tab or account's results. */
export function useProfileActivity(
  userId: string | undefined,
  tab: "contributions" | "reviews" | "collections",
) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [more, setMore] = useState(false);
  const historyRequest = useRef(0);
  async function load(append = false) {
    if (!userId) return;
    const request = ++historyRequest.current;
    setLoading(true);
    try {
      let result: any[];
      if (tab === "collections")
        result = (
          await apiRequest<any[]>("/community/collections", { auth: true })
        ).filter((item) => item.user_id === userId);
      else
        result = await getProfileHistory(
          userId,
          tab,
          append ? items.length : 0,
          12,
        );
      if (request !== historyRequest.current) return;
      setItems((current) => (append ? [...current, ...result] : result));
      setMore(tab !== "collections" && result.length === 12);
      setError("");
    } catch (e: any) {
      if (request === historyRequest.current) setError(e.message);
    } finally {
      if (request === historyRequest.current) setLoading(false);
    }
  }
  useEffect(() => {
    setItems([]);
    void load(false);
    return () => {
      historyRequest.current++;
    };
  }, [userId, tab]);
  return { items, loading, error, more, load };
}
