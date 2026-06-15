"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, CalendarEvent } from "@/lib/api/client";

function urgency(days: number) {
  if (days < 0) return { cls: "bg-red-100 text-red-700 border-red-200", label: "Overdue" };
  if (days <= 1) return { cls: "bg-red-100 text-red-700 border-red-200", label: "Due today/tomorrow" };
  if (days <= 7) return { cls: "bg-amber-100 text-amber-700 border-amber-200", label: `${days} days left` };
  return { cls: "bg-slate-100 text-slate-600 border-slate-200", label: `${days} days left` };
}

function groupByMonth(events: CalendarEvent[]) {
  const groups: Record<string, CalendarEvent[]> = {};
  for (const e of events) {
    const key = new Date(e.deadline).toLocaleDateString(undefined, {
      month: "long",
      year: "numeric",
    });
    (groups[key] ||= []).push(e);
  }
  return groups;
}

export default function CalendarPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["calendar"],
    queryFn: async () => (await api.getCalendar(120)).data,
  });

  const groups = data ? groupByMonth(data) : {};

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Bid Calendar</h1>
        <p className="mt-1 text-slate-500">
          Every upcoming submission deadline across your pipeline and analysed tenders.
        </p>
      </div>

      {isLoading && <p className="text-slate-500">Loading deadlines…</p>}

      {data && data.length === 0 && (
        <div className="p-12 bg-white rounded-xl border text-center text-slate-500">
          No upcoming deadlines in the next 120 days.
        </div>
      )}

      {Object.entries(groups).map(([month, events]) => (
        <div key={month} className="mb-8">
          <h2 className="text-sm font-semibold text-slate-500 uppercase mb-3">{month}</h2>
          <div className="space-y-2">
            {events.map((e, i) => {
              const u = urgency(e.days_remaining);
              const href = e.bid_id
                ? `/dashboard/bids/${e.bid_id}`
                : e.tender_id
                ? `/dashboard/tenders/${e.tender_id}`
                : "#";
              return (
                <Link
                  key={i}
                  href={href}
                  className="flex items-center justify-between gap-4 p-4 bg-white border rounded-xl hover:border-brand-300"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-slate-900 truncate">{e.title}</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {new Date(e.deadline).toLocaleDateString(undefined, {
                        weekday: "short",
                        day: "numeric",
                        month: "short",
                      })}
                      {e.stage ? ` · ${e.stage}` : " · not in pipeline"}
                    </p>
                  </div>
                  <span className={`shrink-0 px-2.5 py-1 rounded-full text-xs font-medium border ${u.cls}`}>
                    {u.label}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
