"use client";

import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Home() {
  const [healthStatus, setHealthStatus] = useState<string>("Checking...");

  useEffect(() => {
    async function checkHealth() {
      const { data } = await api.get("/health");
      if (data && data.status) {
        setHealthStatus(data.status);
      } else {
        setHealthStatus("Offline");
      }
    }
    checkHealth();
  }, []);

  return (
    <main className="flex flex-col flex-1 items-center justify-center min-h-[100dvh] relative overflow-hidden bg-background transition-colors duration-300">
      {/* Background with premium mesh gradients */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] mesh-glow-violet opacity-60 dark:opacity-100"></div>
        <div className="absolute bottom-[-10%] right-[-10%] mesh-glow-emerald opacity-60 dark:opacity-100"></div>
      </div>

      <div className="relative z-10 w-full max-w-6xl px-6 py-24 flex flex-col items-center text-center">
        {/* Eyebrow Tag */}
        <span className="rounded-full px-4 py-1.5 text-[10px] uppercase tracking-[0.25em] font-bold text-muted bg-foreground/5 border border-border mb-8 shadow-sm">
          Giải pháp RAG thông minh
        </span>

        {/* The 2-line Iron Rule: max-w and clamp font size */}
        <h1 className="text-[clamp(2.5rem,6vw,5rem)] font-bold tracking-tight text-foreground leading-[1.1] mb-8 max-w-5xl transition-premium">
          Tương tác với tài liệu của bạn{" "}
          <span className="inline-block w-20 md:w-24 h-[clamp(2.5rem,5vw,4rem)] rounded-full align-middle bg-cover bg-center mx-2 shadow-2xl filter grayscale contrast-125 opacity-90 border border-border" 
                style={{backgroundImage: 'url(https://picsum.photos/seed/knowledge/800/400)'}}>
          </span>
          tức thì bằng RAG.
        </h1>

        <p className="text-lg md:text-xl text-muted max-w-2xl mb-12 leading-relaxed">
          Tải lên tài liệu PDF, phân tích nội dung và trò chuyện trực tiếp với AI tiên tiến được đồng bộ trực tiếp với cơ sở tri thức cá nhân của bạn.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          <Link href="/documents" className="group flex items-center justify-between gap-4 bg-foreground text-background pl-8 pr-3 py-3 rounded-full font-semibold text-lg hover:scale-[1.03] active:scale-[0.98] transition-premium shadow-xl">
            Tải tài liệu lên
            <div className="w-10 h-10 rounded-full bg-background/20 dark:bg-background/10 flex items-center justify-center group-hover:translate-x-1 transition-transform">
              <ArrowRight className="w-5 h-5 text-background" weight="bold" />
            </div>
          </Link>
          <Link href="/chat" className="group flex items-center justify-center gap-2 bg-card hover:bg-foreground/5 border border-border text-foreground px-8 py-4 rounded-full font-semibold text-lg hover:scale-[1.03] active:scale-[0.98] transition-premium shadow-md">
            Bắt đầu trò chuyện
          </Link>
        </div>
        
        <div className="mt-20 inline-flex items-center gap-3 px-4 py-2.5 rounded-full bg-card border border-border shadow-sm transition-premium">
          <div className={`w-2.5 h-2.5 rounded-full ${healthStatus === 'ok' ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' : 'bg-red-500 animate-pulse'}`}></div>
          <span className="text-xs font-bold text-muted uppercase tracking-[0.2em]">
            Hệ thống: {healthStatus === 'ok' ? 'Trực tuyến' : 'Ngoại tuyến'}
          </span>
        </div>
      </div>
    </main>
  );
}
