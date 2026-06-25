"use client";

import { useEffect, useState } from "react";
import { api, getReportPreview, downloadReport } from "@/lib/api";
import { 
  Certificate, 
  FilePdf, 
  Sparkle, 
  BookOpen, 
  CheckCircle, 
  ArrowRight,
  ChartLine,
  Warning,
  ArrowClockwise
} from "@phosphor-icons/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { preprocessLaTeX, markdownComponents, quizMarkdownComponents } from "@/lib/latex";

interface StrengthOrWeakness {
  id: string;
  topic: string;
  probability: number;
}

interface ReviewQuestion {
  chunk_id: string;
  question: string;
  options: { [key: string]: string };
  answer: string;
  explanation: string;
}

interface ReportData {
  doc_name: string;
  overall_summary: string;
  overall_progress: number;
  total_chunks: number;
  mastered_chunks: number;
  strengths: StrengthOrWeakness[];
  weaknesses: StrengthOrWeakness[];
  quiz_stats: {
    total: number;
    correct: number;
    accuracy: number;
  };
  bloom_stats: {
    [key: string]: {
      correct: number;
      total: number;
      accuracy: number;
    };
  };
  recommended_review: ReviewQuestion[];
}

export default function ReportPage() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | "">("");
  const [loading, setLoading] = useState<boolean>(false);
  const [pdfLoading, setPdfLoading] = useState<boolean>(false);
  const [reportData, setReportData] = useState<ReportData | null>(null);

  const bloomConfig: { [key: string]: { name: string; color: string; bg: string; fill: string } } = {
    remember: { name: "Nhận biết (Remember)", color: "text-blue-500", bg: "bg-blue-500/10", fill: "bg-blue-500" },
    understand: { name: "Thông hiểu (Understand)", color: "text-purple-500", bg: "bg-purple-500/10", fill: "bg-purple-500" },
    apply: { name: "Vận dụng (Apply)", color: "text-orange-500", bg: "bg-orange-500/10", fill: "bg-orange-500" },
    analyze: { name: "Vận dụng cao (Analyze)", color: "text-rose-500", bg: "bg-rose-500/10", fill: "bg-rose-500" },
  };

  useEffect(() => {
    const fetchDocs = async () => {
      const { data } = await api.get("/documents");
      if (data && data.documents) {
        const indexedDocs = data.documents.filter((d: any) => d.status === "INDEXED");
        setDocuments(indexedDocs);
        if (indexedDocs.length > 0) {
          setSelectedDocId(indexedDocs[0].id);
        }
      }
    };
    fetchDocs();
  }, []);

  const handleFetchReport = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    try {
      const response = await getReportPreview(Number(selectedDocId));
      if (response && response.data) {
        setReportData(response.data);
      }
    } catch (err) {
      console.error("Lỗi lấy dữ liệu báo cáo:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!selectedDocId || !reportData) return;
    setPdfLoading(true);
    try {
      const blob = await downloadReport(Number(selectedDocId));
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      
      // Đặt tên file theo tên tài liệu gốc
      const selectedDoc = documents.find(d => d.id === Number(selectedDocId));
      const docName = selectedDoc ? selectedDoc.file_name : `doc_${selectedDocId}`;
      a.download = `learning_report_${docName}.pdf`;
      
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Lỗi tải PDF:", err);
    } finally {
      setPdfLoading(false);
    }
  };

  const selectedDoc = documents.find(d => d.id === Number(selectedDocId));

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 py-8 md:py-16 pb-56">
      {/* BACKGROUND DECOR DECORATIONS */}
      <div className="mesh-glow-violet top-20 right-10" />
      <div className="mesh-glow-emerald bottom-10 left-5" />

      {/* HEADER */}
      <div className="flex items-center gap-3 mb-8 md:mb-12">
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 rounded-2xl">
          <Certificate weight="fill" className="w-8 h-8" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Báo cáo Học tập</h1>
          <p className="text-muted text-sm mt-1">Xuất và thống kê dữ liệu năng lực BKT & Bloom</p>
        </div>
      </div>

      {/* MAIN LAYOUT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* LEFT COLUMN: CONTROLS */}
        <div className="lg:col-span-1 double-bezel-outer">
          <div className="double-bezel-inner p-6 border border-border space-y-6">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Sparkle className="w-5 h-5 text-emerald-500" /> Tùy chọn Báo cáo
            </h2>

            {/* Document select */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-muted mb-2">Chọn tài liệu</label>
              {documents.length === 0 ? (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-400">
                  Chưa có tài liệu hoàn tất (INDEXED). Vui lòng upload trước.
                </div>
              ) : (
                <select
                  value={selectedDocId}
                  onChange={(e) => {
                    setSelectedDocId(Number(e.target.value));
                    setReportData(null);
                  }}
                  className="w-full bg-background border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-emerald-500"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.file_name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Action buttons */}
            <div className="space-y-3 pt-2">
              <button
                onClick={handleFetchReport}
                disabled={loading || documents.length === 0 || !selectedDocId}
                className="w-full flex items-center justify-center gap-2 py-3 bg-foreground text-background font-bold rounded-full transition-premium-fast hover:scale-[1.02] active:scale-[0.99] disabled:opacity-50"
              >
                {loading ? (
                  <div className="w-5 h-5 border-2 border-background border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <BookOpen className="w-5 h-5" /> Tải dữ liệu báo cáo
                  </>
                )}
              </button>

              {/* <button
                onClick={handleDownloadPdf}
                disabled={pdfLoading || !reportData}
                className="w-full flex items-center justify-center gap-2 py-3 bg-emerald-500 hover:bg-emerald-600 text-black font-bold rounded-full transition-premium-fast hover:scale-[1.02] active:scale-[0.99] disabled:opacity-50 disabled:pointer-events-none shadow-lg"
              >
                {pdfLoading ? (
                  <div className="w-5 h-5 border-2 border-black border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <FilePdf className="w-5 h-5" /> Xuất báo cáo PDF
                  </>
                )}
              </button> */}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: PREVIEW PANEL */}
        <div className="lg:col-span-2 space-y-6">
          {!reportData ? (
            <div className="double-bezel-outer w-full text-center py-20">
              <div className="double-bezel-inner p-10 border border-border flex flex-col items-center justify-center space-y-3">
                <Certificate weight="light" className="w-16 h-16 text-muted" />
                <h3 className="text-xl font-bold">Chưa tải dữ liệu báo cáo</h3>
                <p className="text-sm text-muted max-w-sm">
                  Chọn tài liệu ở cột bên trái và bấm nút "Tải dữ liệu báo cáo" để phân tích chi tiết.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-6 animate-fade-in">
              {/* Document Overview Header */}
              <div className="bg-card border border-border rounded-3xl p-6 md:p-8 space-y-4">
                <div className="flex justify-between items-start gap-4">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-500">Tên tài liệu</span>
                    <h2 className="text-xl font-bold mt-1 text-foreground">{reportData.doc_name}</h2>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted">Độ hiểu bài</span>
                    <div className="text-3xl font-black text-emerald-500 mt-1">{reportData.overall_progress}%</div>
                  </div>
                </div>

                <div className="border-t border-border pt-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-muted mb-2">Tóm tắt tài liệu AI (Summary)</h4>
                  <div className="prose prose-sm prose-zinc dark:prose-invert max-w-none text-muted leading-relaxed">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={markdownComponents}
                    >
                      {preprocessLaTeX(reportData.overall_summary)}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>

              {/* Progress and statistics breakdown grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Mastered Progress Card */}
                <div className="bg-card border border-border rounded-3xl p-6 flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs font-bold text-muted uppercase tracking-wider">Tiến trình tri thức</span>
                    <div className="text-3xl font-black">{reportData.mastered_chunks} / {reportData.total_chunks}</div>
                    <p className="text-xs text-muted">Số phân đoạn đã nắm vững (BKT &ge; 80%)</p>
                  </div>
                  {/* Progress ring SVG */}
                  <div className="relative w-18 h-18 shrink-0">
                    <svg className="w-full h-full transform -rotate-90">
                      <circle cx="36" cy="36" r="28" className="stroke-border fill-transparent" strokeWidth="6" />
                      <circle cx="36" cy="36" r="28" className="stroke-emerald-500 fill-transparent transition-all duration-500" strokeWidth="6" 
                              strokeDasharray={`${2 * Math.PI * 28}`}
                              strokeDashoffset={`${2 * Math.PI * 28 * (1 - reportData.overall_progress / 100)}`}
                              strokeLinecap="round" />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                      {reportData.overall_progress}%
                    </div>
                  </div>
                </div>

                {/* Practice Score accuracy */}
                <div className="bg-card border border-border rounded-3xl p-6 flex items-center justify-between">
                  <div className="space-y-1">
                    <span className="text-xs font-bold text-muted uppercase tracking-wider">Hiệu suất luyện tập</span>
                    <div className="text-3xl font-black">
                      {reportData.quiz_stats.correct} / {reportData.quiz_stats.total}
                    </div>
                    <p className="text-xs text-muted">
                      Độ chính xác: {Math.round(reportData.quiz_stats.accuracy * 100)}%
                    </p>
                  </div>
                  <div className="p-3.5 bg-accent-color/10 border border-accent-color/20 text-accent-color rounded-2xl">
                    <ChartLine className="w-8 h-8" />
                  </div>
                </div>
              </div>

              {/* Strengths & Weaknesses Grids */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Strengths (Thế mạnh) */}
                <div className="bg-card border border-border rounded-3xl p-6 space-y-4">
                  <h3 className="text-sm font-bold text-emerald-500 uppercase tracking-widest flex items-center gap-1.5">
                    <CheckCircle weight="fill" className="w-5 h-5 text-emerald-500" /> Điểm mạnh tri thức
                  </h3>
                  <div className="space-y-2">
                    {reportData.strengths.length === 0 ? (
                      <p className="text-xs text-muted italic">Chưa có chủ đề nào thấu hiểu xuất sắc.</p>
                    ) : (
                      reportData.strengths.map((s, idx) => (
                        <div key={s.id} className="flex justify-between items-center text-sm p-2 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
                          <span className="truncate pr-4 font-medium text-foreground">{idx + 1}. {s.topic}</span>
                          <span className="text-xs font-bold text-emerald-500 shrink-0">{s.probability}%</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Weaknesses (Lỗ hổng) */}
                <div className="bg-card border border-border rounded-3xl p-6 space-y-4">
                  <h3 className="text-sm font-bold text-rose-500 uppercase tracking-widest flex items-center gap-1.5">
                    <Warning weight="fill" className="w-5 h-5 text-rose-500" /> Lỗ hổng cần ôn tập
                  </h3>
                  <div className="space-y-2">
                    {reportData.weaknesses.length === 0 ? (
                      <p className="text-xs text-muted italic">Chúc mừng! Không có lỗ hổng tri thức.</p>
                    ) : (
                      reportData.weaknesses.map((w, idx) => (
                        <div key={w.id} className="flex justify-between items-center text-sm p-2 bg-rose-500/5 border border-rose-500/10 rounded-xl">
                          <span className="truncate pr-4 font-medium text-foreground">{idx + 1}. {w.topic}</span>
                          <span className="text-xs font-bold text-rose-500 shrink-0">{w.probability}%</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Bloom breakdown page details */}
              <div className="bg-card border border-border rounded-3xl p-6 md:p-8 space-y-5">
                <h3 className="text-base font-bold text-foreground">Phân bổ cấp độ nhận thức Bloom's Taxonomy</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.keys(bloomConfig).map((key) => {
                    const cfg = bloomConfig[key];
                    const stats = reportData.bloom_stats[key] || { correct: 0, total: 0, accuracy: 0.0 };
                    const pct = Math.round(stats.accuracy * 100);
                    return (
                      <div key={key} className="p-4 bg-background border border-border rounded-2xl space-y-2">
                        <div className="flex justify-between items-center text-xs">
                          <span className={`font-semibold ${cfg.color}`}>{cfg.name}</span>
                          <span className="text-muted font-bold">{stats.correct}/{stats.total} câu</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 bg-border h-2.5 rounded-full overflow-hidden">
                            <div className={`h-full ${cfg.fill}`} style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-xs font-black w-8 text-right">{pct}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Recommended Review Exercises (Exercises) */}
              <div className="bg-card border border-border rounded-3xl p-6 md:p-8 space-y-5">
                <h3 className="text-base font-bold text-emerald-500 uppercase tracking-widest flex items-center gap-1.5">
                  💡 Bài tập ôn tập đề xuất (AI Generated)
                </h3>
                {reportData.recommended_review.length === 0 ? (
                  <p className="text-sm text-muted italic">Đang cập nhật hoặc bạn đã hoàn thành tốt tài liệu.</p>
                ) : (
                  <div className="space-y-6">
                    {reportData.recommended_review.map((q, idx) => (
                      <div key={q.chunk_id} className="border border-border rounded-2xl p-5 space-y-3 bg-background/50">
                        <div className="text-sm md:text-base font-semibold leading-relaxed">
                          Câu {idx + 1}: <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={markdownComponents}>{preprocessLaTeX(q.question)}</ReactMarkdown>
                        </div>
                        {/* Options list */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-muted">
                          {Object.keys(q.options).map((optKey) => (
                            <div key={optKey} className="flex items-center gap-2 p-2.5 bg-card border border-border rounded-xl">
                              <span className="font-bold border border-border rounded px-1 text-[10px]">{optKey}</span>
                              <span className="truncate">
                                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={quizMarkdownComponents}>
                                  {preprocessLaTeX(q.options[optKey])}
                                </ReactMarkdown>
                              </span>
                            </div>
                          ))}
                        </div>
                        {/* Answer explanation */}
                        <div className="text-xs text-emerald-500 bg-emerald-500/5 border border-emerald-500/10 rounded-xl p-3 leading-relaxed">
                          <span className="font-bold">Đáp án đúng: {q.answer}</span>
                          <span className="block mt-1 text-muted">
                            Giải thích:{" "}
                            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={quizMarkdownComponents}>
                              {preprocessLaTeX(q.explanation)}
                            </ReactMarkdown>
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
