"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  UploadIcon,
  FileTextIcon,
  MessageSquareIcon,
  Loader2Icon,
  DatabaseIcon,
  Trash2Icon,
  CheckCircle2Icon,
  XCircleIcon,
  StopCircleIcon,
  RefreshCwIcon,
  CloudUploadIcon,
  CopyIcon,
} from "lucide-react";
import Nav from "@/components/nav";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@clerk/nextjs";
import { Doc, deleteDoc, listDocs, reindexDoc, stopDoc, uploadDoc } from "@/lib/api";
import { cn } from "@/lib/utils";

// Statuses that mean a background job is running or queued
const ACTIVE_STATUSES = new Set(["pending", "processing"]);

// Steps shown during ingestion — weights sum to 100 %
const INGEST_STEPS = [
  { label: "Queued",      doneLabel: "Queued",      weight: 5,  threshold: 0  },
  { label: "Parsing",     doneLabel: "Parsed",      weight: 65, threshold: 5  },
  { label: "Extracting",  doneLabel: "Extracted",   weight: 10, threshold: 70 },
  { label: "Embedding",   doneLabel: "Embedded",    weight: 18, threshold: 80 },
  { label: "Finalizing",  doneLabel: "Finalized",   weight: 2,  threshold: 98 },
] as const;

function getCurrentStepIdx(pct: number): number {
  for (let i = INGEST_STEPS.length - 1; i >= 0; i--) {
    if (pct >= INGEST_STEPS[i].threshold) return i;
  }
  return 0;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

// ── Status badge ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "indexed":
      return (
        <span className="inline-flex items-center gap-1 text-emerald-400 text-xs">
          <CheckCircle2Icon className="size-3" /> Ready
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 text-destructive text-xs">
          <XCircleIcon className="size-3" /> Failed
        </span>
      );
    case "stopped":
      return (
        <span className="inline-flex items-center gap-1 text-orange-400 text-xs">
          <StopCircleIcon className="size-3" /> Stopped
        </span>
      );
    case "processing":
      return (
        <span className="inline-flex items-center gap-1 text-blue-400 text-xs">
          <Loader2Icon className="size-3 animate-spin" /> Processing
        </span>
      );
    case "uploading":
      return (
        <span className="inline-flex items-center gap-1 text-muted-foreground text-xs">
          <Loader2Icon className="size-3 animate-spin" /> Uploading
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 text-yellow-400 text-xs">
          <DatabaseIcon className="size-3" /> Queued
        </span>
      );
  }
}

// ── Smooth progress (bar + percentage counter share one animated value) ───────

function useSmoothedValue(real: number): number {
  const [display, setDisplay] = useState(real);
  const ref = useRef(real);

  useEffect(() => { ref.current = display; });

  useEffect(() => {
    const id = setInterval(() => {
      const cur = ref.current;
      if (cur < real) {
        const next = Math.min(cur + 0.5, real);
        ref.current = next;
        setDisplay(next);
        return;
      }
      // Creep toward next threshold - 1 while waiting for real progress
      const nextStep = INGEST_STEPS.find(s => s.threshold > real);
      const cap = nextStep ? nextStep.threshold - 1 : real;
      if (cur < cap) {
        const next = Math.min(cur + 0.06, cap);
        ref.current = next;
        setDisplay(next);
      }
    }, 80);
    return () => clearInterval(id);
  }, [real]);

  return display;
}

// One-line label + percentage, then bar on the line below
function StatusProgress({ status, value }: { status: string; value: number }) {
  const display = useSmoothedValue(value);
  const isUploading = status === "uploading";
  return (
    <div className="flex flex-col gap-1.5">
      {/* Top row: status icon + label + percentage — all on one line */}
      <div style={{ display: "flex", alignItems: "center", width: "100%" }}>
        <Loader2Icon className="size-3 animate-spin text-blue-400 shrink-0" />
        <span className="text-blue-400 text-xs ml-1">
          {isUploading ? "Uploading" : "Processing"}
        </span>
        {!isUploading && (
          <span className="text-xs text-muted-foreground tabular-nums" style={{ marginLeft: "auto" }}>
            {Math.floor(display)}%
          </span>
        )}
      </div>
      {/* Bar */}
      <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${display}%` }}
        />
      </div>
    </div>
  );
}

// ── Steps breakdown ──────────────────────────────────────────────────────────

function StepsBreakdown({ progress, status }: { progress: number; status: string }) {
  const currentIdx = getCurrentStepIdx(progress);
  const stopped = status === "stopped" || status === "failed";
  return (
    <div className="flex items-center flex-wrap gap-0.5 pt-0.5">
      {INGEST_STEPS.map((s, i) => {
        const done = i < currentIdx;
        const active = i === currentIdx;
        const labelColor = done
          ? "text-emerald-400"
          : active && stopped
          ? "text-red-400"
          : active
          ? "text-yellow-400"
          : "text-muted-foreground/35";
        const arrowColor = done ? "text-emerald-500/60" : "text-muted-foreground/25";
        return (
          <span key={s.label} className="flex items-center gap-0.5">
            <span className={cn("text-[11px] leading-none font-medium", labelColor)}>
              {done ? `${s.doneLabel} ✓` : s.label}
            </span>
            {i < INGEST_STEPS.length - 1 && (
              <span className={cn("text-[11px] leading-none", arrowColor)}>→</span>
            )}
          </span>
        );
      })}
    </div>
  );
}

// ── Page component ────────────────────────────────────────────────────────────

export default function DocsPage() {
  const router = useRouter();
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [optimisticDoc, setOptimisticDoc] = useState<Doc | null>(null);
  const [stopping, setStopping] = useState<Set<string>>(new Set());
  const [reindexing, setReindexing] = useState<Set<string>>(new Set());
  const fileRef = useRef<HTMLInputElement>(null);
  const prevStatusRef = useRef<Record<string, string>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchDocs(silent = false) {
    try {
      const token = (await getToken()) ?? undefined;
      const fetched = await listDocs(token);

      fetched.forEach((doc) => {
        const prev = prevStatusRef.current[doc.doc_id];
        if (prev && prev !== doc.status) {
          if (doc.status === "indexed") toast.success(`"${doc.filename}" is ready.`);
          else if (doc.status === "failed") toast.error(`"${doc.filename}" failed to process.`);
          else if (doc.status === "stopped") toast.info(`"${doc.filename}" was stopped.`);
        }
        prevStatusRef.current[doc.doc_id] = doc.status;
      });

      setDocs(fetched);
    } catch {
      if (!silent) toast.error("Could not reach the API. Is the backend running?");
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    const hasActive = docs.some((d) => ACTIVE_STATUSES.has(d.status));
    if (hasActive && !pollRef.current) {
      pollRef.current = setInterval(() => fetchDocs(true), 2000);
    } else if (!hasActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {};
  }, [docs]);

  useEffect(() => {
    if (isLoaded && isSignedIn) fetchDocs();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [isLoaded, isSignedIn]);

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);

    // Optimistic "uploading" card
    const tempId = "__uploading__";
    setOptimisticDoc({
      doc_id: tempId,
      filename: selectedFile.name,
      uploaded_at: new Date().toISOString(),
      status: "uploading",
      indexed: false,
      progress_percent: 0,
    });
    setUploadOpen(false);
    setSelectedFile(null);

    try {
      const token = (await getToken()) ?? undefined;
      const uploaded = await uploadDoc(selectedFile, token);
      toast.success(`"${uploaded.filename}" queued for processing.`);
      await fetchDocs(true);
    } catch (err) {
      toast.error(String(err));
    } finally {
      setOptimisticDoc(null);
      setUploading(false);
    }
  }

  async function handleStop(doc: Doc) {
    setStopping((s) => new Set(s).add(doc.doc_id));
    try {
      const token = (await getToken()) ?? undefined;
      await stopDoc(doc.doc_id, token);
      await fetchDocs(true);
      toast.info(`"${doc.filename}" stopped.`);
    } catch (err) {
      toast.error(String(err));
    } finally {
      setStopping((s) => { const n = new Set(s); n.delete(doc.doc_id); return n; });
    }
  }

  async function handleReindex(doc: Doc) {
    setReindexing((s) => new Set(s).add(doc.doc_id));
    try {
      const token = (await getToken()) ?? undefined;
      await reindexDoc(doc.doc_id, token);
      await fetchDocs(true);
      toast.success(`"${doc.filename}" queued for reprocessing.`);
    } catch (err) {
      toast.error(String(err));
    } finally {
      setReindexing((s) => { const n = new Set(s); n.delete(doc.doc_id); return n; });
    }
  }

  async function handleDelete(doc: Doc) {
    if (!confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return;
    try {
      const token = (await getToken()) ?? undefined;
      await deleteDoc(doc.doc_id, token);
      delete prevStatusRef.current[doc.doc_id];
      setDocs((prev) => prev.filter((d) => d.doc_id !== doc.doc_id));
      toast.success(`"${doc.filename}" deleted.`);
    } catch (err) {
      toast.error(String(err));
    }
  }

  const displayDocs = optimisticDoc ? [optimisticDoc, ...docs] : docs;

  return (
    <div className="flex flex-col min-h-screen">
      <Nav />

      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% -5%, oklch(0.62 0.22 264 / 0.08), transparent)",
        }}
      />

      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-10">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-semibold">Document Library</h1>
          <Button onClick={() => setUploadOpen(true)}>
            <UploadIcon />
            Upload PDF
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-24 text-muted-foreground gap-2">
            <Loader2Icon className="animate-spin size-4" />
            Loading…
          </div>
        ) : displayDocs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-muted-foreground gap-3">
            <FileTextIcon className="size-10 opacity-30" />
            <p className="text-sm">No documents yet. Upload a PDF to get started.</p>
            <Button variant="outline" onClick={() => setUploadOpen(true)}>
              Upload PDF
            </Button>
          </div>
        ) : (
          <motion.div
            initial="hidden"
            animate="show"
            variants={{ hidden: {}, show: { transition: { staggerChildren: 0.07 } } }}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
          >
            <AnimatePresence>
              {displayDocs.map((doc) => {
                const isActive = ACTIVE_STATUSES.has(doc.status);
                const isUploading = doc.status === "uploading";
                const canRecover = doc.status === "stopped" || doc.status === "failed";

                return (
                  <motion.div
                    key={doc.doc_id}
                    variants={{
                      hidden: { opacity: 0, y: 16 },
                      show: { opacity: 1, y: 0, transition: { duration: 0.25 } },
                    }}
                  >
                    <Card className="card-glow flex flex-col h-full">
                      <CardHeader className="pb-3">
                        <CardTitle
                          className="text-sm font-semibold leading-snug"
                          title={doc.filename}
                        >
                          {doc.filename}
                        </CardTitle>
                      </CardHeader>

                      <CardContent className="flex-1 pb-3 space-y-3">
                        <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-xs">
                          <dt className="text-muted-foreground/70 font-medium">Uploaded</dt>
                          <dd className="text-muted-foreground">{formatDate(doc.uploaded_at)}</dd>
                          <dt className="text-muted-foreground/70 font-medium">PDF ID</dt>
                          <dd>
                            {doc.doc_id === "__uploading__" ? (
                              <span className="text-muted-foreground font-mono text-[10px]">—</span>
                            ) : (
                              <button
                                className="group inline-flex items-center gap-1 text-muted-foreground font-mono text-[10px] break-all text-left hover:text-foreground transition-colors cursor-pointer"
                                onClick={() => {
                                  navigator.clipboard.writeText(doc.doc_id);
                                  toast.success("Doc ID copied.");
                                }}
                                title="Click to copy"
                              >
                                {doc.doc_id}
                                <CopyIcon className="size-2.5 shrink-0 opacity-0 group-hover:opacity-60 transition-opacity" />
                              </button>
                            )}
                          </dd>
                          {doc.page_count != null && (
                            <>
                              <dt className="text-muted-foreground/70 font-medium">Pages</dt>
                              <dd className="text-muted-foreground">{doc.page_count}</dd>
                            </>
                          )}
                          {doc.index_time_s != null && (
                            <>
                              <dt className="text-muted-foreground/70 font-medium">Indexed in</dt>
                              <dd className="text-muted-foreground">{doc.index_time_s}s</dd>
                            </>
                          )}
                        </dl>

                        {/* Status — one line with bar+% when processing/uploading */}
                        {(doc.status === "processing" || isUploading) ? (
                          <StatusProgress
                            status={doc.status}
                            value={isUploading ? 0 : doc.progress_percent}
                          />
                        ) : (
                          <StatusBadge status={doc.status} />
                        )}

                        {/* Step breakdown — active or stopped/failed */}
                        {(doc.status === "processing" || doc.status === "stopped" || doc.status === "failed") && (
                          <StepsBreakdown progress={doc.progress_percent} status={doc.status} />
                        )}
                      </CardContent>

                      <CardFooter className="gap-2">
                        {isUploading ? (
                          <Button size="sm" className="flex-1" disabled>
                            <CloudUploadIcon className="size-3.5" />
                            Uploading…
                          </Button>
                        ) : isActive ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 text-destructive hover:text-destructive"
                            onClick={() => handleStop(doc)}
                            disabled={stopping.has(doc.doc_id)}
                          >
                            {stopping.has(doc.doc_id) ? (
                              <Loader2Icon className="size-3.5 animate-spin" />
                            ) : (
                              <StopCircleIcon className="size-3.5" />
                            )}
                            Stop
                          </Button>
                        ) : canRecover ? (
                          <>
                            <Button
                              size="sm"
                              className="flex-1"
                              onClick={() => handleReindex(doc)}
                              disabled={reindexing.has(doc.doc_id)}
                            >
                              {reindexing.has(doc.doc_id) ? (
                                <Loader2Icon className="size-3.5 animate-spin" />
                              ) : (
                                <RefreshCwIcon className="size-3.5" />
                              )}
                              Reindex
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="shrink-0 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(doc)}
                              title="Delete document"
                            >
                              <Trash2Icon className="size-3.5" />
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              className="flex-1"
                              disabled={!doc.indexed}
                              onClick={() => router.push(`/chat?doc=${doc.doc_id}`)}
                            >
                              <MessageSquareIcon />
                              Chat
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="shrink-0 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(doc)}
                              title="Delete document"
                            >
                              <Trash2Icon className="size-3.5" />
                            </Button>
                          </>
                        )}
                      </CardFooter>
                    </Card>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </motion.div>
        )}
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} DocuMind
      </footer>

      <Dialog
        open={uploadOpen}
        onOpenChange={(open) => {
          if (!uploading) { setUploadOpen(open); setSelectedFile(null); }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload a PDF</DialogTitle>
            <DialogDescription>
              The document will be queued for background processing. You can leave this page — the
              card will update automatically.
            </DialogDescription>
          </DialogHeader>

          <div
            className="border-2 border-dashed border-border rounded-xl p-8 text-center cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-colors"
            onClick={() => !uploading && fileRef.current?.click()}
          >
            {selectedFile ? (
              <p className="text-sm font-medium">{selectedFile.name}</p>
            ) : (
              <>
                <FileTextIcon className="mx-auto size-8 text-muted-foreground mb-2 opacity-50" />
                <p className="text-sm text-muted-foreground">Click to select a PDF</p>
              </>
            )}
            <input
              ref={fileRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => { setUploadOpen(false); setSelectedFile(null); }}
              disabled={uploading}
            >
              Cancel
            </Button>
            <Button onClick={handleUpload} disabled={!selectedFile || uploading}>
              {uploading ? (
                <><Loader2Icon className="size-4 animate-spin mr-1" /> Uploading…</>
              ) : (
                "Upload"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
