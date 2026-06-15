import axios, { AxiosInstance, AxiosError } from "axios";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

// ---- Token storage (in-memory + localStorage on client) ----
export const tokenStore = {
  get access() {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  },
  get refresh() {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("refresh_token");
  },
  set(access: string, refresh: string) {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  },
  clear() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};

// ---- Axios instance ----
const client: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-refresh on 401
client.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as any;
    if (error.response?.status === 401 && !original._retry && tokenStore.refresh) {
      original._retry = true;
      try {
        const { data } = await axios.post(
          `${API_URL}/auth/refresh`,
          {},
          { headers: { Authorization: `Bearer ${tokenStore.refresh}` } }
        );
        tokenStore.set(data.access_token, data.refresh_token);
        original.headers.Authorization = `Bearer ${data.access_token}`;
        return client(original);
      } catch {
        tokenStore.clear();
        if (typeof window !== "undefined") window.location.href = "/auth/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---- Error helper ----
// FastAPI returns validation (422) errors as `detail: [{type, loc, msg, ...}]`
// and most others as `detail: "message"`. Normalise either into a string so
// components never render an object as a React child.
export function errorMessage(err: any, fallback = "Something went wrong"): string {
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (typeof d === "string" ? d : d?.msg))
      .filter(Boolean);
    if (msgs.length) return msgs.join(", ");
  }
  if (typeof err?.message === "string") return err.message;
  return fallback;
}

// ---- Types ----
export interface Tender {
  id: string;
  file_name: string;
  status: "pending" | "processing" | "completed" | "failed";
  created_at: string;
}

export interface TenderScore {
  win_probability: number;
  eligibility_score: number;
  fit_score: number;
  risk_level: string;
  competition_intensity: string;
  recommendation: string;
  reasoning: string[];
}

export interface TenderAnalysis {
  tender_id: string;
  summary: string | null;
  tender_value: number | null;
  bid_deadline: string | null;
  sector: string | null;
  location: string | null;
  eligibility_criteria: Record<string, unknown>;
  required_documents: string[];
}

export interface QAResponse {
  answer: string;
  sources: Array<{ page: number; preview: string; score: number }>;
  confidence: number;
}

export interface TenderSource {
  id: string;
  name: string;
  source_type: "rss" | "http_json" | "sample";
  url: string | null;
  keywords: string[];
  sectors: string[];
  states: string[];
  is_active: boolean;
  last_checked_at: string | null;
  last_error: string | null;
}

export interface DiscoveredTender {
  id: string;
  source_id: string;
  title: string;
  description: string | null;
  tender_value: number | null;
  bid_deadline: string | null;
  sector: string | null;
  location: string | null;
  url: string | null;
  match_score: number;
  match_reasons: string[];
  status: "new" | "dismissed" | "imported";
  discovered_at: string;
}

export interface ScanResult {
  sources_scanned: number;
  new_discovered: number;
  alerts_created: number;
}

export type BidStage =
  | "identified"
  | "qualifying"
  | "go_no_go"
  | "preparing"
  | "submitted"
  | "won"
  | "lost"
  | "dropped";

export interface Bid {
  id: string;
  title: string;
  stage: BidStage;
  tender_id: string | null;
  discovered_tender_id: string | null;
  assigned_to_id: string | null;
  tender_value: number | null;
  bid_deadline: string | null;
  win_probability: number | null;
  notes: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BidEvent {
  id: string;
  event_type: string;
  from_value: string | null;
  to_value: string | null;
  note: string | null;
  actor_id: string | null;
  created_at: string;
}

export interface BidDetail extends Bid {
  events: BidEvent[];
}

export interface CalendarEvent {
  bid_id: string | null;
  tender_id: string | null;
  title: string;
  deadline: string;
  stage: string | null;
  days_remaining: number;
}

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  bid_id: string | null;
  discovered_tender_id: string | null;
  is_read: boolean;
  created_at: string;
}

// ---- API methods ----
export const api = {
  // Auth
  register: (email: string, password: string, organization_name: string) =>
    client.post("/auth/register", { email, password, organization_name }),
  login: (email: string, password: string) =>
    client.post("/auth/login", { email, password }),
  me: () => client.get("/auth/me"),

  // Tenders
  uploadTender: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return client.post("/tenders/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  listTenders: () => client.get<Tender[]>("/tenders"),
  getTender: (id: string) => client.get<Tender>(`/tenders/${id}`),
  getTenderStatus: (id: string) => client.get(`/tenders/${id}/status`),
  getAnalysis: (id: string) => client.get<TenderAnalysis>(`/tenders/${id}/analysis`),
  askTender: (id: string, question: string) =>
    client.post<QAResponse>(`/tenders/${id}/ask`, { question, top_k: 5 }),
  deleteTender: (id: string) => client.delete(`/tenders/${id}`),

  // Scoring
  computeScore: (id: string) => client.post<TenderScore>(`/tenders/${id}/score`),
  getScore: (id: string) => client.get<TenderScore>(`/tenders/${id}/score`),

  // Company
  getProfile: () => client.get("/company/profile"),
  saveProfile: (data: Record<string, unknown>) =>
    client.post("/company/profile", data),

  // Billing
  getUsage: () => client.get("/billing/usage"),
  subscribe: (tier: string) => client.post(`/billing/subscribe?tier=${tier}`),

  // Jobs
  getJobStatus: (jobId: string) => client.get(`/jobs/${jobId}/status`),

  // Monitoring
  listSources: () => client.get<TenderSource[]>("/monitoring/sources"),
  createSource: (data: Partial<TenderSource> & { name: string }) =>
    client.post<TenderSource>("/monitoring/sources", data),
  updateSource: (id: string, data: Partial<TenderSource>) =>
    client.patch<TenderSource>(`/monitoring/sources/${id}`, data),
  deleteSource: (id: string) => client.delete(`/monitoring/sources/${id}`),
  scanNow: () => client.post<ScanResult>("/monitoring/scan"),
  listDiscovered: (status = "new", minMatch = 0) =>
    client.get<DiscoveredTender[]>(
      `/monitoring/discovered?status=${status}&min_match=${minMatch}`
    ),
  dismissDiscovered: (id: string) =>
    client.post<DiscoveredTender>(`/monitoring/discovered/${id}/dismiss`),
  importDiscovered: (id: string) =>
    client.post<Bid>(`/monitoring/discovered/${id}/import`),

  // Bids
  listBids: () => client.get<Bid[]>("/bids"),
  getBid: (id: string) => client.get<BidDetail>(`/bids/${id}`),
  createBid: (data: {
    title?: string;
    tender_id?: string;
    discovered_tender_id?: string;
    assigned_to_id?: string;
    notes?: string;
  }) => client.post<Bid>("/bids", data),
  updateBidStage: (id: string, stage: BidStage, note?: string) =>
    client.patch<Bid>(`/bids/${id}/stage`, { stage, note }),
  assignBid: (id: string, assigned_to_id: string | null, note?: string) =>
    client.patch<Bid>(`/bids/${id}/assign`, { assigned_to_id, note }),
  deleteBid: (id: string) => client.delete(`/bids/${id}`),
  getCalendar: (days = 60) =>
    client.get<CalendarEvent[]>(`/bids/calendar?days=${days}`),

  // Notifications
  listNotifications: (unreadOnly = false) =>
    client.get<AppNotification[]>(`/notifications?unread_only=${unreadOnly}`),
  unreadCount: () => client.get<{ unread: number }>("/notifications/unread-count"),
  markNotificationRead: (id: string) =>
    client.post(`/notifications/${id}/read`),
  markAllNotificationsRead: () => client.post("/notifications/read-all"),
};

export default client;
