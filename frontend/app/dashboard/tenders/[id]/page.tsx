"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api, QAResponse } from "@/lib/api/client";

const recommendationStyles: Record<string, string> = {
  high_priority: "bg-green-100 text-green-800",
  medium_priority: "bg-amber-100 text-amber-800",
  low_priority: "bg-orange-100 text-orange-800",
  skip: "bg-red-100 text-red-800",
  maybe: "bg-slate-100 text-slate-800",
};

const riskStyles: Record<string, string> = {
  low: "text-green-600",
  medium: "text-amber-600",
  high: "text-red-600",
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-900">{pct}%</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand-500 rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function TenderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [qaResult, setQaResult] = useState<QAResponse | null>(null);

  const addToPipeline = useMutation({
    mutationFn: async () => (await api.createBid({ tender_id: id })).data,
    onSuccess: (bid) => router.push(`/dashboard/bids/${bid.id}`),
  });

  const { data: analysis } = useQuery({
    queryKey: ["analysis", id],
    queryFn: async () => (await api.getAnalysis(id)).data,
  });

  const { data: score, refetch: refetchScore } = useQuery({
    queryKey: ["score", id],
    queryFn: async () => {
      try {
        return (await api.getScore(id)).data;
      } catch {
        return null;
      }
    },
  });

  const computeScore = useMutation({
    mutationFn: async () => (await api.computeScore(id)).data,
    onSuccess: () => refetchScore(),
  });

  const askMutation = useMutation({
    mutationFn: async (q: string) => (await api.askTender(id, q)).data,
    onSuccess: (data) => setQaResult(data),
  });

  return (
    <div className="p-8 max-w-4xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Tender Analysis</h1>
        <button
          onClick={() => addToPipeline.mutate()}
          disabled={addToPipeline.isPending}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {addToPipeline.isPending ? "Adding…" : "→ Add to pipeline"}
        </button>
      </div>

      {/* Summary */}
      {analysis?.summary && (
        <div className="mt-6 p-6 bg-white rounded-xl border">
          <h2 className="text-sm font-medium text-slate-500 uppercase mb-2">
            Summary
          </h2>
          <p className="text-slate-700 leading-relaxed">{analysis.summary}</p>
        </div>
      )}

      {/* Key facts */}
      {analysis && (
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: "Value",
              value: analysis.tender_value
                ? `₹${analysis.tender_value.toLocaleString()}`
                : "—",
            },
            {
              label: "Deadline",
              value: analysis.bid_deadline
                ? new Date(analysis.bid_deadline).toLocaleDateString()
                : "—",
            },
            { label: "Sector", value: analysis.sector || "—" },
            { label: "Location", value: analysis.location || "—" },
          ].map((f) => (
            <div key={f.label} className="p-4 bg-white rounded-xl border">
              <div className="text-xs text-slate-500 uppercase">{f.label}</div>
              <div className="mt-1 font-semibold text-slate-900">{f.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Score */}
      <div className="mt-6 p-6 bg-white rounded-xl border">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-slate-900">
            Bid Suitability Score
          </h2>
          {!score && (
            <button
              onClick={() => computeScore.mutate()}
              disabled={computeScore.isPending}
              className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {computeScore.isPending ? "Computing..." : "Compute Score"}
            </button>
          )}
        </div>

        {computeScore.isError && (
          <p className="text-red-600 text-sm">
            {(computeScore.error as any)?.response?.data?.detail ||
              "Set up your company profile first."}
          </p>
        )}

        {score && (
          <div>
            {/* Headline win probability */}
            <div className="flex items-center gap-6 mb-6">
              <div className="text-center">
                <div className="text-5xl font-bold text-brand-600">
                  {Math.round(score.win_probability * 100)}%
                </div>
                <div className="text-sm text-slate-500 mt-1">Win probability</div>
              </div>
              <div className="flex-1">
                <span
                  className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                    recommendationStyles[score.recommendation]
                  }`}
                >
                  {score.recommendation.replace(/_/g, " ").toUpperCase()}
                </span>
                <div className="mt-2 text-sm">
                  Risk:{" "}
                  <span className={`font-medium ${riskStyles[score.risk_level]}`}>
                    {score.risk_level}
                  </span>{" "}
                  · Competition:{" "}
                  <span className="font-medium text-slate-700">
                    {score.competition_intensity}
                  </span>
                </div>
              </div>
            </div>

            {/* Sub-scores */}
            <div className="space-y-3">
              <ScoreBar label="Eligibility" value={score.eligibility_score} />
              <ScoreBar label="Fit" value={score.fit_score} />
            </div>

            {/* Reasoning */}
            {score.reasoning?.length > 0 && (
              <div className="mt-6 pt-6 border-t">
                <h3 className="text-sm font-medium text-slate-500 uppercase mb-3">
                  Why this score
                </h3>
                <ul className="space-y-2">
                  {score.reasoning.map((r, i) => (
                    <li key={i} className="text-sm text-slate-700">
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Q&A */}
      <div className="mt-6 p-6 bg-white rounded-xl border">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">
          Ask about this tender
        </h2>
        <div className="flex gap-2">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) =>
              e.key === "Enter" && question && askMutation.mutate(question)
            }
            placeholder="e.g. What is the EMD amount?"
            className="flex-1 px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500"
          />
          <button
            onClick={() => question && askMutation.mutate(question)}
            disabled={askMutation.isPending}
            className="px-4 py-2 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {askMutation.isPending ? "..." : "Ask"}
          </button>
        </div>

        {qaResult && (
          <div className="mt-4 p-4 bg-slate-50 rounded-lg">
            <p className="text-slate-800">{qaResult.answer}</p>
            {qaResult.sources?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-200">
                <p className="text-xs text-slate-500 mb-1">
                  Sources (confidence: {Math.round(qaResult.confidence * 100)}%)
                </p>
                {qaResult.sources.map((s, i) => (
                  <span
                    key={i}
                    className="inline-block px-2 py-0.5 mr-1 mb-1 bg-white border rounded text-xs text-slate-600"
                  >
                    Page {s.page}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
