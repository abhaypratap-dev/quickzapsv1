import type { Transaction, User } from "@/types";

export function money(value: string | number | null | undefined) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2
  }).format(numeric);
}

export function number(value: string | number | null | undefined) {
  return new Intl.NumberFormat("en-IN").format(Number(value || 0));
}

export function dateTime(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function name(user?: Pick<User, "first_name" | "last_name" | "mobile"> | null) {
  const full = `${user?.first_name || ""} ${user?.last_name || ""}`.trim();
  return full || user?.mobile || "-";
}

export function statusTone(status?: string) {
  switch (status) {
    case "active":
    case "approved":
    case "success":
    case "healthy":
    case "sent":
      return "green";
    case "pending":
    case "signup":
    case "created":
    case "manual_review":
      return "amber";
    case "failed":
    case "rejected":
    case "deleted":
    case "down":
      return "red";
    case "inactive":
    case "reupload_requested":
    case "degraded":
      return "violet";
    default:
      return "neutral";
  }
}

export function transactionOutcome(status: Transaction["status"]) {
  if (status === "success") return "success";
  if (status === "failed" || status === "reversed" || status === "refunded") return "failed";
  return "pending";
}
