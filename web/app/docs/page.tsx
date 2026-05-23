"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { UploadIcon, FileTextIcon, MessageSquareIcon, Loader2Icon, DatabaseIcon, Trash2Icon } from "lucide-react";
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
import { Doc, deleteDoc, indexDocStream, listDocs, uploadDoc } from "@/lib/api";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

export default function DocsPage() {
  const router = useRouter();
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [indexingStatus, setIndexingStatus] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function fetchDocs() {
    try {
      const token = await getToken() ?? undefined;
      setDocs(await listDocs(token));
    } catch {
      toast.error("Could not reach the API. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (isLoaded && isSignedIn) fetchDocs(); }, [isLoaded, isSignedIn]);

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setIndexingStatus("Uploading…");
    const token = await getToken() ?? undefined;
    let docId = "";
    let filename = "";
    try {
      const uploaded = await uploadDoc(selectedFile, token);
      docId = uploaded.doc_id;
      filename = uploaded.filename;
    } catch (err) {
      toast.error(String(err));
      setUploading(false);
      setIndexingStatus("");
      return;
    }

    abortRef.current = new AbortController();
    await new Promise<void>((resolve) => {
      indexDocStream(
        docId,
        token,
        (msg) => setIndexingStatus(msg),
        (_chunks, _index_time_s) => {
          toast.success(`"${filename}" is ready.`);
          setUploadOpen(false);
          setSelectedFile(null);
          fetchDocs();
          setUploading(false);
          setIndexingStatus("");
          resolve();
        },
        (err) => {
          toast.error(err);
          setUploading(false);
          setIndexingStatus("");
          resolve();
        },
        abortRef.current!.signal,
      );
    });
  }

  async function handleDelete(doc: Doc) {
    if (!confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return;
    try {
      const token = await getToken() ?? undefined;
      await deleteDoc(doc.doc_id, token);
      setDocs((prev) => prev.filter((d) => d.doc_id !== doc.doc_id));
      toast.success(`"${doc.filename}" deleted.`);
    } catch (err) {
      toast.error(String(err));
    }
  }

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
        ) : docs.length === 0 ? (
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
              {docs.map((doc) => (
                <motion.div
                  key={doc.doc_id}
                  variants={{
                    hidden: { opacity: 0, y: 16 },
                    show:   { opacity: 1, y: 0, transition: { duration: 0.25 } },
                  }}
                >
                  <Card className="card-glow flex flex-col h-full">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm font-semibold leading-snug" title={doc.filename}>
                        {doc.filename}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 pb-3">
                      <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 text-xs">
                        <dt className="text-muted-foreground/70 font-medium">Uploaded</dt>
                        <dd className="text-muted-foreground">{formatDate(doc.uploaded_at)}</dd>
                        <dt className="text-muted-foreground/70 font-medium">PDF ID</dt>
                        <dd className="text-muted-foreground font-mono text-[10px] break-all select-all">{doc.doc_id}</dd>
                        {doc.index_time_s !== undefined ? (
                          <>
                            <dt className="text-muted-foreground/70 font-medium">Indexed in</dt>
                            <dd className="text-muted-foreground">{doc.index_time_s}s</dd>
                          </>
                        ) : (
                          <dd className="col-span-2">
                            <span className="inline-flex items-center gap-1 text-yellow-400">
                              <DatabaseIcon className="size-3" /> Not indexed
                            </span>
                          </dd>
                        )}
                      </dl>
                    </CardContent>
                    <CardFooter className="gap-2">
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
                    </CardFooter>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} DocuMind
      </footer>

      <Dialog open={uploadOpen} onOpenChange={(open) => { if (!uploading) { setUploadOpen(open); setSelectedFile(null); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload a PDF</DialogTitle>
            <DialogDescription>
              {uploading
                ? "Parsing and indexing your document — this may take 1–3 minutes for hi_res."
                : "The document will be parsed, chunked, and indexed automatically."}
            </DialogDescription>
          </DialogHeader>

          {uploading ? (
            <div className="flex flex-col items-center gap-4 py-6">
              <div className="relative flex items-center justify-center size-14">
                <Loader2Icon className="size-10 animate-spin text-primary" />
                <DatabaseIcon className="absolute size-4 text-primary" />
              </div>
              <AnimatePresence mode="wait">
                <motion.p
                  key={indexingStatus}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.2 }}
                  className="text-sm text-muted-foreground text-center max-w-xs"
                >
                  {indexingStatus || "Starting…"}
                </motion.p>
              </AnimatePresence>
            </div>
          ) : (
            <div
              className="border-2 border-dashed border-border rounded-xl p-8 text-center cursor-pointer hover:border-primary/50 hover:bg-primary/5 transition-colors"
              onClick={() => fileRef.current?.click()}
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
          )}

          {!uploading && (
            <DialogFooter>
              <Button variant="outline" onClick={() => { setUploadOpen(false); setSelectedFile(null); }}>
                Cancel
              </Button>
              <Button onClick={handleUpload} disabled={!selectedFile}>
                Upload &amp; Index
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
