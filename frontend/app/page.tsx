"use client";

import Link from "next/link";

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5 bg-white border-b">
        <div className="text-xl font-bold text-brand-600">BidPilot AI</div>
        <div className="flex gap-4">
          <Link
            href="/auth/login"
            className="px-4 py-2 text-slate-600 hover:text-slate-900"
          >
            Login
          </Link>
          <Link
            href="/auth/register"
            className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700"
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-8 py-24 text-center">
        <h1 className="text-5xl font-bold text-slate-900 leading-tight">
          Should you bid on this tender?
        </h1>
        <p className="mt-6 text-xl text-slate-600 max-w-2xl mx-auto">
          BidPilot AI reads government tenders, scores your win probability, and
          tells you which bids are worth your time — so you stop wasting hours on
          losing bids.
        </p>
        <div className="mt-10 flex gap-4 justify-center">
          <Link
            href="/auth/register"
            className="px-8 py-4 bg-brand-600 text-white rounded-lg text-lg font-medium hover:bg-brand-700"
          >
            Start Free — 3 Tenders/Month
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-8 py-16 grid md:grid-cols-3 gap-8">
        {[
          {
            title: "Upload & Extract",
            desc: "Drop a tender PDF. We extract eligibility, deadlines, required docs, and penalties automatically.",
          },
          {
            title: "Bid Suitability Score",
            desc: "Win probability, eligibility match, risk level, and competition — so you bid smart.",
          },
          {
            title: "Ask Anything",
            desc: "Q&A on any tender with answers cited to exact source pages. No hallucinations.",
          },
        ].map((f) => (
          <div key={f.title} className="p-6 bg-white rounded-xl border">
            <h3 className="text-lg font-semibold text-slate-900">{f.title}</h3>
            <p className="mt-3 text-slate-600">{f.desc}</p>
          </div>
        ))}
      </section>

      {/* Pricing */}
      <section className="max-w-5xl mx-auto px-8 py-16">
        <h2 className="text-3xl font-bold text-center text-slate-900 mb-12">
          Simple pricing
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { name: "Starter", price: "₹999", tenders: "10 tenders/mo" },
            { name: "Pro", price: "₹4,999", tenders: "50 tenders/mo", featured: true },
            { name: "Enterprise", price: "Custom", tenders: "Unlimited" },
          ].map((p) => (
            <div
              key={p.name}
              className={`p-8 rounded-xl border ${
                p.featured ? "border-brand-600 border-2 bg-white" : "bg-white"
              }`}
            >
              <h3 className="text-lg font-semibold">{p.name}</h3>
              <div className="mt-4 text-4xl font-bold text-slate-900">
                {p.price}
                {p.price !== "Custom" && (
                  <span className="text-base font-normal text-slate-500">/mo</span>
                )}
              </div>
              <p className="mt-2 text-slate-600">{p.tenders}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="text-center py-12 text-slate-400 border-t mt-16">
        © 2026 BidPilot AI · Built for construction SMBs in India
      </footer>
    </main>
  );
}
