"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, tokenStore, errorMessage } from "@/lib/api/client";

export default function RegisterPage() {
  const router = useRouter();
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setError("");
    setLoading(true);
    try {
      const { data } = await api.register(email, password, orgName);
      tokenStore.set(data.access_token, data.refresh_token);
      router.push("/dashboard");
    } catch (err: any) {
      setError(errorMessage(err, "Registration failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="w-full max-w-md p-8 bg-white rounded-xl border shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">Create your account</h1>
        <p className="mt-2 text-slate-500">Start scoring tenders in minutes</p>

        {error && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="mt-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Company name
            </label>
            <input
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="mt-1 w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500"
              placeholder="ABC Construction Pvt Ltd"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500"
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              className="mt-1 w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-brand-500"
              placeholder="At least 8 characters"
            />
          </div>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="w-full py-2.5 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Create Account"}
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/auth/login" className="text-brand-600 font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
