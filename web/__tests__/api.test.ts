import { chat, getDocStatus, getMyUsage, listDocs, uploadDoc } from "@/lib/api";

function mockFetch(body: unknown, ok = true, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
    body: null,
  });
}

describe("listDocs", () => {
  it("returns parsed JSON on success", async () => {
    const docs = [
      {
        doc_id: "abc",
        filename: "test.pdf",
        uploaded_at: "2024-01-01T00:00:00Z",
        status: "indexed",
        indexed: true,
        progress_percent: 100,
      },
    ];
    mockFetch(docs);
    const result = await listDocs();
    expect(result).toEqual(docs);
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/documents");
  });

  it("throws on non-ok response", async () => {
    mockFetch({}, false, 500);
    await expect(listDocs()).rejects.toThrow("Failed to fetch documents");
  });
});

describe("uploadDoc", () => {
  it("posts a multipart form and returns upload response with status", async () => {
    const resp = { doc_id: "xyz", filename: "paper.pdf", status: "pending" };
    mockFetch(resp);
    const file = new File(["content"], "paper.pdf", { type: "application/pdf" });
    const result = await uploadDoc(file);
    expect(result.doc_id).toBe("xyz");
    expect(result.status).toBe("pending");
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[1].method).toBe("POST");
    expect(call[1].body).toBeInstanceOf(FormData);
  });

  it("throws on failure", async () => {
    mockFetch({}, false, 422);
    const file = new File(["x"], "x.pdf", { type: "application/pdf" });
    await expect(uploadDoc(file)).rejects.toThrow("Upload failed");
  });
});

describe("getDocStatus", () => {
  it("returns status response for a doc", async () => {
    const resp = { status: "processing", progress_percent: 42, page_count: null };
    mockFetch(resp);
    const result = await getDocStatus("doc-123");
    expect(result.status).toBe("processing");
    expect(result.progress_percent).toBe(42);
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/documents/doc-123/status");
  });

  it("sends auth header when token provided", async () => {
    mockFetch({ status: "indexed", progress_percent: 100, page_count: 5 });
    await getDocStatus("doc-abc", "tok_123");
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[1].headers).toMatchObject({ Authorization: "Bearer tok_123" });
  });

  it("throws on non-ok response", async () => {
    mockFetch({}, false, 404);
    await expect(getDocStatus("missing")).rejects.toThrow("Failed to fetch document status");
  });
});

describe("chat", () => {
  it("posts to /query/stream with correct body", () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500, body: null });
    const ctrl = new AbortController();
    chat(
      { doc_id: "abc", question: "What is this?", session_id: "sess1" },
      undefined,
      () => {}, () => {}, () => {}, () => {},
      () => {},
      ctrl.signal
    );
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[0]).toContain("/query/stream");
    expect(call[1].method).toBe("POST");
    expect(JSON.parse(call[1].body)).toMatchObject({
      doc_id: "abc",
      question: "What is this?",
      session_id: "sess1",
    });
  });

  it("calls onError with 429 sentinel when rate limited", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: { get: (h: string) => (h === "Retry-After" ? "3600" : null) },
      body: null,
    });
    const onError = jest.fn();
    chat(
      { doc_id: "abc", question: "hi" },
      undefined,
      () => {}, () => {}, () => {}, () => {},
      onError,
      undefined
    );
    await new Promise((r) => setTimeout(r, 50));
    expect(onError).toHaveBeenCalledWith("429:3600");
  });
});

describe("getMyUsage", () => {
  it("returns usage summary", async () => {
    const summary = { total_cost_usd: 0.0042, total_tokens: 1234 };
    mockFetch(summary);
    const result = await getMyUsage("tok_abc");
    expect(result.total_cost_usd).toBeCloseTo(0.0042);
    expect(result.total_tokens).toBe(1234);
    const call = (global.fetch as jest.Mock).mock.calls[0];
    expect(call[0]).toContain("/usage/me");
    expect(call[1].headers).toMatchObject({ Authorization: "Bearer tok_abc" });
  });

  it("throws on non-ok response", async () => {
    mockFetch({}, false, 500);
    await expect(getMyUsage()).rejects.toThrow("Failed to fetch usage");
  });
});
