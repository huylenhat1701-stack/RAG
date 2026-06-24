"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Clock, ChatCircle, CaretDown, CaretUp } from "@phosphor-icons/react";

interface ChatMessage {
  role: string;
  content: string;
}

interface HistoryItem {
  id: number;
  question: string;
  answer: string;
  created_at: string;
  model_used: string;
}

export default function HistoryPage() {
  const [histories, setHistories] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setLoading(true);
    const { data } = await api.get("/chat/history", { limit: 50 });
    if (data && data.histories) {
      setHistories(data.histories);
      setTotal(data.total || 0);
    }
    setLoading(false);
  };

  const formatDate = (dateStr: string) => {
    try {
      const dt = new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z");
      return dt.toLocaleString("vi-VN");
    } catch {
      return dateStr;
    }
  };

  return (
    <main className="min-h-screen bg-background text-foreground p-8 pb-36 md:p-16 relative overflow-hidden transition-colors duration-300">
      {/* Background ambient light */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] mesh-glow-violet opacity-30 dark:opacity-60"></div>
        <div className="absolute bottom-[-10%] right-[-10%] mesh-glow-emerald opacity-30 dark:opacity-60"></div>
      </div>

      <div className="max-w-4xl mx-auto relative z-10">
        <div className="mb-12 text-center md:text-left">
          <span className="rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.2em] font-bold text-muted bg-foreground/5 border border-border mb-4 inline-block">
            Nhật ký lưu trữ
          </span>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 text-foreground">
            Lịch sử hội thoại.
          </h1>
          <p className="text-muted text-lg">Bạn có {total} phiên hội thoại đã được ghi nhận.</p>
        </div>

        {loading ? (
          <div className="flex justify-center items-center h-40">
            <div className="w-8 h-8 rounded-full bg-foreground/5 flex items-center justify-center">
              <div className="w-3 h-3 bg-accent-color rounded-full animate-pulse"></div>
            </div>
          </div>
        ) : histories.length === 0 ? (
          <div className="double-bezel-outer">
            <div className="double-bezel-inner p-12 text-center flex flex-col items-center justify-center">
              <Clock className="w-12 h-12 text-muted mb-4" weight="light" />
              <h3 className="text-xl font-bold text-foreground">Chưa có lịch sử</h3>
              <p className="text-muted text-sm mt-2">Bắt đầu gửi tin nhắn tại trang Hội thoại để hiển thị lịch sử ở đây.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {histories.map((session, idx) => {
              const isExpanded = expandedIndex === idx;
              const previewTitle = session.question.slice(0, 65) + (session.question.length > 65 ? "..." : "");
              
              return (
                <div 
                  key={idx} 
                  className={`double-bezel-outer transition-premium duration-500 overflow-hidden ${
                    isExpanded ? "scale-[1.01]" : "hover:scale-[1.005]"
                  }`}
                >
                  <div className="double-bezel-inner overflow-hidden">
                    <button 
                      onClick={() => setExpandedIndex(isExpanded ? null : idx)}
                      className="w-full text-left p-6 flex items-center justify-between gap-4 focus:outline-none cursor-pointer"
                    >
                      <div className="flex items-center gap-4 overflow-hidden">
                        <div className="w-11 h-11 rounded-full bg-foreground/5 flex items-center justify-center flex-shrink-0">
                          <ChatCircle className="text-accent-color w-5 h-5" weight={isExpanded ? "fill" : "light"} />
                        </div>
                        <div className="overflow-hidden">
                          <h3 className="font-bold text-base text-foreground truncate leading-snug">{previewTitle}</h3>
                          <p className="text-xs text-muted mt-1 font-medium">{formatDate(session.created_at)}</p>
                        </div>
                      </div>
                      <div className="text-muted flex-shrink-0">
                        {isExpanded ? <CaretUp weight="bold" /> : <CaretDown weight="bold" />}
                      </div>
                    </button>

                    <div className={`transition-all duration-500 ease-in-out ${isExpanded ? "max-h-[800px] opacity-100" : "max-h-0 opacity-0"} overflow-y-auto`}>
                      <div className="p-6 pt-0 border-t border-border bg-foreground/[0.01]">
                        <div className="space-y-6 mt-6 max-w-3xl mx-auto">
                          {/* User Message */}
                          <div className="flex justify-end">
                            <div className="max-w-[85%] rounded-3xl p-5 bg-foreground text-background rounded-tr-none font-semibold text-sm shadow-md leading-relaxed whitespace-pre-wrap">
                              {session.question}
                            </div>
                          </div>
                          {/* Assistant Message */}
                          <div className="flex justify-start">
                            <div className="max-w-[85%] double-bezel-outer w-full">
                              <div className="double-bezel-inner p-5 border border-border text-foreground text-base leading-relaxed whitespace-pre-wrap">
                                {session.answer}
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
