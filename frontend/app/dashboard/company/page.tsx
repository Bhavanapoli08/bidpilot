"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

const SECTORS = ["construction", "electrical", "IT", "civil", "mechanical", "consulting"];
const STATES = ["Maharashtra", "Gujarat", "Karnataka", "Telangana", "Tamil Nadu", "Delhi"];
const CERTS = ["ISO_9001", "ISO_14001", "OHSAS_18001"];

export default function CompanyProfilePage() {
  const [form, setForm] = useState({
    company_name: "",
    annual_turnover: 0,
    net_worth: 0,
    team_size: 0,
    years_in_business: 0,
    sectors: [] as string[],
    operating_states: [] as string[],
    certifications: {} as Record<string, boolean>,
    registrations: {} as Record<string, string>,
  });
  const [saved, setSaved] = useState(false);

  const { data } = useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      try {
        return (await api.getProfile()).data;
      } catch {
        return null;
      }
    },
  });

  useEffect(() => {
    if (data) {
      setForm((prev) => ({ ...prev, ...data }));
    }
  }, [data]);

  const save = useMutation({
    mutationFn: async () => (await api.saveProfile(form)).data,
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const toggleArray = (key: "sectors" | "operating_states", value: string) => {
    setForm((prev) => {
      const arr = prev[key];
      return {
        ...prev,
        [key]: arr.includes(value)
          ? arr.filter((v) => v !== value)
          : [...arr, value],
      };
    });
  };

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-slate-900">Company Profile</h1>
      <p className="mt-1 text-slate-500">
        This is used to compute your bid suitability scores
      </p>

      {saved && (
        <div className="mt-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm">
          Profile saved
        </div>
      )}

      <div className="mt-6 space-y-6 bg-white p-6 rounded-xl border">
        <div>
          <label className="block text-sm font-medium text-slate-700">
            Company name
          </label>
          <input
            value={form.company_name}
            onChange={(e) => setForm({ ...form, company_name: e.target.value })}
            className="mt-1 w-full px-3 py-2 border rounded-lg"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Annual turnover (₹ lakhs)
            </label>
            <input
              type="number"
              value={form.annual_turnover}
              onChange={(e) =>
                setForm({ ...form, annual_turnover: Number(e.target.value) })
              }
              className="mt-1 w-full px-3 py-2 border rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Net worth (₹ lakhs)
            </label>
            <input
              type="number"
              value={form.net_worth}
              onChange={(e) =>
                setForm({ ...form, net_worth: Number(e.target.value) })
              }
              className="mt-1 w-full px-3 py-2 border rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Team size
            </label>
            <input
              type="number"
              value={form.team_size}
              onChange={(e) =>
                setForm({ ...form, team_size: Number(e.target.value) })
              }
              className="mt-1 w-full px-3 py-2 border rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Years in business
            </label>
            <input
              type="number"
              value={form.years_in_business}
              onChange={(e) =>
                setForm({ ...form, years_in_business: Number(e.target.value) })
              }
              className="mt-1 w-full px-3 py-2 border rounded-lg"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Sectors
          </label>
          <div className="flex flex-wrap gap-2">
            {SECTORS.map((s) => (
              <button
                key={s}
                onClick={() => toggleArray("sectors", s)}
                className={`px-3 py-1.5 rounded-full text-sm border ${
                  form.sectors.includes(s)
                    ? "bg-brand-600 text-white border-brand-600"
                    : "bg-white text-slate-600 border-slate-300"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Operating states
          </label>
          <div className="flex flex-wrap gap-2">
            {STATES.map((s) => (
              <button
                key={s}
                onClick={() => toggleArray("operating_states", s)}
                className={`px-3 py-1.5 rounded-full text-sm border ${
                  form.operating_states.includes(s)
                    ? "bg-brand-600 text-white border-brand-600"
                    : "bg-white text-slate-600 border-slate-300"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Certifications
          </label>
          <div className="space-y-2">
            {CERTS.map((c) => (
              <label key={c} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.certifications[c] || false}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      certifications: {
                        ...form.certifications,
                        [c]: e.target.checked,
                      },
                    })
                  }
                  className="rounded"
                />
                <span className="text-sm text-slate-700">{c.replace(/_/g, " ")}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">
              GST number
            </label>
            <input
              value={form.registrations.GST || ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  registrations: { ...form.registrations, GST: e.target.value },
                })
              }
              className="mt-1 w-full px-3 py-2 border rounded-lg"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              PAN number
            </label>
            <input
              value={form.registrations.PAN || ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  registrations: { ...form.registrations, PAN: e.target.value },
                })
              }
              className="mt-1 w-full px-3 py-2 border rounded-lg"
            />
          </div>
        </div>

        <button
          onClick={() => save.mutate()}
          disabled={save.isPending}
          className="px-6 py-2.5 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
        >
          {save.isPending ? "Saving..." : "Save Profile"}
        </button>
      </div>
    </div>
  );
}
