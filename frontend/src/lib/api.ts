const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000/api").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}/${path.replace(/^\/+/, "")}`;
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(url, { ...options, headers });
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message)) ||
      `${res.status} ${res.statusText}`;
    throw new ApiError(typeof msg === "string" ? msg : JSON.stringify(msg), res.status);
  }
  return data as T;
}

export function getExportUrl(path: string): string {
  return `${API_BASE}/${path.replace(/^\/+/, "")}`;
}

export const api = {
  // Health & Settings
  health: () => apiRequest("/health"),
  getSettings: () => apiRequest("/settings"),
  updateSettings: (payload: Record<string, unknown>) =>
    apiRequest("/settings", { method: "PUT", body: JSON.stringify(payload) }),

  // Analytics & Dashboard
  getAnalyticsOverview: (days = 30, campaignId?: number) => {
    const params = new URLSearchParams({ days: String(days) });
    if (campaignId) params.set("campaign_id", String(campaignId));
    return apiRequest(`/analytics/overview?${params.toString()}`);
  },

  // Websites
  getWebsitesSummary: () => apiRequest("/websites"),
  listWebsites: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== "all") qs.set(k, String(v));
    });
    return apiRequest(`/websites/list?${qs.toString()}`);
  },
  addWebsite: (url: string) =>
    apiRequest("/websites", { method: "POST", body: JSON.stringify({ url }) }),
  bulkImportWebsites: (urls: string[]) =>
    apiRequest("/websites/bulk", { method: "POST", body: JSON.stringify({ urls }) }),
  importWebsitesCsv: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest("/websites/import-csv", { method: "POST", body: fd });
  },
  getWebsiteDetails: (id: number) => apiRequest(`/websites/${id}`),
  scanWebsite: (id: number) => apiRequest(`/websites/${id}/scan`, { method: "POST" }),
  startBatchScan: (mode: "pending" | "pending_and_noform" | "all", limit?: number, concurrency = 3) => {
    const qs = new URLSearchParams({ mode, concurrency: String(concurrency) });
    if (limit) qs.set("limit", String(limit));
    return apiRequest(`/websites/batch-scan?${qs.toString()}`, { method: "POST" });
  },
  getBatchScanStatus: () => apiRequest("/websites/batch-scan/status"),
  stopBatchScan: () => apiRequest("/websites/batch-scan/stop", { method: "POST" }),
  updateWebsiteField: (websiteId: number, fieldId: number, clusterKey: string) =>
    apiRequest(`/websites/${websiteId}/fields/${fieldId}`, {
      method: "PATCH",
      body: JSON.stringify({ cluster_key: clusterKey }),
    }),
  deleteWebsite: (id: number) => apiRequest(`/websites/${id}`, { method: "DELETE" }),

  // Campaigns
  listCampaigns: (params?: { search?: string; status?: string; sort_by?: string }) => {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.status && params.status !== "all") qs.set("status", params.status);
    if (params?.sort_by) qs.set("sort_by", params.sort_by);
    return apiRequest(`/campaigns?${qs.toString()}`);
  },
  createCampaign: (payload: Record<string, unknown>) =>
    apiRequest("/campaigns", { method: "POST", body: JSON.stringify(payload) }),
  updateCampaign: (id: number, payload: Record<string, unknown>) =>
    apiRequest(`/campaigns/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteCampaign: (id: number) => apiRequest(`/campaigns/${id}`, { method: "DELETE" }),
  duplicateCampaign: (id: number) => apiRequest(`/campaigns/${id}/duplicate`, { method: "POST" }),
  getCampaign: (id: number) => apiRequest(`/campaigns/${id}`),
  getCampaignStatus: (id: number) => apiRequest(`/campaigns/${id}/status`),
  startCampaign: (id: number) => apiRequest(`/campaigns/${id}/start`, { method: "POST" }),
  pauseCampaign: (id: number) => apiRequest(`/campaigns/${id}/pause`, { method: "POST" }),
  resumeCampaign: (id: number) => apiRequest(`/campaigns/${id}/resume`, { method: "POST" }),
  restartCampaign: (id: number) => apiRequest(`/campaigns/${id}/restart`, { method: "POST" }),
  cancelCampaign: (id: number) => apiRequest(`/campaigns/${id}/cancel`, { method: "POST" }),

  // Submissions
  listSubmissions: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== "all") qs.set(k, String(v));
    });
    return apiRequest(`/form-submissions?${qs.toString()}`);
  },

  // Fields & Random Values
  getFillFormTemplate: () => apiRequest("/fill-form-template"),
  getFieldFrequency: () => apiRequest("/field-frequency"),
  getFieldMappingSummary: () => apiRequest("/field-mapping"),
  listFieldMappingDetails: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== "all") qs.set(k, String(v));
    });
    return apiRequest(`/field-mappings/details?${qs.toString()}`);
  },
  updateFieldMapping: (normalized_label: string, canonical_concept: string) =>
    apiRequest("/field-mappings", {
      method: "PUT",
      body: JSON.stringify({ normalized_label, canonical_concept }),
    }),
  listRandomValues: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== "all") qs.set(k, String(v));
    });
    return apiRequest(`/random-values?${qs.toString()}`);
  },
  addRandomValue: (field_concept: string, value: string) =>
    apiRequest("/random-values", {
      method: "POST",
      body: JSON.stringify({ field_concept, value }),
    }),
  deleteRandomValue: (id: number) => apiRequest(`/random-values/${id}`, { method: "DELETE" }),
  importRandomValuesCsv: (fieldconcept: string, file: File) => {
    const fd = new FormData();
    fd.append("fieldconcept", fieldconcept);
    fd.append("csvfile", file);
    return apiRequest("/random-values/import-csv", { method: "POST", body: fd });
  },

  // Notifications
  listNotificationEmails: () => apiRequest("/notification-emails"),
  addNotificationEmail: (email: string) =>
    apiRequest("/notification-emails", { method: "POST", body: JSON.stringify({ email }) }),
  deleteNotificationEmail: (id: number) =>
    apiRequest(`/notification-emails/${id}`, { method: "DELETE" }),
  toggleNotificationEmail: (id: number) =>
    apiRequest(`/notification-emails/${id}`, { method: "PATCH" }),
  getEmailConfig: () => apiRequest("/email-config"),
  updateEmailConfig: (payload: Record<string, unknown>) =>
    apiRequest("/email-config", { method: "POST", body: JSON.stringify(payload) }),
  sendTestEmail: () => apiRequest("/test-email", { method: "POST" }),
};
