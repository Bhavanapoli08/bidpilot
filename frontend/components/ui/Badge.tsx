import React from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";

const badgeStyles: Record<BadgeVariant, string> = {
  default: "bg-slate-100 text-slate-700",
  success: "bg-green-100 text-green-700",
  warning: "bg-amber-100 text-amber-700",
  danger: "bg-red-100 text-red-700",
  info: "bg-blue-100 text-blue-700",
};

export function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: BadgeVariant;
}) {
  return (
    <span
      className={`inline-block px-2.5 py-1 rounded-full text-xs font-medium ${badgeStyles[variant]}`}
    >
      {children}
    </span>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`p-6 bg-white rounded-xl border ${className}`}>{children}</div>
  );
}

/** Maps a tender status to a badge variant. */
export function statusVariant(status: string): BadgeVariant {
  switch (status) {
    case "completed":
      return "success";
    case "processing":
    case "pending":
      return "warning";
    case "failed":
      return "danger";
    default:
      return "default";
  }
}
