"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, DiscoveredTender } from "@/lib/api/client";

function matchColor(score: number) {
  if (score >= 0.7) return "bg-green-100 text-green-700";
  if (score >= 0.4) return "bg-amber-100 text-amber-700";
  return "bg-slate-100 text-slate-600";
}

function formatValue(v: number | null) {
  if (!v) return "—";
  if (v >= 10_000_000) return `₹${(v / 10_000_000).toFixed(2)} Cr`;
  if (v >= 100_000) return `₹${(v / 100_000).toFixed(1)} L`;
  return `₹${v.toLocaleString()}`;
}

export default function MonitoringPage() {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", source_type: "sample", url: "" });

  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: async () => (await api.listSources()).data,
  });

  const discovered = useQuery({
    queryKey: ["discovered"],
    queryFn: async () => (await api.listDiscovered("new")).data,
  });

  const scan = useMutation({
    mutationFn: async () => (await api.scanNow()).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discovered"] });
      qc.invalidateQueries({ queryKey: ["sources"] });
      qc.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const createSource = useMutation({
    mutationFn: async () =>
      (await api.createSource({
        name: form.name,
        source_type: form.source_type as any,
        url: form.url || undefined,
      })).data,
    onSuccess: () => {
      setShowAdd(false);
      setForm({ name: "", source_type: "sample", url: "" });
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const dismiss = useMutation({
    mutationFn: async (id: string) => (await api.dismissDiscovered(id)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["discovered"] }),
  });

  const importBid = useMutation({
    mutationFn: async (id: string) => (await api.importDiscovered(id)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["discovered"] });
      qc.invalidateQueries({ queryKey: ["bids"] });
    },
  });

  return (
    <div className="p-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Tender Monitoring</h1>
          <p className="mt-1 text-slate-500">
            Auto-discover opportunities from your sources, matched to your company profile.
          </p>
        </div>
        <button
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {scan.isPending ? "Scanning…" : "🔄 Scan now"}
        </button>
      </div>

      {scan.data && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          Scanned {scan.data.sources_scanned} source(s) · {scan.data.new_discovered} new ·{" "}
          {scan.data.alerts_created} alert(s) raised.
        </div>
      )}

      {/* Sources */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-800">Sources</h2>
          <button
            onClick={() => setShowAdd((s) => !s)}
            className="text-sm text-brand-600 font-medium hover:underline"
          >
            {showAdd ? "Cancel" : "+ Add source"}
          </button>
        </div>

        {showAdd && (
          <div className="mb-4 p-4 bg-white border rounded-xl grid gap-3 sm:grid-cols-3">
            <input
              className="border rounded-lg px-3 py-2 text-sm"
              placeholder="Source name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <select
              className="border rounded-lg px-3 py-2 text-sm"
              value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })}
            >
              <option value="sample">Sample (demo data)</option>
              <option value="rss">RSS / Atom feed</option>
              <option value="http_json">HTTP JSON</option>
            </select>
            <input
              className="border rounded-lg px-3 py-2 text-sm"
              placeholder="Feed URL (for RSS / JSON)"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
            />
            <div className="sm:col-span-3">
              <button
                onClick={() => createSource.mutate()}
                disabled={!form.name || createSource.isPending}
                className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium disabled:opacity-50"
              >
                Save source
              </button>
            </div>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sources.data?.map((s) => (
            <div key={s.id} className="p-4 bg-white border rounded-xl">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-900">{s.name}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 uppercase">
                  {s.source_type}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                {s.last_checked_at
                  ? `Last checked ${new Date(s.last_checked_at).toLocaleString()}`
                  : "Never checked"}
              </p>
              {s.last_error && (
                <p className="mt-1 text-xs text-red-500">⚠ {s.last_error}</p>
              )}
            </div>
          ))}
          {sources.data?.length === 0 && (
            <p className="text-slate-500 text-sm">
              No sources yet. Add a "Sample" source to try the pipeline instantly.
            </p>
          )}
        </div>
      </section>

      {/* Discovered */}
      <section>
        <h2 className="text-lg font-semibold text-slate-800 mb-3">
          New opportunities {discovered.data ? `(${discovered.data.length})` : ""}
        </h2>
        <div className="space-y-3">
          {discovered.data?.map((d: DiscoveredTender) => (
            <div key={d.id} className="p-4 bg-white border rounded-xl">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-semibold ${matchColor(
                        d.match_score
                      )}`}
                    >
                      {Math.round(d.match_score * 100)}% match
                    </span>
                    <h3 className="font-medium text-slate-900 truncate">{d.title}</h3>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">
                    {formatValue(d.tender_value)} · {d.sector || "—"} · {d.location || "—"}
                    {d.bid_deadline &&
                      ` · due ${new Date(d.bid_deadline).toLocaleDateString()}`}
                  </p>
                  {d.match_reasons?.length > 0 && (
                    <ul className="mt-2 text-xs text-slate-500 space-y-0.5">
                      {d.match_reasons.slice(0, 3).map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="flex flex-col gap-2 shrink-0">
                  <button
                    onClick={() => importBid.mutate(d.id)}
                    disabled={importBid.isPending}
                    className="px-3 py-1.5 bg-brand-600 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                  >
                    → Add to pipeline
                  </button>
                  <button
                    onClick={() => dismiss.mutate(d.id)}
                    className="px-3 py-1.5 text-slate-500 text-sm hover:bg-slate-50 rounded-lg"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          ))}
          {discovered.data?.length === 0 && (
            <div className="p-12 bg-white rounded-xl border text-center text-slate-500">
              No new opportunities. Run a scan to check your sources.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
