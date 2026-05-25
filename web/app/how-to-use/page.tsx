import Nav from "@/components/nav";
import { LogInIcon, UploadIcon, DatabaseIcon, MessageSquareIcon, LightbulbIcon, AlertCircleIcon } from "lucide-react";

const steps = [
  {
    number: "01",
    icon: LogInIcon,
    title: "Sign in",
    desc: "Click Sign in from the nav bar or visit /login. Create an account or sign in with an existing one.",
    detail: "DocuMind uses Clerk for authentication. Your documents and chats are private — no other user can see them.",
  },
  {
    number: "02",
    icon: UploadIcon,
    title: "Upload a PDF",
    desc: "Go to Documents and click Upload PDF. Select any PDF from your machine. Only PDF files are supported.",
    detail: "The file is stored securely on the server and associated with your account.",
  },
  {
    number: "03",
    icon: DatabaseIcon,
    title: "Wait for indexing",
    desc: "After upload the document is queued for background processing. The card shows live progress through five stages: Queued, Parsing, Extracting, Embedding, and Finalizing.",
    detail: "Indexing can take 1 to 3 minutes depending on file size. You can leave the page and come back — the card updates automatically every two seconds. Use the Stop button to cancel at any time, or Reindex to retry a failed or stopped document. The Chat button activates once indexing completes.",
  },
  {
    number: "04",
    icon: MessageSquareIcon,
    title: "Start chatting",
    desc: "Click Chat on any indexed document. You can also navigate to /chat directly and pick a document from the selector.",
    detail: "Conversation history is saved per session and per account — pick up where you left off.",
  },
  {
    number: "05",
    icon: LightbulbIcon,
    title: "Read citations",
    desc: "Every answer includes page badges beneath the response. Click a badge to open the PDF at the exact source passage.",
    detail: "If the model cannot find relevant context, it says so rather than hallucinating.",
  },
];

const tips = [
  "Ask specific questions — the retrieval pipeline works best with focused queries.",
  "Rephrase if the first answer is weak — the rewrite node will try a different query.",
  "Repeated or near-identical questions hit the semantic cache and return instantly.",
  "Your documents are private — only you can see and chat with files you've uploaded.",
  "Session memory persists across logins — your chat history is saved to your account.",
];

export default function HowToUsePage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Nav />

      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% -5%, oklch(0.62 0.22 264 / 0.1), transparent)",
        }}
      />

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-16">
        <h1 className="text-3xl font-bold tracking-tight mb-2">How to use DocuMind</h1>
        <p className="text-muted-foreground mb-14">
          From upload to conversation in five steps.
        </p>

        {/* Steps */}
        <div className="flex flex-col gap-6 mb-16">
          {steps.map(({ number, icon: Icon, title, desc, detail }) => (
            <div key={number} className="card-glow flex gap-5 rounded-xl border border-border bg-card p-6">
              <div className="shrink-0 flex flex-col items-center gap-2">
                <span className="text-xs font-mono text-primary font-bold">{number}</span>
                <span className="flex items-center justify-center size-9 rounded-lg bg-primary/15 text-primary">
                  <Icon className="size-4" />
                </span>
              </div>
              <div>
                <h3 className="font-semibold mb-1">{title}</h3>
                <p className="text-sm text-foreground/80 mb-2 text-justify">{desc}</p>
                <p className="text-xs text-muted-foreground leading-relaxed text-justify">{detail}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Tips */}
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-6">
          <div className="flex items-center gap-2 mb-4 text-primary font-medium text-sm">
            <AlertCircleIcon className="size-4" />
            Tips for best results
          </div>
          <ul className="flex flex-col gap-2">
            {tips.map((tip) => (
              <li key={tip} className="flex items-start gap-2 text-sm text-muted-foreground text-justify">
                <span className="mt-1.5 size-1.5 rounded-full bg-primary/60 shrink-0" />
                {tip}
              </li>
            ))}
          </ul>
        </div>

        {/* Build time note */}
        <div className="mt-6 rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
          <strong className="text-foreground">First Docker build takes longer.</strong>{" "}
          The initial{" "}
          <code className="font-mono text-xs bg-muted px-1 py-0.5 rounded">docker compose up --build</code>{" "}
          downloads Python ML models (~1 GB) and compiles the Next.js app. Subsequent
          builds use Docker layer cache and are significantly faster.
        </div>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} DocuMind
      </footer>
    </div>
  );
}
