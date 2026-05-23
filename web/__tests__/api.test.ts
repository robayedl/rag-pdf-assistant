import { chat, listDocs, uploadDoc } from "@/lib/api";

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
      { doc_id: "abc", filename: "test.pdf", uploaded_at: "2024-01-01T00:00:00Z", indexed: true },
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
  it("posts a multipart form and returns upload response", async () => {
    const resp = { doc_id: "xyz", filename: "paper.pdf" };
    mockFetch(resp);
    const file = new File(["content"], "paper.pdf", { type: "application/pdf" });
    const result = await uploadDoc(file);
    expect(result.doc_id).toBe("xyz");
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
});
