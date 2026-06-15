"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, Bid, BidStage } from "@/lib/api/client";

const COLUMNS: { stage: BidStage; label: string }[] = [
  { stage: "identified", label: "Identified" },
  { stage: "qualifying", label: "Qualifying" },
  { stage: "go_no_go", label: "Go / No-Go" },
  { stage: "preparing", label: "Preparing" },
  { stage: "submitted", label: "Submitted" },
];

const ALL_STAGES: BidStage[] = [
  "identified", "qualifying", "go_no_go", "preparing",
  "submitted", "won", "lost", "dropped",
];

const STAGE_LABEL: Record<BidStage, string> = {
  identified: "Identified", qualifying: "Qualifying", go_no_go: "Go / No-Go",
  preparing: "Preparing", submitted: "Submitted", won: "Won", lost: "Lost",
  dropped: "Dropped",
};

function formatValue(v: number | null) {
  if (!v) return null;
  if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(2)} Cr`;
  if (v >= 100_000) return `₹${(v / 100_000).toFixed(1)} L`;
  return `₹${v.toLocaleString()}`;
}

function deadlineBadge(deadline: string | null) {
  if (!deadline) return null;
  const days = Math.ceil(
    (new Date(deadline).getTime() - Date.now()) / 86_400_000
  );
  const cls =
    days <= 1 ? "bg-red-100 text-red-700"
    : days <= 7 ? "bg-amber-100 text-amber-700"
    : "bg-slate-100 text-slate-600";
  const label = days < 0 ? "overdue" : days === 0 ? "today" : `${days}d`;
  return <span className={`px-1.5 py-0.5 rounded text-[11px] font-medium ${cls}`}>⏰ {label}</span>;
}

function BidCard({ bid }: { bid: Bid }) {
  const qc = useQueryClient();
  const move = useMutation({
    mutationFn: async (stage: BidStage) =>
      (await api.updateBidStage(bid.id, stage)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bids"] }),
  });

  return (
    <div className="p-3 bg-white border rounded-lg shadow-sm space-y-2">
      <Link
        href={`/dashboard/bids/${bid.id}`}
        className="block text-sm font-medium text-slate-900 hover:text-brand-600 line-clamp-2"
      >
        {bid.title}
      </Link>
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
        {formatValue(bid.tender_value) && <span>{formatValue(bid.tender_value)}</span>}
        {deadlineBadge(bid.bid_deadline)}
        {bid.win_probability != null && (
          <span className="px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 text-[11px] font-medium">
            {Math.round(bid.win_probability * 100)}% win
          </span>
        )}
      </div>
      <select
        value={bid.stage}
        onChange={(e) => move.mutate(e.target.value as BidStage)}
        className="w-full text-xs border rounded px-2 py-1 text-slate-600 bg-slate-50"
      >
        {ALL_STAGES.map((s) => (
          <option key={s} value={s}>{STAGE_LABEL[s]}</option>
        ))}
      </select>
    </div>
  );
}

export default function BidsBoard() {
  const { data, isLoading } = useQuery({
    queryKey: ["bids"],
    queryFn: async () => (await api.listBids()).data,
  });

  const byStage = (stage: BidStage) => data?.filter((b) => b.stage === stage) ?? [];
  const decided = data?.filter((b) =>
    ["won", "lost", "dropped"].includes(b.stage)
  ) ?? [];

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Bid Pipeline</h1>
        <p className="mt-1 text-slate-500">
          Track every pursuit from identification to win/loss. Move cards through stages.
        </p>
      </div>

      {isLoading && <p className="text-slate-500">Loading pipeline…</p>}

      {data && data.length === 0 && (
        <div className="p-12 bg-white rounded-xl border text-center text-slate-500">
          No bids yet. Add one from{" "}
          <Link href="/dashboard/monitoring" className="text-brand-600 hover:underline">
            Monitoring
          </Link>{" "}
          or a completed tender.
        </div>
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {COLUMNS.map((col) => {
            const items = byStage(col.stage);
            return (
              <div key={col.stage} className="bg-slate-100/70 rounded-xl p-3">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-slate-700">{col.label}</h2>
                  <span className="text-xs text-slate-400">{items.length}</span>
                </div>
                <div className="space-y-2">
                  {items.map((b) => <BidCard key={b.id} bid={b} />)}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {decided.length > 0 && (
        <div className="mt-8">
          <h2 className="text-sm font-semibold text-slate-700 mb-3">
            Decided ({decided.length})
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {decided.map((b) => <BidCard key={b.id} bid={b} />)}
          </div>
        </div>
      )}
    </div>
  );
}
