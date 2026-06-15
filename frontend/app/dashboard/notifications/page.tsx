"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, AppNotification } from "@/lib/api/client";

const TYPE_ICON: Record<string, string> = {
  new_high_match: "🎯",
  deadline_approaching: "⏰",
  bid_assigned: "👤",
  stage_changed: "🔀",
};

function localPath(link: string | null) {
  if (!link) return null;
  try {
    return new URL(link).pathname;
  } catch {
    return link.startsWith("/") ? link : null;
  }
}

export default function NotificationsPage() {
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => (await api.listNotifications(false)).data,
  });

  const markRead = useMutation({
    mutationFn: async (id: string) => (await api.markNotificationRead(id)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const markAll = useMutation({
    mutationFn: async () => (await api.markAllNotificationsRead()).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Alerts</h1>
          <p className="mt-1 text-slate-500">
            New high-match tenders, approaching deadlines, and bid assignments.
          </p>
        </div>
        <button
          onClick={() => markAll.mutate()}
          className="text-sm text-brand-600 font-medium hover:underline"
        >
          Mark all read
        </button>
      </div>

      {isLoading && <p className="text-slate-500">Loading…</p>}

      {data && data.length === 0 && (
        <div className="p-12 bg-white rounded-xl border text-center text-slate-500">
          No alerts yet.
        </div>
      )}

      <div className="space-y-2">
        {data?.map((n: AppNotification) => {
          const path = localPath(n.link);
          const inner = (
            <div
              className={`p-4 border rounded-xl flex items-start gap-3 ${
                n.is_read ? "bg-white" : "bg-brand-50/40 border-brand-200"
              }`}
            >
              <span className="text-lg">{TYPE_ICON[n.type] || "🔔"}</span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-900">{n.title}</p>
                {n.body && <p className="text-sm text-slate-500 mt-0.5">{n.body}</p>}
                <p className="text-xs text-slate-400 mt-1">
                  {new Date(n.created_at).toLocaleString()}
                </p>
              </div>
              {!n.is_read && (
                <button
                  onClick={(ev) => {
                    ev.preventDefault();
                    markRead.mutate(n.id);
                  }}
                  className="shrink-0 text-xs text-brand-600 hover:underline"
                >
                  Mark read
                </button>
              )}
            </div>
          );
          return path ? (
            <Link key={n.id} href={path} onClick={() => !n.is_read && markRead.mutate(n.id)}>
              {inner}
            </Link>
          ) : (
            <div key={n.id}>{inner}</div>
          );
        })}
      </div>
    </div>
  );
}
