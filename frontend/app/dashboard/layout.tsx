"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { tokenStore, api } from "@/lib/api/client";

const navItems = [
  { href: "/dashboard", label: "Tenders", icon: "📄" },
  { href: "/dashboard/upload", label: "Upload", icon: "⬆️" },
  { href: "/dashboard/monitoring", label: "Monitoring", icon: "📡" },
  { href: "/dashboard/bids", label: "Bid Pipeline", icon: "📊" },
  { href: "/dashboard/calendar", label: "Calendar", icon: "🗓️" },
  { href: "/dashboard/company", label: "Company Profile", icon: "🏢" },
  { href: "/dashboard/billing", label: "Billing", icon: "💳" },
];

function NotificationBell() {
  const { data } = useQuery({
    queryKey: ["unread-count"],
    queryFn: async () => (await api.unreadCount()).data,
    refetchInterval: 30000,
  });
  const unread = data?.unread ?? 0;
  return (
    <Link
      href="/dashboard/notifications"
      className="relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50"
    >
      <span>🔔</span>
      Alerts
      {unread > 0 && (
        <span className="absolute right-3 top-2 min-w-[18px] h-[18px] px-1 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
    </Link>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!tokenStore.access) router.push("/auth/login");
  }, [router]);

  const logout = () => {
    tokenStore.clear();
    router.push("/auth/login");
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r flex flex-col">
        <div className="px-6 py-5 border-b">
          <div className="text-xl font-bold text-brand-600">BidPilot AI</div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium ${
                  active
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                <span>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
          <NotificationBell />
        </nav>
        <div className="p-3 border-t">
          <button
            onClick={logout}
            className="w-full px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 rounded-lg text-left"
          >
            🚪 Logout
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
