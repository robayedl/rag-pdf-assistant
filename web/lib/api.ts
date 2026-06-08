const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Doc {
  doc_id: string;
  filename: string;
  uploaded_at: string;
  status: string;
  indexed: boolean;
  source_type?: string;
  index_time_s?: number;
  page_count?: number;
  progress_percent: number;
  step?: string;
  ingestion_cost_usd?: number;
  ingestion_tokens?: number;
}

export interface UploadResponse {
  doc_id: string;
  filename: string;
  status: string;
  source_type?: string;
}

export interface DocStatusResponse {
  status: string;
  progress_percent: number;
  page_count?: number;
  step?: string;
}

export interface IndexResponse {
  doc_id: string;
  chunks_indexed: number;
  collection: string;
}

export interface Citation {
  ref: string;
  page: number;
  chunk_id: number;
  source: string;
  text?: string;
}

export interface ChatParams {
  doc_id: string;
  question: string;
  session_id?: string;
}

export interface UsageEvent {
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

export type UsagePeriod = "1h" | "24h" | "7d" | "30d" | "all";

export interface UsageSummary {
  total_cost_usd: number;
  total_tokens: number;
}

export interface UsageHistoryPoint {
  bucket: string;
  tokens: number;
  requests: number;
  cost_usd: number;
}

export interface UsageHistory {
  points: UsageHistoryPoint[];
}

export interface MetaEvent {
  hyde_triggered: boolean;
  pii_redacted: boolean;
  from_cache?: boolean;
}

export const USD_TO_AUD = 1.57;

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  created_at?: string;
}

export async function fetchConversation(sessionId: string, token?: string): Promise<ConversationMessage[]> {
  try {
    const res = await fetch(`${API_URL}/conversations/${sessionId}`, {
      headers: authHeaders(token),
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export async function getMyUsage(token?: string, period: UsagePeriod = "30d"): Promise<UsageSummary> {
  const res = await fetch(`${API_URL}/usage/me?period=${period}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to fetch usage");
  return res.json();
}

export async function getMyUsageHistory(token?: string, period: UsagePeriod = "30d"): Promise<UsageHistory> {
  const res = await fetch(`${API_URL}/usage/me/history?period=${period}`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to fetch usage history");
  return res.json();
}

function authHeaders(token?: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function listDocs(token?: string): Promise<Doc[]> {
  const res = await fetch(`${API_URL}/documents`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to fetch documents");
  return res.json();
}

export async function uploadDoc(file: File, token?: string): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/documents`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
}

export async function deleteDoc(docId: string, token?: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${docId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to delete document");
}

export async function stopDoc(docId: string, token?: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${docId}/stop`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to stop document");
}

export async function reindexDoc(docId: string, token?: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${docId}/reindex`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to reindex document");
}

export async function getDocStatus(docId: string, token?: string): Promise<DocStatusResponse> {
  const res = await fetch(`${API_URL}/documents/${docId}/status`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to fetch document status");
  return res.json();
}

export function indexDocStream(
  docId: string,
  token: string | undefined,
  onStatus: (msg: string) => void,
  onDone: (chunks: number, index_time_s: number) => void,
  onError: (err: string) => void,
  signal?: AbortSignal
): void {
  fetch(`${API_URL}/documents/${docId}/index/stream`, {
    method: "POST",
    headers: authHeaders(token),
    signal,
  })
    .then(async (res) => {
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      if (!res.body) throw new Error("No response body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const match = part.match(/^event: (\w+)\ndata: ([\s\S]*)$/);
          if (!match) continue;
          const [, event, data] = match;
          if (event === "status") onStatus(data);
          else if (event === "done") {
            try {
              const { chunks, index_time_s } = JSON.parse(data);
              onDone(chunks, index_time_s);
            } catch { onDone(0, 0); }
          } else if (event === "error") onError(data);
        }
      }
    })
    .catch((err) => {
      if (err?.name !== "AbortError") onError(String(err));
    });
}

export function getDocFileUrl(docId: string, token?: string): string {
  // Token is passed as query param for direct PDF loading in iframe/react-pdf
  const url = `${API_URL}/documents/${docId}/file`;
  return token ? `${url}?token=${encodeURIComponent(token)}` : url;
}

export function getDocDownloadUrl(docId: string): string {
  return `${API_URL}/documents/${docId}/download`;
}

export interface ApiKeyRecord {
  id: string;
  name: string;
  created_at: string;
  last_used_at?: string | null;
}

export interface ApiKeyCreated extends ApiKeyRecord {
  key: string;
}

export async function listApiKeys(token?: string): Promise<ApiKeyRecord[]> {
  const res = await fetch(`${API_URL}/api-keys`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error("Failed to fetch API keys");
  return res.json();
}

export async function createApiKey(name: string, token?: string): Promise<ApiKeyCreated> {
  const res = await fetch(`${API_URL}/api-keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("Failed to create API key");
  return res.json();
}

export async function revokeApiKey(keyId: string, token?: string): Promise<void> {
  const res = await fetch(`${API_URL}/api-keys/${keyId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Failed to revoke API key");
}

export function chat(
  params: ChatParams,
  token: string | undefined,
  onStatus: (msg: string) => void,
  onToken: (token: string) => void,
  onCitations: (citations: Citation[]) => void,
  onDone: (duration_ms: number) => void,
  onError: (err: string) => void,
  signal?: AbortSignal,
  onUsage?: (usage: UsageEvent) => void,
  onMeta?: (meta: MetaEvent) => void,
  onPii?: () => void
): void {
  const startTime = Date.now();
  fetch(`${API_URL}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify(params),
    signal,
  })
    .then(async (res) => {
      if (res.status === 429) {
        const retryAfter = res.headers.get("Retry-After");
        onError(`429:${retryAfter ?? "0"}`);
        return;
      }
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let doneFired = false;

      const dispatchPart = (part: string) => {
        const match = part.match(/^event: (\w+)\ndata: ([\s\S]*)$/);
        if (!match) return;
        const [, event, data] = match;
        if (event === "status") onStatus(data);
        else if (event === "token") onToken(data);
        else if (event === "citations") {
          try { onCitations(JSON.parse(data)); } catch { }
        } else if (event === "usage") {
          try { if (onUsage) onUsage(JSON.parse(data)); } catch { }
        } else if (event === "meta") {
          try { if (onMeta) onMeta(JSON.parse(data)); } catch { }
        } else if (event === "pii") {
          if (onPii) onPii();
        } else if (event === "done") {
          if (!doneFired) { doneFired = true; onDone(Date.now() - startTime); }
        } else if (event === "error") onError(data);
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) dispatchPart(part);
      }

      // Flush any remaining data not terminated by \n\n
      if (buf.trim()) dispatchPart(buf.trim());
      // Fallback: if stream closed without a done event (e.g. clean TCP close)
      if (!doneFired) onDone(Date.now() - startTime);
    })
    .catch((err) => {
      if (err?.name !== "AbortError") onError(String(err));
    });
}
