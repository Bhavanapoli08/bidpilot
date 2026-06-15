"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

const plans = [
  { tier: "starter", name: "Starter", price: "₹999", limit: 10 },
  { tier: "pro", name: "Pro", price: "₹4,999", limit: 50, featured: true },
  { tier: "enterprise", name: "Enterprise", price: "Custom", limit: "∞" },
];

export default function BillingPage() {
  const { data: usage, refetch } = useQuery({
    queryKey: ["usage"],
    queryFn: async () => (await api.getUsage()).data,
  });

  const subscribe = useMutation({
    mutationFn: async (tier: string) => (await api.subscribe(tier)).data,
    onSuccess: (data) => {
      if (data.payment_url) {
        window.open(data.payment_url, "_blank");
      }
      refetch();
    },
  });

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-900">Billing & Usage</h1>

      {/* Current usage */}
      {usage && (
        <div className="mt-6 p-6 bg-white rounded-xl border">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-sm text-slate-500">Current plan</span>
              <div className="text-lg font-semibold text-slate-900 capitalize">
                {usage.tier}
              </div>
            </div>
            <div className="text-right">
              <span className="text-sm text-slate-500">This month</span>
              <div className="text-lg font-semibold text-slate-900">
                {usage.tenders_analyzed} / {usage.tenders_limit}
              </div>
            </div>
          </div>
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 rounded-full"
              style={{ width: `${Math.min(usage.percent_used, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Plans */}
      <div className="mt-8 grid md:grid-cols-3 gap-4">
        {plans.map((p) => (
          <div
            key={p.tier}
            className={`p-6 rounded-xl border ${
              p.featured ? "border-brand-600 border-2" : ""
            } bg-white`}
          >
            <h3 className="font-semibold text-slate-900">{p.name}</h3>
            <div className="mt-2 text-3xl font-bold text-slate-900">
              {p.price}
              {p.price !== "Custom" && (
                <span className="text-sm font-normal text-slate-500">/mo</span>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-500">{p.limit} tenders/month</p>
            <button
              onClick={() => subscribe.mutate(p.tier)}
              disabled={subscribe.isPending || usage?.tier === p.tier}
              className="mt-4 w-full py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
            >
              {usage?.tier === p.tier ? "Current plan" : "Choose plan"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
