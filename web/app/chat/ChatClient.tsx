"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  SendIcon, Loader2Icon, BotIcon, UserIcon,
  PlusIcon, Trash2Icon, MessageSquareIcon, CopyIcon, CheckIcon,
  PanelRightOpenIcon, PanelRightCloseIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { useAuth } from "@clerk/nextjs";
import { chat, Citation, Doc, getDocFileUrl, listDocs } from "@/lib/api";
import {
  ChatSession,
  StoredMessage,
  createSession,
  deleteSession,
  loadSessions,
  upsertSession,
} from "@/lib/chat-storage";
import dynamic from "next/dynamic";

// Lazy-load PdfPane to avoid SSR issues with pdfjs
const PdfPane = dynamic(() => import("@/components/PdfPane"), { ssr: false });

interface LiveMessage extends StoredMessage {
  status?: string;
  streaming?: boolean;
}

interface ActivePdf {
  url: string;
  page: number;
  snippet: string;
  jumpKey: number;
}

function uid() {
  return Math.random().toString(36).slice(2);
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function ChatClient() {
  const router = useRouter();
  const params = useSearchParams();
  const docParam = params.get("doc");
  const sessionParam = params.get("session");
  const { getToken, isLoaded, isSignedIn, userId } = useAuth();
  const authTokenRef = useRef<string | undefined>(undefined);

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [messages, setMessages] = useState<LiveMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [newChatOpen, setNewChatOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // PDF pane state
  const [pdfOpen, setPdfOpen] = useState(false);
  const [activePdf, setActivePdf] = useState<ActivePdf | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const cancelledRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeSessionRef = useRef<ChatSession | null>(null);
  const autoSaveRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    const init = async () => {
      const t = await getToken();
      authTokenRef.current = t ?? undefined;

      const saved = loadSessions(userId ?? "");
      setSessions(saved);

      try {
        const data = await listDocs(authTokenRef.current);
        const indexed = data.filter((d) => d.indexed);
        setDocs(indexed);

        if (docParam) {
          const doc = indexed.find((d) => d.doc_id === docParam);
          if (doc) {
            const session = createSession(doc.doc_id, doc.filename);
            setSessions((prev) => {
              const next = [session, ...prev];
              upsertSession(prev, session, userId ?? "");
              return next;
            });
            setActiveId(session.id);
            activeSessionRef.current = session;
            router.replace(`/chat?session=${session.id}`);
          }
        } else if (sessionParam) {
          const session = saved.find((s) => s.id === sessionParam);
          if (session) {
            setActiveId(session.id);
            activeSessionRef.current = session;
            setMessages(session.messages.map((m) => ({ ...m })));
          }
        }
      } catch {}
    };

    init();
  }, [isLoaded, isSignedIn]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const activeSession = sessions.find((s) => s.id === activeId) ?? null;

  function openSession(session: ChatSession) {
    if (streaming) abortRef.current?.abort();
    setStreaming(false);
    setActiveId(session.id);
    activeSessionRef.current = session;
    setMessages(session.messages.map((m) => ({ ...m })));
    router.replace(`/chat?session=${session.id}`);
  }

  function startNewChat(doc: Doc) {
    const session = createSession(doc.doc_id, doc.filename);
    setSessions((prev) => {
      const next = [session, ...prev];
      upsertSession(prev, session, userId ?? "");
      return next;
    });
    setActiveId(session.id);
    activeSessionRef.current = session;
    setMessages([]);
    setNewChatOpen(false);
    router.replace(`/chat?session=${session.id}`);
  }

  function removeSession(id: string, name: string) {
    if (!confirm(`Delete chat "${name}"? This cannot be undone.`)) return;
    setSessions((prev) => deleteSession(prev, id, userId ?? ""));
    if (activeId === id) {
      setActiveId(null);
      activeSessionRef.current = null;
      setMessages([]);
      router.replace("/chat");
    }
  }

  // Open the PDF pane for a specific citation (fetches PDF as authenticated blob URL)
  async function openCitation(citation: Citation, docId: string) {
    const rawUrl = getDocFileUrl(docId);
    const freshToken = await getToken();
    authTokenRef.current = freshToken ?? undefined;
    const token = authTokenRef.current;
    const load = token
      ? fetch(rawUrl, { headers: { Authorization: `Bearer ${token}` } })
          .then((r) => r.blob())
          .then((b) => URL.createObjectURL(b))
      : Promise.resolve(rawUrl);

    load.then((url) => {
      setActivePdf((prev) => ({
        url,
        page: citation.page > 0 ? citation.page : 1,
        snippet: citation.text ?? "",
        jumpKey: (prev?.jumpKey ?? 0) + 1,
      }));
      setPdfOpen(true);
    });
  }

  const persistMessages = useCallback(
    (msgs: StoredMessage[]) => {
      const session = activeSessionRef.current;
      if (!session) return;
      const updated: ChatSession = {
        ...session,
        messages: msgs,
        updated_at: new Date().toISOString(),
      };
      activeSessionRef.current = updated;
      setSessions((prev) => upsertSession(prev, updated, userId ?? ""));
    },
    [userId]
  );

  const debouncedPersist = useCallback(
    (msgs: StoredMessage[]) => {
      if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
      autoSaveRef.current = setTimeout(() => persistMessages(msgs), 600);
    },
    [persistMessages]
  );

  const updateLast = useCallback(
    (updater: (msg: LiveMessage) => LiveMessage) => {
      setMessages((prev) => {
        if (prev.length === 0) return prev;
        const next = [...prev];
        next[next.length - 1] = updater(next[next.length - 1]);
        return next;
      });
    },
    []
  );

  function toStored(msgs: LiveMessage[]): StoredMessage[] {
    return msgs.map(({ status: _s, streaming: _st, ...rest }) => rest);
  }

  function friendlyError(err: string): string {
    if (err.includes("404") || err.toLowerCase().includes("not found"))
      return "Document not found. It may have been deleted.";
    if (err.includes("401") || err.includes("403"))
      return "Access denied. Check your API key.";
    if (err.includes("fetch") || err.includes("network"))
      return "Cannot reach the API. Is the backend running?";
    return err;
  }

  function stop() {
    cancelledRef.current = true;
    abortRef.current?.abort();
    if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
    setStreaming(false);
    setMessages((prev) => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      const last = next[next.length - 1];
      if (last.role === "assistant" && last.streaming) {
        next[next.length - 1] = { ...last, streaming: false, status: undefined, interrupted: true };
        persistMessages(toStored(next));
      }
      return next;
    });
  }

  async function send() {
    const question = input.trim();
    if (!question || !activeSession || streaming) return;

    cancelledRef.current = false;
    setInput("");
    setStreaming(true);

    const freshToken = await getToken();
    authTokenRef.current = freshToken ?? undefined;

    const userMsg: LiveMessage = { id: uid(), role: "user", content: question };
    const assistantMsg: LiveMessage = {
      id: uid(), role: "assistant", content: "", streaming: true, status: "Thinking…",
    };

    setMessages((prev) => {
      const next = [...prev, userMsg, assistantMsg];
      persistMessages(toStored([...next.slice(0, -1), { ...assistantMsg, interrupted: true }]));
      return next;
    });

    abortRef.current = new AbortController();

    chat(
      { doc_id: activeSession.doc_id, question, session_id: activeSession.id },
      authTokenRef.current,
      (msg) => { if (!cancelledRef.current) updateLast((m) => ({ ...m, status: msg })); },
      (token) => {
        if (cancelledRef.current) return;
        setMessages((prev) => {
          if (prev.length === 0) return prev;
          const next = [...prev];
          next[next.length - 1] = {
            ...next[next.length - 1],
            content: next[next.length - 1].content + token,
            status: undefined,
          };
          debouncedPersist(toStored(next));
          return next;
        });
      },
      (citations) => { if (!cancelledRef.current) updateLast((m) => ({ ...m, citations })); },
      (duration_ms) => {
        if (cancelledRef.current) return;
        if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
        setMessages((prev) => {
          const next = prev.map((m, i) =>
            i === prev.length - 1
              ? { ...m, streaming: false, status: undefined, duration_ms }
              : m
          );
          persistMessages(toStored(next));
          return next;
        });
        setStreaming(false);
      },
      (err) => {
        if (cancelledRef.current) return;
        if (autoSaveRef.current) clearTimeout(autoSaveRef.current);
        const msg = friendlyError(err);
        setMessages((prev) => {
          const next = prev.map((m, i) =>
            i === prev.length - 1
              ? { ...m, content: msg, streaming: false, status: undefined }
              : m
          );
          persistMessages(toStored(next));
          return next;
        });
        setStreaming(false);
      },
      abortRef.current.signal
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-border flex flex-col bg-background/50">
        <div className="p-3 border-b border-border">
          <Button size="sm" className="w-full gap-1.5" onClick={() => setNewChatOpen(true)}>
            <PlusIcon className="size-3.5" />
            New Chat
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 ? (
            <p className="text-xs text-muted-foreground p-4 text-center">
              No chats yet. Start one above.
            </p>
          ) : (
            <div className="p-2 flex flex-col gap-0.5">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`group relative rounded-lg px-3 py-2.5 cursor-pointer transition-colors ${
                    s.id === activeId
                      ? "bg-primary/15 text-foreground"
                      : "hover:bg-accent/50 text-muted-foreground hover:text-foreground"
                  }`}
                  onClick={() => openSession(s)}
                >
                  <p className="text-xs font-medium truncate pr-5">{s.doc_name}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {s.messages.length > 0
                      ? s.messages[s.messages.length - 1].content.slice(0, 40) + "…"
                      : relativeTime(s.created_at)}
                  </p>
                  <button
                    className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-opacity"
                    onClick={(e) => { e.stopPropagation(); removeSession(s.id, s.doc_name); }}
                    title="Delete chat"
                  >
                    <Trash2Icon className="size-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Chat area */}
      <div className={`flex flex-col overflow-hidden transition-all duration-300 ${pdfOpen ? "flex-1" : "flex-1"}`}>
        {!activeSession ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4 text-muted-foreground">
            <MessageSquareIcon className="size-10 opacity-20" />
            <p className="text-sm">Select a chat or start a new one.</p>
            <Button size="sm" onClick={() => setNewChatOpen(true)}>
              <PlusIcon className="size-3.5 mr-1.5" />
              New Chat
            </Button>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="border-b border-border px-4 h-12 flex items-center gap-2 shrink-0 bg-background/80 backdrop-blur-sm">
              <span className="text-sm font-medium truncate text-muted-foreground flex-1">
                {activeSession.doc_name}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 shrink-0"
                onClick={() => {
                  if (!pdfOpen) {
                    // Open to show placeholder if no citation loaded yet
                    setPdfOpen(true);
                  } else {
                    setPdfOpen(false);
                  }
                }}
                title={pdfOpen ? "Close PDF pane" : "Open PDF pane"}
              >
                {pdfOpen
                  ? <PanelRightCloseIcon className="size-4" />
                  : <PanelRightOpenIcon className="size-4" />
                }
              </Button>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full min-h-[40vh] text-muted-foreground gap-2">
                  <p className="text-sm font-medium text-foreground">{activeSession.doc_name}</p>
                  <p className="text-xs">Ask anything about this document.</p>
                </div>
              ) : (
                <div className="max-w-3xl mx-auto flex flex-col gap-6">
                  <AnimatePresence initial={false}>
                    {messages.map((msg) => (
                      <motion.div
                        key={msg.id}
                        initial={{ opacity: 0, y: 12 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.2, ease: "easeOut" as const }}
                        className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
                      >
                        <Avatar className="size-7 shrink-0 mt-0.5">
                          <AvatarFallback className={`text-[10px] ${msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-red-500/15 text-red-400"}`}>
                            {msg.role === "user"
                              ? <UserIcon className="size-3.5" />
                              : <BotIcon className="size-3.5" />
                            }
                          </AvatarFallback>
                        </Avatar>

                        <div className={`flex flex-col gap-1 max-w-[80%] ${msg.role === "user" ? "items-end" : "items-start"}`}>
                          <div className={`group/msg flex items-end gap-1.5 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
                            <div
                              className={`rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap break-words ${
                                msg.role === "user"
                                  ? "bg-primary text-primary-foreground rounded-tr-sm"
                                  : "bg-card border border-border rounded-tl-sm"
                              }`}
                            >
                              {msg.status && !msg.content ? (
                                <span className="flex items-center gap-2 text-muted-foreground italic text-xs">
                                  <Loader2Icon className="size-3 animate-spin shrink-0" />
                                  {msg.status}
                                </span>
                              ) : (
                                <>
                                  {msg.content || (msg.interrupted && !msg.streaming
                                    ? <span className="italic text-muted-foreground text-xs">Response interrupted. Try asking again.</span>
                                    : null
                                  )}
                                  {msg.streaming && msg.content && (
                                    <span className="inline-block w-0.5 h-3.5 bg-current ml-0.5 animate-pulse rounded-full align-middle" />
                                  )}
                                  {msg.streaming && !msg.content && (
                                    <Loader2Icon className="size-3 animate-spin text-muted-foreground" />
                                  )}
                                  {msg.interrupted && msg.content && !msg.streaming && (
                                    <span className="block text-[10px] text-muted-foreground/60 mt-1 italic">— interrupted</span>
                                  )}
                                </>
                              )}
                            </div>
                            {msg.content && !msg.streaming && (
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(msg.content);
                                  setCopiedId(msg.id);
                                  setTimeout(() => setCopiedId((prev) => prev === msg.id ? null : prev), 2000);
                                }}
                                className="shrink-0 mb-1 opacity-0 group-hover/msg:opacity-100 transition-opacity p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent"
                                title="Copy"
                              >
                                {copiedId === msg.id
                                  ? <CheckIcon className="size-3 text-green-400" />
                                  : <CopyIcon className="size-3" />}
                              </button>
                            )}
                          </div>

                          {msg.citations && msg.citations.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 px-1">
                              {msg.citations.map((c: Citation, i: number) => (
                                <button
                                  key={i}
                                  title={c.text ?? `Page ${c.page}`}
                                  onClick={() => void openCitation(c, activeSession.doc_id)}
                                  className="text-[10px] bg-primary/15 hover:bg-primary/30 text-primary px-2 py-0.5 rounded-full cursor-pointer border border-primary/20 hover:border-primary/50 transition-colors active:scale-95"
                                >
                                  p.{c.page}
                                </button>
                              ))}
                            </div>
                          )}

                          {msg.duration_ms !== undefined && (
                            <span className="text-[10px] text-muted-foreground/60 px-1">
                              Answered in {(msg.duration_ms / 1000).toFixed(1)}s
                            </span>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  <div ref={bottomRef} />
                </div>
              )}
            </div>

            {/* Input */}
            <div className="border-t border-border px-4 py-3 shrink-0 bg-background/80 backdrop-blur-sm">
              <form
                className="max-w-3xl mx-auto flex gap-2"
                onSubmit={(e) => { e.preventDefault(); void send(); }}
              >
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={`Ask about ${activeSession.doc_name}…`}
                  disabled={streaming}
                  className="flex-1"
                />
                {streaming ? (
                  <Button
                    type="button"
                    size="icon-lg"
                    variant="destructive"
                    onClick={stop}
                    title="Stop generating"
                  >
                    <span className="block size-3 bg-current" />
                  </Button>
                ) : (
                  <Button type="submit" size="icon-lg" disabled={!input.trim()}>
                    <SendIcon />
                  </Button>
                )}
              </form>
            </div>
          </>
        )}
      </div>

      {/* PDF Pane */}
      <AnimatePresence>
        {pdfOpen && (
          <motion.div
            key="pdf-pane"
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: "50%", opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="shrink-0 border-l border-border flex flex-col overflow-hidden bg-background"
            style={{ minWidth: 0 }}
          >
            <PdfPane
              url={activePdf?.url ?? null}
              targetPage={activePdf?.page ?? 1}
              snippet={activePdf?.snippet ?? ""}
              jumpKey={activePdf?.jumpKey ?? 0}
              onClose={() => setPdfOpen(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* New Chat dialog */}
      <Dialog open={newChatOpen} onOpenChange={setNewChatOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Choose a document</DialogTitle>
          </DialogHeader>
          {docs.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No indexed documents. Upload one in Documents first.
            </p>
          ) : (
            <div className="flex flex-col gap-1 max-h-72 overflow-y-auto">
              {docs.map((doc) => (
                <button
                  key={doc.doc_id}
                  className="text-left px-4 py-3 rounded-lg hover:bg-accent/50 transition-colors text-sm"
                  onClick={() => startNewChat(doc)}
                >
                  <p className="font-medium truncate">{doc.filename}</p>
                  <p className="text-[10px] text-muted-foreground font-mono break-all select-all">{doc.doc_id}</p>
                </button>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
