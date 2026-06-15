"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, BidStage } from "@/lib/api/client";

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
  if (!v) return "—";
  if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(2)} Cr`;
  if (v >= 100_000) return `₹${(v / 100_000).toFixed(1)} L`;
  return `₹${v.toLocaleString()}`;
}

export default function BidDetailPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const { data: bid, isLoading } = useQuery({
    queryKey: ["bid", id],
    queryFn: async () => (await api.getBid(id)).data,
  });

  const move = useMutation({
    mutationFn: async (stage: BidStage) => (await api.updateBidStage(id, stage)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["bid", id] });
      qc.invalidateQueries({ queryKey: ["bids"] });
    },
  });

  if (isLoading) return <div className="p-8 text-slate-500">Loading…</div>;
  if (!bid) return <div className="p-8 text-red-600">Bid not found.</div>;

  return (
    <div className="p-8 max-w-3xl">
      <Link href="/dashboard/bids" className="text-sm text-brand-600 hover:underline">
        ← Back to pipeline
      </Link>

      <div className="mt-4 flex items-start justify-between gap-4">
        <h1 className="text-2xl font-bold text-slate-900">{bid.title}</h1>
        <span className="shrink-0 px-3 py-1 rounded-full bg-brand-50 text-brand-700 text-sm font-medium">
          {STAGE_LABEL[bid.stage]}
        </span>
      </div>

      <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Stat label="Value" value={formatValue(bid.tender_value)} />
        <Stat
          label="Deadline"
          value={bid.bid_deadline ? new Date(bid.bid_deadline).toLocaleDateString() : "—"}
        />
        <Stat
          label="Win probability"
          value={bid.win_probability != null ? `${Math.round(bid.win_probability * 100)}%` : "—"}
        />
        <Stat
          label="Decided"
          value={bid.decided_at ? new Date(bid.decided_at).toLocaleDateString() : "Active"}
        />
      </div>

      <div className="mt-6">
        <label className="block text-sm font-medium text-slate-600 mb-1">Move to stage</label>
        <select
          value={bid.stage}
          onChange={(e) => move.mutate(e.target.value as BidStage)}
          className="border rounded-lg px-3 py-2 text-sm"
        >
          {ALL_STAGES.map((s) => (
            <option key={s} value={s}>{STAGE_LABEL[s]}</option>
          ))}
        </select>
      </div>

      {bid.notes && (
        <div className="mt-6 p-4 bg-white border rounded-xl">
          <h3 className="text-sm font-semibold text-slate-700 mb-1">Notes</h3>
          <p className="text-sm text-slate-600 whitespace-pre-wrap">{bid.notes}</p>
        </div>
      )}

      <div className="mt-8">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Activity</h3>
        <ol className="relative border-l border-slate-200 ml-2 space-y-4">
          {bid.events.map((e) => (
            <li key={e.id} className="ml-4">
              <div className="absolute w-2 h-2 bg-brand-500 rounded-full -left-1 mt-1.5" />
              <p className="text-sm text-slate-700">
                {e.event_type === "stage_change"
                  ? `Stage: ${e.from_value || "—"} → ${e.to_value}`
                  : e.event_type === "assigned"
                  ? "Reassigned"
                  : e.event_type === "created"
                  ? "Bid created"
                  : e.event_type}
              </p>
              {e.note && <p className="text-xs text-slate-500 mt-0.5">{e.note}</p>}
              <p className="text-xs text-slate-400 mt-0.5">
                {new Date(e.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-3 bg-white border rounded-xl">
      <p className="text-xs text-slate-400 uppercase">{label}</p>
      <p className="mt-1 font-semibold text-slate-900">{value}</p>
    </div>
  );
}
