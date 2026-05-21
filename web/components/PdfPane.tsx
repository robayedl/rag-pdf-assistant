"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { ChevronLeftIcon, ChevronRightIcon, XIcon, FileTextIcon, AlertCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.mjs";

export interface PdfPaneProps {
  url: string | null;
  targetPage: number;
  snippet: string;
  /** Incremented by parent to force a jump even when page hasn't changed. */
  jumpKey: number;
  onClose: () => void;
}

const HIGHLIGHT_STYLE =
  'background:#FFE600;color:#1a1a1a;border-radius:2px;padding:0 2px;font-weight:inherit';

const norm = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();

// Trigram highlight: fires when any 3-word sequence from the snippet is found
// in a rolling window of recent text items. Highlights that item + ~N more.
function buildTextRenderer(snippet: string) {
  if (!snippet) return ({ str }: { str: string }) => str;

  const snWords = norm(snippet).split(' ').filter(Boolean);
  if (snWords.length < 3) return ({ str }: { str: string }) => str;

  const trigrams = new Set<string>();
  for (let i = 0; i < snWords.length - 2; i++) {
    trigrams.add(`${snWords[i]} ${snWords[i + 1]} ${snWords[i + 2]}`);
  }

  const buf: string[] = [];
  let runLeft = 0;

  return function customTextRenderer({ str }: { str: string }): string {
    if (!str.trim()) return str;
    const words = norm(str.trim()).split(' ').filter(Boolean);
    if (!words.length) return str;

    if (runLeft > 0) {
      runLeft--;
      buf.push(...words);
      if (buf.length > 8) buf.splice(0, buf.length - 8);
      return `<mark style="${HIGHLIGHT_STYLE}">${str}</mark>`;
    }

    const combined = [...buf.slice(-4), ...words];
    let hit = false;
    for (let i = 0; i <= combined.length - 3; i++) {
      if (trigrams.has(`${combined[i]} ${combined[i + 1]} ${combined[i + 2]}`)) {
        hit = true;
        break;
      }
    }

    buf.push(...words);
    if (buf.length > 8) buf.splice(0, buf.length - 8);

    if (hit) {
      runLeft = Math.max(3, Math.ceil(snWords.length / 5));
      return `<mark style="${HIGHLIGHT_STYLE}">${str}</mark>`;
    }

    return str;
  };
}

export default function PdfPane({ url, targetPage, snippet, jumpKey, onClose }: PdfPaneProps) {
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(targetPage > 0 ? targetPage : 1);
  const [containerWidth, setContainerWidth] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      if (w > 0) setContainerWidth(w);
    });
    ro.observe(el);
    if (el.clientWidth > 0) setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const p = targetPage > 0 ? targetPage : 1;
    setCurrentPage(p);
    setLoadError(false);
  }, [targetPage, url, jumpKey]);

  function goTo(page: number) {
    if (!numPages) return;
    setCurrentPage(Math.max(1, Math.min(numPages, page)));
  }

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); goTo(currentPage + 1); }
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); goTo(currentPage - 1); }
    },
    [currentPage, numPages],
  );

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const customTextRenderer = useCallback(buildTextRenderer(snippet), [snippet]);

  function onLoadSuccess({ numPages: n }: { numPages: number }) {
    setNumPages(n);
    setLoadError(false);
    setCurrentPage(Math.min(Math.max(1, targetPage > 0 ? targetPage : 1), n));
  }

  if (!url) {
    return (
      <div className="flex flex-col h-full">
        <PdfToolbar currentPage={0} numPages={0} onPrev={() => {}} onNext={() => {}} onClose={onClose} />
        <div className="flex flex-col items-center justify-center flex-1 gap-3 text-muted-foreground">
          <FileTextIcon className="size-10 opacity-20" />
          <p className="text-sm text-center px-6">Click any citation to view the source</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full outline-none focus-visible:ring-0"
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <PdfToolbar
        currentPage={currentPage}
        numPages={numPages}
        onPrev={() => goTo(currentPage - 1)}
        onNext={() => goTo(currentPage + 1)}
        onClose={onClose}
      />

      <div className="flex-1 overflow-y-auto bg-muted/30 flex flex-col items-center py-4 px-2">
        <Document
          key={url}
          file={url}
          onLoadSuccess={onLoadSuccess}
          onLoadError={() => setLoadError(true)}
          loading={
            <div className="flex items-center justify-center h-40 text-muted-foreground text-sm gap-2">
              <span className="animate-pulse">Loading PDF…</span>
            </div>
          }
          error={null}
        >
          {loadError ? (
            <div className="flex flex-col items-center gap-2 text-muted-foreground py-10 px-4 text-center">
              <AlertCircleIcon className="size-8 opacity-40" />
              <p className="text-sm">Could not load this PDF.</p>
              <p className="text-xs opacity-60">The document may have been deleted or re-uploaded.</p>
            </div>
          ) : (
            <div className="shadow-lg ring-1 ring-border/30">
              <Page
                key={`${url}-${currentPage}`}
                pageNumber={currentPage}
                width={containerWidth > 32 ? containerWidth - 32 : undefined}
                renderTextLayer
                renderAnnotationLayer
                customTextRenderer={customTextRenderer}
                loading={
                  <div
                    style={{ width: containerWidth > 32 ? containerWidth - 32 : 400, height: 560 }}
                    className="flex items-center justify-center text-muted-foreground text-sm animate-pulse"
                  >
                    Rendering page {currentPage}…
                  </div>
                }
              />
            </div>
          )}
        </Document>
      </div>
    </div>
  );
}

interface PdfToolbarProps {
  currentPage: number;
  numPages: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}

function PdfToolbar({ currentPage, numPages, onPrev, onNext, onClose }: PdfToolbarProps) {
  return (
    <div className="shrink-0 h-10 border-b border-border flex items-center px-2 gap-1 bg-background/80 backdrop-blur-sm">
      <Button variant="ghost" size="icon" className="size-7" onClick={onPrev}
        disabled={currentPage <= 1} title="Previous page (←)">
        <ChevronLeftIcon className="size-4" />
      </Button>
      <span className="text-xs text-muted-foreground tabular-nums select-none min-w-[4rem] text-center">
        {currentPage > 0 ? `${currentPage} / ${numPages || "—"}` : "—"}
      </span>
      <Button variant="ghost" size="icon" className="size-7" onClick={onNext}
        disabled={!numPages || currentPage >= numPages} title="Next page (→)">
        <ChevronRightIcon className="size-4" />
      </Button>
      <div className="flex-1" />
      <Button variant="ghost" size="icon" className="size-7" onClick={onClose} title="Close PDF pane">
        <XIcon className="size-4" />
      </Button>
    </div>
  );
}
