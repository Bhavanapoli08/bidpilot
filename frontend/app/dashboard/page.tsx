"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api, Tender } from "@/lib/api/client";

const statusStyles: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700",
  processing: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export default function DashboardHome() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tenders"],
    queryFn: async () => (await api.listTenders()).data,
    refetchInterval: (query) => {
      const tenders = query.state.data as Tender[] | undefined;
      // Poll while anything is still processing
      const processing = tenders?.some(
        (t) => t.status === "pending" || t.status === "processing"
      );
      return processing ? 4000 : false;
    },
  });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Your Tenders</h1>
          <p className="mt-1 text-slate-500">
            Upload tenders to get bid suitability scores
          </p>
        </div>
        <Link
          href="/dashboard/upload"
          className="px-4 py-2 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700"
        >
          + Upload Tender
        </Link>
      </div>

      {isLoading && <p className="text-slate-500">Loading tenders...</p>}
      {error && (
        <p className="text-red-600">Failed to load tenders. Check your connection.</p>
      )}

      {data && data.length === 0 && (
        <div className="p-12 bg-white rounded-xl border text-center">
          <p className="text-slate-500">No tenders yet.</p>
          <Link
            href="/dashboard/upload"
            className="mt-4 inline-block px-4 py-2 bg-brand-600 text-white rounded-lg"
          >
            Upload your first tender
          </Link>
        </div>
      )}

      {data && data.length > 0 && (
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  File
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  Status
                </th>
                <th className="text-left px-6 py-3 text-xs font-medium text-slate-500 uppercase">
                  Uploaded
                </th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map((tender) => (
                <tr key={tender.id} className="hover:bg-slate-50">
                  <td className="px-6 py-4 font-medium text-slate-900">
                    {tender.file_name}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                        statusStyles[tender.status]
                      }`}
                    >
                      {tender.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-500 text-sm">
                    {new Date(tender.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {tender.status === "completed" && (
                      <Link
                        href={`/dashboard/tenders/${tender.id}`}
                        className="text-brand-600 font-medium text-sm hover:underline"
                      >
                        View score →
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
