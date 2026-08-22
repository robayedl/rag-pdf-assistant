import Nav from "@/components/nav";
import {
  Brain, GitBranch, Search, Lightbulb, Shield,
  Layers, FlaskConical, Server, Plug, Wrench,
} from "lucide-react";

const features = [
  { icon: GitBranch,    title: "Multi-Agent Supervisor",  desc: "LangGraph supervisor orchestrates Researcher, Synthesizer, and Critic agents. The Critic checks hallucination, missing citations, and off-topic drift, sending the draft back to the Synthesizer for up to 2 revisions." },
  { icon: Wrench,       title: "Researcher Tools",         desc: "The Researcher agent calls Tavily web search and a safe (simpleeval) calculator via Gemini function calling. Tool selection is entirely up to the model, with no hardcoded trigger rules." },
  { icon: FlaskConical, title: "RAGAS Evaluation",         desc: "Faithfulness, answer relevancy, context precision, and recall measured on a 30-question golden dataset, re-checked on every pipeline change." },
  { icon: Search,       title: "Hybrid Search",            desc: "Dense pgvector HNSW + sparse ts_rank full-text fused with Reciprocal Rank Fusion and cross-encoder reranking for maximum retrieval precision." },
  { icon: Brain,        title: "Contextual Retrieval",     desc: "Gemini prepends a context sentence to every chunk before embedding, dramatically improving retrieval precision for long documents." },
  { icon: Lightbulb,    title: "HyDE Fallback",            desc: "On low reranker confidence, generates a hypothetical passage and re-retrieves for better recall when the query is sparse." },
  { icon: Plug,         title: "MCP Server",              desc: "Exposes search_documents, list_documents, and get_document as Model Context Protocol tools for Claude Desktop and Cursor. Authenticated via per-user API keys." },
  { icon: Layers,       title: "Multimodal Parsing",       desc: "Tables extracted as Markdown, figures captioned by Gemini Vision, and full OCR coverage for scanned pages via unstructured + Tesseract." },
  { icon: Server,       title: "Async Ingestion",          desc: "Celery worker queue processes documents in the background with live multi-stage progress tracking, so uploads never block the UI." },
  { icon: Shield,       title: "PII Redaction",            desc: "Presidio detects and strips personally identifiable information from your query before it reaches the model." },
];

const stack = [
  { layer: "Agent",      tech: "LangGraph multi-agent supervisor (Researcher/Synthesizer/Critic)" },
  { layer: "Tools",      tech: "Tavily web search · simpleeval calculator (Gemini function calling)" },
  { layer: "LLM",        tech: "Google Gemini 2.5 Flash"                                      },
  { layer: "Retrieval",  tech: "pgvector HNSW + ts_rank FTS · Reciprocal Rank Fusion"         },
  { layer: "Reranking",  tech: "ms-marco-MiniLM-L-6-v2 cross-encoder"                         },
  { layer: "Cache",      tech: "Redis Stack (vector similarity + Celery broker)"               },
  { layer: "Worker",     tech: "Celery (unified PDF pipeline · LibreOffice DOCX conversion)"    },
  { layer: "Parsing",    tech: "unstructured hi_res · Tesseract OCR · Gemini multimodal"       },
  { layer: "Database",   tech: "PostgreSQL + pgvector"                                         },
  { layer: "Auth",       tech: "Clerk JWT RS256 · per-user document isolation"                 },
  { layer: "Rate limit", tech: "Redis token-bucket · 30 req/hour · 200 req/day"               },
  { layer: "PII",        tech: "Presidio analyzer/anonymizer · opt-in redaction"               },
  { layer: "API",        tech: "FastAPI + SSE streaming"                                       },
  { layer: "MCP",        tech: "Model Context Protocol server · stdio + HTTP/SSE · API key auth" },
  { layer: "Frontend",   tech: "Next.js 16 · shadcn/ui · Tailwind CSS"                        },
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
            v3.0.0
          </span>
        </div>

        <p className="text-muted-foreground leading-relaxed mb-12 text-justify">
          DocuMind is an open-source multi-agent RAG system that lets you have a grounded, citation-backed conversation with any PDF or DOCX file. A LangGraph supervisor coordinates Researcher, Synthesizer, and Critic agents: the Researcher runs hybrid pgvector + full-text search and can call web search or a calculator tool via Gemini function calling, the Synthesizer writes a cited answer, and the Critic checks it for hallucination, missing citations, and off-topic drift before it reaches you. It also exposes a Model Context Protocol server so Claude Desktop and Cursor can search your documents as native tools. Per-user rate limiting, optional PII redaction, and a cost-tracking dashboard are built in. Each user's documents, chats, and usage data are fully isolated via Clerk JWT authentication.
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
          <span className="font-mono">DocuMind v3.0.0</span>
        </div>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} DocuMind
      </footer>
    </div>
  );
}
