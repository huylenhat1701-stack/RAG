"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ChartBar, ArrowClockwise, Lightbulb, TrendUp, Database } from "@phosphor-icons/react";

export default function EvaluationPage() {
  const [bktData, setBktData] = useState<any>(null);
  const [ragData, setRagData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    const [bktRes, ragRes] = await Promise.all([
      api.get("/evaluate/bkt"),
      api.get("/evaluate/rag-stats")
    ]);
    if (bktRes.data) setBktData(bktRes.data);
    if (ragRes.data) setRagData(ragRes.data);
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <main className="min-h-screen bg-background text-foreground pt-32 pb-40 px-6 relative overflow-hidden transition-colors duration-300">
      {/* Background ambient light */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] mesh-glow-violet opacity-30 dark:opacity-60"></div>
        <div className="absolute bottom-[-10%] right-[-10%] mesh-glow-emerald opacity-30 dark:opacity-60"></div>
      </div>

      <div className="max-w-7xl mx-auto w-full flex flex-col gap-12 relative z-10">
        
        <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-6">
          <div>
            <span className="rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.2em] font-bold text-muted bg-foreground/5 border border-border mb-4 inline-block">
              Báo cáo hiệu năng
            </span>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-foreground mb-4">
              Chẩn đoán hệ thống
            </h1>
            <p className="text-muted text-lg max-w-2xl">
              Số liệu đánh giá thời gian thực cho mô hình Bayesian Knowledge Tracing (BKT) và Retrieval-Augmented Generation (RAG).
            </p>
          </div>
          
          <button 
            onClick={fetchData}
            disabled={loading}
            className="group flex items-center justify-center gap-2 bg-card border border-border text-foreground px-6 py-3.5 rounded-full font-bold text-sm hover:scale-105 active:scale-[0.98] transition-premium cursor-pointer shadow-md"
          >
            <ArrowClockwise className={`w-5 h-5 ${loading ? 'animate-spin' : 'group-hover:-rotate-90 transition-premium-fast'}`} weight="bold" />
            Cập nhật số liệu
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-64 text-muted">
            <div className="w-8 h-8 rounded-full bg-foreground/5 flex items-center justify-center">
              <div className="w-3 h-3 bg-accent-color rounded-full animate-pulse"></div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6 grid-flow-dense auto-rows-[230px]">
            
            {/* RAG Metrics Header Card (Col span 2) */}
            <div className="md:col-span-2 row-span-1 double-bezel-outer group">
              <div className="double-bezel-inner p-8 flex flex-col justify-between h-full relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-premium"></div>
                <div className="relative z-10 flex items-center gap-3 text-indigo-500 mb-2">
                  <Database className="w-6 h-6" weight="light" />
                  <span className="font-bold uppercase tracking-widest text-[10px]">Phân tích RAG</span>
                </div>
                <div className="relative z-10 flex items-end justify-between">
                  <div>
                    <div className="text-6xl font-bold tracking-tighter text-indigo-500">{ragData?.total_questions || 0}</div>
                    <div className="text-foreground font-semibold mt-2 text-base">Tổng số câu hỏi đã gửi</div>
                  </div>
                </div>
              </div>
            </div>

            {/* RAG Secondary Metrics */}
            <div className="double-bezel-outer">
              <div className="double-bezel-inner p-8 flex flex-col justify-between h-full">
                <div className="text-muted font-bold tracking-wide text-xs uppercase">Độ dài câu trả lời TB</div>
                <div className="text-4xl font-bold tracking-tight text-purple-500">{ragData?.avg_answer_length || 0}</div>
              </div>
            </div>
            
            <div className="double-bezel-outer">
              <div className="double-bezel-inner p-8 flex flex-col justify-between h-full">
                <div className="text-muted font-bold tracking-wide text-xs uppercase">Truy xuất đa nguồn</div>
                <div className="text-4xl font-bold tracking-tight text-cyan-500">{ragData?.multi_source_pct || 0}%</div>
              </div>
            </div>

            {/* BKT Main Card (Span 2x2) */}
            <div className="md:col-span-2 row-span-2 double-bezel-outer group">
              <div className="double-bezel-inner p-8 flex flex-col justify-between h-full relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-premium"></div>
                <div className="relative z-10 flex items-center gap-3 text-emerald-500 mb-6">
                  <TrendUp className="w-6 h-6" weight="light" />
                  <span className="font-bold uppercase tracking-widest text-[10px]">Định vị tri thức (BKT)</span>
                </div>
                
                <div className="relative z-10 grid grid-cols-2 gap-8">
                  <div>
                    <div className="text-muted text-xs font-bold uppercase mb-1">Độ chính xác</div>
                    <div className="text-4xl md:text-5xl font-bold text-emerald-500">{((bktData?.accuracy || 0) * 100).toFixed(1)}%</div>
                  </div>
                  <div>
                    <div className="text-muted text-xs font-bold uppercase mb-1">Chỉ số AUC-ROC</div>
                    <div className="text-4xl md:text-5xl font-bold text-amber-500">{(bktData?.auc_roc || 0).toFixed(3)}</div>
                  </div>
                  <div>
                    <div className="text-muted text-xs font-bold uppercase mb-1">Log-Loss</div>
                    <div className="text-4xl md:text-5xl font-bold text-rose-500">{(bktData?.log_loss || 0).toFixed(3)}</div>
                  </div>
                  <div>
                    <div className="text-muted text-xs font-bold uppercase mb-1">Tổng câu trả lời</div>
                    <div className="text-4xl md:text-5xl font-bold text-foreground">{bktData?.total_answers || 0}</div>
                    <div className="text-xs text-muted font-semibold mt-2">{bktData?.correct_total || 0} đúng / {bktData?.wrong_total || 0} sai</div>
                  </div>
                </div>
              </div>
            </div>

            {/* BKT Distribution */}
            <div className="md:col-span-2 row-span-1 double-bezel-outer">
              <div className="double-bezel-inner p-8 flex flex-col justify-center h-full">
                <div className="flex items-center gap-2 mb-6">
                  <Lightbulb className="text-muted w-5 h-5" weight="light" />
                  <span className="text-xs font-bold uppercase tracking-wider text-muted">Phân phối mức độ tri thức</span>
                </div>
                <div className="flex justify-between w-full gap-4">
                  <div className="flex-1 flex flex-col items-center p-3 rounded-2xl bg-rose-500/10 border border-rose-500/20">
                    <div className="text-2xl font-bold text-rose-500 mb-1">{bktData?.distribution?.low_count || 0}</div>
                    <div className="text-[9px] uppercase tracking-wider text-rose-500/80 font-bold">Yếu (&lt;40%)</div>
                  </div>
                  <div className="flex-1 flex flex-col items-center p-3 rounded-2xl bg-amber-500/10 border border-amber-500/20">
                    <div className="text-2xl font-bold text-amber-500 mb-1">{bktData?.distribution?.mid_count || 0}</div>
                    <div className="text-[9px] uppercase tracking-wider text-amber-500/80 font-bold">TB (40-70%)</div>
                  </div>
                  <div className="flex-1 flex flex-col items-center p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20">
                    <div className="text-2xl font-bold text-emerald-500 mb-1">{bktData?.distribution?.high_count || 0}</div>
                    <div className="text-[9px] uppercase tracking-wider text-emerald-500/80 font-bold">Tốt (&gt;70%)</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Recommendations / Insights */}
            <div className="md:col-span-2 row-span-1 double-bezel-outer">
              <div className="double-bezel-inner p-8 flex flex-col justify-center h-full bg-card">
                <div className="text-xs font-bold uppercase tracking-wider text-muted mb-4">Phân tích & Khuyến nghị</div>
                <div className="text-base font-semibold leading-relaxed text-foreground">
                  {bktData?.accuracy < 0.6 ? (
                    "Độ chính xác của BKT đang dưới mức tối ưu. Hãy xem xét điều chỉnh ngưỡng hoặc tăng xác suất chuyển đổi trạng thái."
                  ) : bktData?.auc_roc < 0.6 ? (
                    "Chỉ số AUC-ROC thấp. Khả năng dự đoán của hệ thống gần như ngẫu nhiên. Nên giảm xác suất đoán mò (guess probability)."
                  ) : bktData?.log_loss > 0.8 ? (
                    "Log-loss ở mức cao nghiêm trọng. Xác suất BKT tính toán đang lệch nhiều so với thực tế."
                  ) : (
                    "Mọi thông số hoạt động bình thường. Mô hình BKT đang định vị chính xác mức độ hiểu bài của người dùng."
                  )}
                </div>
              </div>
            </div>

          </div>
        )}
      </div>
    </main>
  );
}
