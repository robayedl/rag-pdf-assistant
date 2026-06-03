"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import {
  GitBranch, Search, Zap, Lightbulb,
  Radio, BookOpen, Brain, Shield,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import Nav from "@/components/nav";

const features = [
  { icon: GitBranch, title: "Agentic RAG",         desc: "LangGraph pipeline with grading, query rewriting, and hallucination checking. Every answer is verified." },
  { icon: Search,    title: "Hybrid Search",        desc: "pgvector HNSW + PostgreSQL full-text search fused with Reciprocal Rank Fusion" },
  { icon: Zap,       title: "Semantic Cache",        desc: "Redis vector cache; repeated queries return instantly without re-running the pipeline" },
  { icon: Lightbulb, title: "HyDE Fallback",         desc: "Hypothetical passage generation on low-confidence retrieval to improve recall" },
  { icon: Radio,     title: "SSE Streaming",         desc: "Real-time token-by-token output via Server-Sent Events; answers persist to the database even if you navigate away mid-stream" },
  { icon: BookOpen,  title: "Citations",             desc: "Every answer is grounded with page references; click to jump to the exact passage" },
  { icon: Shield,    title: "PII Redaction",          desc: "Presidio detects and strips personal information from your query before it reaches the model" },
  { icon: Brain,     title: "Background Ingestion",   desc: "Celery worker processes PDFs asynchronously with live step-level progress and stop/reindex controls" },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};

const item = {
  hidden: { opacity: 0, y: 16 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" as const } },
};

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Nav />

      {/* Ambient glow */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 50% -5%, oklch(0.62 0.22 264 / 0.12), transparent)",
        }}
      />

      <main className="flex-1">
        {/* Hero */}
        <section className="max-w-6xl mx-auto px-4 pt-16 pb-12 text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/30 bg-primary/10 text-primary text-xs font-medium mb-4"
          >
            <Brain className="size-3.5" />
            Powered by LangGraph + Gemini 2.5 Flash
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-4xl sm:text-5xl font-bold tracking-tight mb-4 leading-[1.1]"
          >
            <span className="gradient-heading">Agentic Document</span>
            <br />
            <span className="gradient-heading">Intelligence</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-base text-muted-foreground max-w-xl mx-auto mb-7"
          >
            Chat with any PDF using a production-grade pipeline: hybrid search,
            semantic caching, hallucination checking, and real-time streaming.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
            className="flex items-center justify-center gap-3"
          >
            <Link href="/docs" className={buttonVariants({ size: "lg" })}>
              Get started
            </Link>
            <Link href="/how-to-use" className={buttonVariants({ variant: "outline", size: "lg" })}>
              How it works
            </Link>
          </motion.div>
        </section>

        {/* Features */}
        <section className="max-w-6xl mx-auto px-4 pb-14">
          <motion.div
            variants={container}
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.2 }}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
          >
            {features.map(({ icon: Icon, title, desc }) => (
              <motion.div
                key={title}
                variants={item}
                className="card-glow rounded-xl border border-border bg-card p-5 cursor-default"
              >
                <div className="flex items-center gap-2.5 mb-2">
                  <span className="flex items-center justify-center size-7 rounded-md bg-primary/15 text-primary">
                    <Icon className="size-3.5" />
                  </span>
                  <h3 className="font-medium text-sm">{title}</h3>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed text-justify">{desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </section>
      </main>

      <footer className="border-t border-border py-6 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} DocuMind
      </footer>
    </div>
  );
}
