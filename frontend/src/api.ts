export type Source = {
  id: number;
  title: string;
  username: string | null;
  url: string | null;
  invite_url: string | null;
  is_public: boolean;
  status: string;
  participants_count: number | null;
  source_score: number | null;
  created_at: string;
};

export type Lead = {
  id: number;
  message_id: number;
  source_id: number;
  source_title: string;
  message_text: string;
  message_url: string | null;
  sender_username: string | null;
  message_date: string;
  confidence: number;
  lead_score: number;
  category: string;
  service: string | null;
  intent: string;
  urgency: string | null;
  budget: string | null;
  budget_currency: string | null;
  deadline: string | null;
  summary: string;
  reason: string | null;
  status: string;
  feedback: "POSITIVE" | "NEGATIVE" | null;
  created_at: string;
};

export type DashboardStats = {
  messages_today: number;
  prefiltered_today: number;
  ai_checked_today: number;
  leads_today: number;
  hot_today: number;
  good_today: number;
  possible_today: number;
  confirmed_today: number;
};

export type PipelineStatus = {
  pending: number;
  retrying: number;
  failed: number;
  completed: number;
  notifications_pending: number;
  notifications_failed: number;
};

export type Settings = {
  minimum_notification_score: number;
  include_vacancies: boolean;
};

export type TelegramStatus = {
  configured: boolean;
  connected: boolean;
  status: string;
  phone: string | null;
  username: string | null;
  account_name: string | null;
};

export type TelegramChallenge = {
  auth_token: string;
  status: "CODE_REQUIRED" | "PASSWORD_REQUIRED" | "CONNECTED";
};

export type IntegrationStatus = {
  ai_configured: boolean;
  ai_provider: string;
  ai_model: string | null;
  notification_bot_configured: boolean;
};

export type NotificationBotStatus = {
  configured: boolean;
  bot_username: string | null;
  bot_name: string | null;
  chat_id: string | null;
  chat_title: string | null;
};

export type NotificationBotChat = {
  chat_id: string;
  title: string;
  type: string;
};

export type NotificationBotProbe = {
  bot_username: string | null;
  bot_name: string | null;
  chats: NotificationBotChat[];
};

export type DiscoveryQuery = {
  id: number;
  query: string;
  enabled: boolean;
  last_run_at: string | null;
  created_at: string;
};

export type DiscoveryRun = { queries_run: number; found: number; added: number };

export type SearchProfile = {
  id: number;
  name: string;
  description: string | null;
  enabled: boolean;
  categories: string[];
  positive_keywords: string[];
  negative_keywords: string[];
  min_score: number;
  include_vacancies: boolean;
  notification_enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type SearchProfileInput = Omit<SearchProfile, "id" | "created_at" | "updated_at">;
export type SourceAnalysis = { fetched: number; inserted: number; candidates: number; source_score: number };

export type TelegramDialog = {
  telegram_chat_id: number;
  title: string;
  username: string | null;
  participants_count: number | null;
  source_type: string;
  source_id: number | null;
  source_status: string | null;
  already_added: boolean;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string" ? body.detail : body.detail?.message ?? message;
    } catch { /* response is not JSON */ }
    throw new ApiError(response.status, message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  authStatus: () => request<{ authenticated: boolean }>("/api/auth/status"),
  login: (password: string) => request<{ authenticated: boolean }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ password }),
  }),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
  sources: () => request<Source[]>("/api/sources"),
  addSource: (url: string) =>
    request<Source>("/api/sources", { method: "POST", body: JSON.stringify({ url }) }),
  setSourceStatus: (id: number, action: "activate" | "pause") =>
    request<Source>(`/api/sources/${id}/${action}`, { method: "POST" }),
  joinSource: (id: number) =>
    request<Source>(`/api/sources/${id}/join`, { method: "POST" }),
  deleteSource: (id: number) =>
    request<void>(`/api/sources/${id}`, { method: "DELETE" }),
  leads: (params?: URLSearchParams) =>
    request<Lead[]>(`/api/leads${params?.size ? `?${params}` : ""}`),
  dashboard: () => request<DashboardStats>("/api/dashboard"),
  pipelineStatus: () => request<PipelineStatus>("/api/dashboard/pipeline"),
  feedback: (id: number, feedback: "POSITIVE" | "NEGATIVE") =>
    request(`/api/leads/${id}/feedback`, {
      method: "POST",
      body: JSON.stringify({ feedback }),
    }),
  draftResponse: (id: number) =>
    request<{ draft: string; generated_at: string; auto_sent: false }>(`/api/leads/${id}/draft-response`, { method: "POST" }),
  analyzeSource: (id: number, limit: 100 | 500 | 1000) =>
    request<SourceAnalysis>(`/api/sources/${id}/analyze`, { method: "POST", body: JSON.stringify({ limit }) }),
  telegramDialogs: () => request<TelegramDialog[]>("/api/sources/telegram-dialogs"),
  importTelegramDialog: (telegram_chat_id: number) =>
    request<Source>("/api/sources/import-dialog", { method: "POST", body: JSON.stringify({ telegram_chat_id }) }),
  discoveryQueries: () => request<DiscoveryQuery[]>("/api/discovery/queries"),
  addDiscoveryQuery: (query: string) => request<DiscoveryQuery>("/api/discovery/queries", { method: "POST", body: JSON.stringify({ query }) }),
  updateDiscoveryQuery: (id: number, payload: Partial<Pick<DiscoveryQuery, "query" | "enabled">>) => request<DiscoveryQuery>(`/api/discovery/queries/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteDiscoveryQuery: (id: number) => request<void>(`/api/discovery/queries/${id}`, { method: "DELETE" }),
  runDiscovery: () => request<DiscoveryRun>("/api/discovery/run", { method: "POST" }),
  discoveryResults: () => request<Source[]>("/api/discovery/results"),
  clearDiscoveryResults: () => request<void>("/api/discovery/results", { method: "DELETE" }),
  searchProfiles: () => request<SearchProfile[]>("/api/search-profiles"),
  addSearchProfile: (payload: SearchProfileInput) => request<SearchProfile>("/api/search-profiles", { method: "POST", body: JSON.stringify(payload) }),
  updateSearchProfile: (id: number, payload: Partial<SearchProfileInput>) => request<SearchProfile>(`/api/search-profiles/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteSearchProfile: (id: number) => request<void>(`/api/search-profiles/${id}`, { method: "DELETE" }),
  settings: () => request<Settings>("/api/settings"),
  updateSettings: (payload: Partial<Settings>) =>
    request<Settings>("/api/settings", { method: "PATCH", body: JSON.stringify(payload) }),
  telegramStatus: () => request<TelegramStatus>("/api/telegram/status"),
  telegramConfigure: (api_id: number, api_hash: string) =>
    request<TelegramStatus>("/api/telegram/configure", {
      method: "POST",
      body: JSON.stringify({ api_id, api_hash }),
    }),
  telegramAuthStart: (phone: string) =>
    request<TelegramChallenge>("/api/telegram/auth/start", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),
  telegramAuthCode: (auth_token: string, code: string) =>
    request<TelegramChallenge>("/api/telegram/auth/code", {
      method: "POST",
      body: JSON.stringify({ auth_token, code }),
    }),
  telegramAuthPassword: (auth_token: string, password: string) =>
    request<TelegramChallenge>("/api/telegram/auth/password", {
      method: "POST",
      body: JSON.stringify({ auth_token, password }),
    }),
  telegramDisconnect: () =>
    request<void>("/api/telegram/disconnect", { method: "POST" }),
  integrationStatus: () => request<IntegrationStatus>("/api/settings/integrations"),
  notificationBotStatus: () => request<NotificationBotStatus>("/api/settings/notification-bot"),
  probeNotificationBot: (token: string) => request<NotificationBotProbe>("/api/settings/notification-bot/probe", {
    method: "POST",
    body: JSON.stringify({ token }),
  }),
  configureNotificationBot: (token: string, chat_id: string) => request<NotificationBotStatus>("/api/settings/notification-bot", {
    method: "POST",
    body: JSON.stringify({ token, chat_id }),
  }),
  disconnectNotificationBot: () => request<void>("/api/settings/notification-bot", { method: "DELETE" }),
};
