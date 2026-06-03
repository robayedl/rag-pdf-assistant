import Nav from "@/components/nav";
import {
  Brain, BookOpen, Zap, ShieldCheck, Activity,
  GitBranch, Search, Lightbulb, Radio, MessageSquare, Shield, Gauge,
} from "lucide-react";

const features = [
  { icon: GitBranch,    title: "Agentic RAG",           desc: "LangGraph pipeline with grading, query rewriting, and hallucination checking. Every answer is verified before it reaches you." },
  { icon: Search,       title: "Hybrid Search",          desc: "pgvector HNSW + PostgreSQL full-text search fused with Reciprocal Rank Fusion for maximum retrieval precision." },
  { icon: Zap,          title: "Semantic Cache",          desc: "Redis vector cache; repeated queries return instantly without re-running the full pipeline." },
  { icon: Lightbulb,    title: "HyDE Fallback",           desc: "Hypothetical passage generation on low-confidence retrieval to improve recall when the query is sparse." },
  { icon: Radio,        title: "SSE Streaming",           desc: "Real-time token-by-token output via Server-Sent Events; answers persist to Postgres even if you disconnect or navigate away mid-stream." },
  { icon: BookOpen,     title: "Citations",               desc: "Every answer is grounded with page references; click to jump to the exact passage in the PDF." },
  { icon: MessageSquare, title: "Conversation Recovery", desc: "Navigate away or refresh mid-query and the completed answer is automatically recovered from the database when you return." },
  { icon: ShieldCheck,  title: "Secure & Private",        desc: "Clerk JWT RS256 auth: your documents, chats, and usage data are fully isolated and visible only to you." },
  { icon: Activity,     title: "Cost & Usage Tracking",   desc: "Token counts and AUD spend tracked per message with hourly, daily, weekly, monthly, and all-time charts." },
  { icon: Gauge,        title: "Rate Limiting",            desc: "Redis token-bucket: 30 requests/hour, 200/day per user with a countdown toast when the limit is reached." },
  { icon: Shield,       title: "PII Redaction",            desc: "Presidio detects and strips personally identifiable information from your query before it reaches the model." },
  { icon: Brain,        title: "Background Ingestion",     desc: "Celery worker processes PDFs asynchronously with live step-level progress and stop/reindex controls." },
];

const stack = [
  { layer: "Agent",      tech: "LangGraph + LangChain"                              },
  { layer: "LLM",        tech: "Google Gemini 2.5 Flash"                            },
  { layer: "Retrieval",  tech: "pgvector HNSW + ts_rank FTS · Reciprocal Rank Fusion" },
  { layer: "Reranking",  tech: "ms-marco-MiniLM-L-6-v2 cross-encoder"               },
  { layer: "Cache",      tech: "Redis Stack (vector similarity + Celery broker)"     },
  { layer: "Worker",     tech: "Celery (async PDF ingestion, step-level progress)"   },
  { layer: "Parsing",    tech: "unstructured hi_res · Gemini multimodal"             },
  { layer: "Database",   tech: "PostgreSQL + pgvector"                               },
  { layer: "Auth",       tech: "Clerk JWT RS256 · per-user document isolation"       },
  { layer: "Rate limit", tech: "Redis token-bucket · 30 req/hour · 200 req/day"      },
  { layer: "PII",        tech: "Presidio analyzer/anonymizer · opt-in redaction"     },
  { layer: "API",        tech: "FastAPI + SSE streaming"                             },
  { layer: "Frontend",   tech: "Next.js 15 · shadcn/ui · Tailwind CSS"              },
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
          <span className="inline-flex items-center px-2 py-0.5 rounded-full border border-primary/25 bg-primary/10 text-primary text-[10px] font-mono font-medium">
            v2.1.0
          </span>
        </div>

        <p className="text-muted-foreground leading-relaxed mb-12 text-justify">
          DocuMind is an open-source agentic RAG system that lets you have a grounded, citation-backed conversation with any PDF. It combines a LangGraph agent, hybrid pgvector + full-text search, a cross-encoder reranker, and Gemini 2.5 Flash to deliver accurate, low-latency answers with real-time streaming. Per-user rate limiting, optional PII redaction, and a cost-tracking dashboard are built in. Each user's documents, chats, and usage data are fully isolated via Clerk JWT authentication.
        </p>

        {/* Features */}
        <h2 className="text-xl font-semibold mb-4">Features</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-16">
          {features.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="card-glow rounded-xl border border-border bg-card p-5">
              <div className="flex items-center gap-2.5 mb-2">
                <span className="flex items-center justify-center size-7 rounded-md bg-primary/15 text-primary">
                  <Icon className="size-3.5" />
                </span>
                <h3 className="font-medium text-sm">{title}</h3>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed text-justify">{desc}</p>
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

        {/* Build credit */}
        <div className="mt-10 pt-6 border-t border-border/50 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-muted-foreground/60">
          <span>
            Designed and developed by{" "}
            <a
              href="https://www.linkedin.com/in/robayedashraf/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-muted-foreground/80 hover:text-primary transition-colors underline underline-offset-2"
            >
              Robayed Ashraf
            </a>
            {" "}· AI/ML Engineer
          </span>
          <span className="font-mono">DocuMind v2.1.0</span>
        </div>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} DocuMind
      </footer>
    </div>
  );
}
