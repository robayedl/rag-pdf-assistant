import Nav from "@/components/nav";
import { Brain, BookOpen, Layers, Zap } from "lucide-react";

const stack = [
  { layer: "Agent",      tech: "LangGraph + LangChain"                              },
  { layer: "LLM",        tech: "Google Gemini 2.5 Flash"                            },
  { layer: "Retrieval",  tech: "pgvector HNSW + ts_rank FTS · Reciprocal Rank Fusion" },
  { layer: "Reranking",  tech: "ms-marco-MiniLM-L-6-v2 cross-encoder"               },
  { layer: "Cache",      tech: "Redis Stack (vector similarity)"                     },
  { layer: "Parsing",    tech: "unstructured hi_res · Gemini multimodal"             },
  { layer: "Database",   tech: "PostgreSQL + pgvector"                               },
  { layer: "Auth",       tech: "Clerk JWT RS256 · per-user document isolation"       },
  { layer: "API",        tech: "FastAPI + SSE streaming"                             },
  { layer: "Frontend",   tech: "Next.js 16 · shadcn/ui · Tailwind CSS"              },
];

const highlights = [
  {
    icon: Layers,
    title: "Production-grade pipeline",
    desc:  "Every query passes through routing, hybrid retrieval, reranking, grading, generation, and hallucination checking before a response is returned.",
  },
  {
    icon: Zap,
    title: "Optimised for speed",
    desc:  "Semantic cache (Redis vector similarity) short-circuits the full pipeline for repeated or near-identical questions. Cache hits return in milliseconds.",
  },
  {
    icon: BookOpen,
    title: "Grounded answers",
    desc:  "Every response includes page-level citations pulled from the source PDF. The hallucination-check node rejects answers that aren't grounded in retrieved context.",
  },
];

export default function AboutPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Nav />

      {/* ambient glow */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% -5%, oklch(0.62 0.22 264 / 0.1), transparent)",
        }}
      />

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-16">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <span className="flex items-center justify-center size-10 rounded-xl bg-primary/15 text-primary">
            <Brain className="size-5" />
          </span>
          <h1 className="text-3xl font-bold tracking-tight">About DocuMind</h1>
        </div>

        <p className="text-muted-foreground leading-relaxed mb-12 max-w-2xl">
          DocuMind is an open-source agentic RAG system that lets you have a
          grounded, citation-backed conversation with any PDF. It combines a
          LangGraph agent, hybrid pgvector + full-text search, a cross-encoder
          reranker, and Gemini 2.5 Flash to deliver accurate, low-latency
          answers with real-time streaming. Each user's documents and chats
          are fully isolated via Clerk JWT authentication.
        </p>

        {/* Highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-16">
          {highlights.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="card-glow rounded-xl border border-border bg-card p-5">
              <span className="flex items-center justify-center size-8 rounded-lg bg-primary/15 text-primary mb-3">
                <Icon className="size-4" />
              </span>
              <h3 className="font-medium text-sm mb-1.5">{title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

        {/* Tech Stack */}
        <h2 className="text-xl font-semibold mb-4">Tech Stack</h2>
        <div className="rounded-xl border border-border overflow-hidden mb-12">
          {stack.map(({ layer, tech }, i) => (
            <div
              key={layer}
              className={`flex items-center gap-4 px-5 py-3 text-sm ${
                i % 2 === 0 ? "bg-card" : "bg-muted/30"
              }`}
            >
              <span className="w-24 shrink-0 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                {layer}
              </span>
              <span>{tech}</span>
            </div>
          ))}
        </div>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} DocuMind
      </footer>
    </div>
  );
}
