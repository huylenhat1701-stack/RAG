"use client";

import { useEffect, useState } from "react";
import { api, createQuiz, submitQuizAnswer, getBloomStats } from "@/lib/api";
import { 
  Brain, 
  ArrowRight, 
  CheckCircle, 
  XCircle, 
  ArrowClockwise, 
  Certificate, 
  CaretRight, 
  FileText,
  Sparkle
} from "@phosphor-icons/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { preprocessLaTeX, markdownComponents, quizMarkdownComponents } from "@/lib/latex";
import Link from "next/link";

interface QuizQuestion {
  id: number;
  question: string;
  options: { [key: string]: string };
  answer: string;
  correct_option?: string;
  explanation?: string;
  step_by_step_explanation?: string;
  chunk_id: string;
  bloom_level: string;
}

export default function QuizPage() {
  // Phase state: "setup" | "active" | "results"
  const [phase, setPhase] = useState<"setup" | "active" | "results">("setup");
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<number | "">("");
  const [bloomLevel, setBloomLevel] = useState<string | null>(null);
  const [count, setCount] = useState<number>(5);
  const [loading, setLoading] = useState<boolean>(false);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  
  // Active Quiz State
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [isAnswerSubmitted, setIsAnswerSubmitted] = useState<boolean>(false);
  const [bktProbability, setBktProbability] = useState<number | null>(null);
  const [answersLog, setAnswersLog] = useState<{ id: number; isCorrect: boolean; bloomLevel: string }[]>([]);

  // Bloom Statistics
  const [bloomStats, setBloomStats] = useState<any>(null);

  // Colors for Bloom Levels
  const bloomConfig: { [key: string]: { name: string; desc: string; color: string; border: string; bg: string } } = {
    remember: {
      name: "Nhớ (Remember)",
      desc: "Nhớ lại định nghĩa, khái niệm, công thức chính xác.",
      color: "text-blue-500",
      border: "border-blue-500/30",
      bg: "bg-blue-500/10",
    },
    understand: {
      name: "Hiểu (Understand)",
      desc: "Giải thích bằng lời, so sánh hoặc phân loại khái niệm.",
      color: "text-purple-500",
      border: "border-purple-500/30",
      bg: "bg-purple-500/10",
    },
    apply: {
      name: "Vận dụng (Apply)",
      desc: "Tình huống thực tế yêu cầu áp dụng kiến thức để giải quyết.",
      color: "text-orange-500",
      border: "border-orange-500/30",
      bg: "bg-orange-500/10",
    },
    analyze: {
      name: "Phân tích (Analyze)",
      desc: "Phân tích nguyên nhân-kết quả, suy luận logic.",
      color: "text-rose-500",
      border: "border-rose-500/30",
      bg: "bg-rose-500/10",
    },
  };

  useEffect(() => {
    // Load documents list
    const fetchDocs = async () => {
      const { data } = await api.get("/documents");
      if (data && data.documents) {
        // Lọc tài liệu đã INDEXED
        const indexedDocs = data.documents.filter((d: any) => d.status === "INDEXED");
        setDocuments(indexedDocs);
        if (indexedDocs.length > 0) {
          setSelectedDocId(indexedDocs[0].id);
        }
      }
    };
    fetchDocs();
  }, []);

  const handleStartQuiz = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    try {
      const response = await createQuiz(Number(selectedDocId), count, bloomLevel || undefined);
      if (response && response.data && response.data.questions) {
        setQuestions(response.data.questions);
        setCurrentIndex(0);
        setSelectedOption(null);
        setIsAnswerSubmitted(false);
        setBktProbability(null);
        setAnswersLog([]);
        setPhase("active");
      }
    } catch (err) {
      console.error("Lỗi tạo quiz:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleOptionSelect = (option: string) => {
    if (isAnswerSubmitted) return;
    setSelectedOption(option);
  };

  const handleSubmitAnswer = async () => {
    if (!selectedOption || isAnswerSubmitted || !selectedDocId) return;
    setIsAnswerSubmitted(true);

    const question = questions[currentIndex];
    const isCorrect = selectedOption === question.answer;

    // Log kết quả câu trả lời
    setAnswersLog((prev) => [
      ...prev,
      { id: question.id, isCorrect, bloomLevel: question.bloom_level },
    ]);

    // Gửi kết quả lên backend để cập nhật BKT
    try {
      const response = await submitQuizAnswer(
        Number(selectedDocId),
        question.chunk_id,
        isCorrect,
        question.bloom_level
      );
      if (response && response.data) {
        setBktProbability(response.data.new_probability);
      }
    } catch (err) {
      console.error("Lỗi nộp đáp án:", err);
    }
  };

  const handleNextQuestion = () => {
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOption(null);
      setIsAnswerSubmitted(false);
      setBktProbability(null);
    } else {
      // Hoàn thành quiz, tải Bloom Stats và đổi phase
      fetchBloomStats();
      setPhase("results");
    }
  };

  const fetchBloomStats = async () => {
    if (!selectedDocId) return;
    try {
      const response = await getBloomStats(Number(selectedDocId));
      if (response && response.data) {
        setBloomStats(response.data);
      }
    } catch (err) {
      console.error("Lỗi tải thống kê Bloom:", err);
    }
  };

  const handleRestart = () => {
    setPhase("setup");
    setQuestions([]);
    setAnswersLog([]);
  };

  const activeQuestion = questions[currentIndex];
  const activeBloomColor = activeQuestion ? (bloomConfig[activeQuestion.bloom_level]?.color || "text-emerald-500") : "text-emerald-500";
  const activeBloomBg = activeQuestion ? (bloomConfig[activeQuestion.bloom_level]?.bg || "bg-emerald-500/10") : "bg-emerald-500/10";

  return (
    <div className="flex-1 w-full max-w-5xl mx-auto px-4 py-8 md:py-16 pb-56">
      {/* BACKGROUND DECORATIONS */}
      <div className="mesh-glow-violet top-10 left-10" />
      <div className="mesh-glow-emerald bottom-20 right-10" />

      {/* HEADER */}
      <div className="flex items-center gap-3 mb-8 md:mb-12">
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 rounded-2xl">
          <Brain weight="fill" className="w-8 h-8" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Bloom's Taxonomy Quiz</h1>
          <p className="text-muted text-sm mt-1">Luyện tập cá nhân hóa & củng cố lỗ hổng kiến thức</p>
        </div>
      </div>

      {/* PHASE 1: SETUP */}
      {phase === "setup" && (
        <div className="w-full max-w-2xl mx-auto double-bezel-outer">
          <div className="double-bezel-inner p-6 md:p-10 border border-border">
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
              <Sparkle className="w-5 h-5 text-emerald-500" /> Cấu hình bài Quiz của bạn
            </h2>

            {/* Document Selector */}
            <div className="mb-6">
              <label className="block text-sm font-semibold mb-2">Chọn tài liệu ôn tập</label>
              {documents.length === 0 ? (
                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">
                  Chưa có tài liệu nào được xử lý hoàn tất (INDEXED). Vui lòng upload tài liệu trước.
                </div>
              ) : (
                <select
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(Number(e.target.value))}
                  className="w-full bg-background border border-border rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-emerald-500"
                >
                  {documents.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.file_name} ({doc.chunk_count} chunks)
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Bloom Level Selector */}
            <div className="mb-8">
              <label className="block text-sm font-semibold mb-3">Chọn cấp độ Bloom's Taxonomy</label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setBloomLevel(null)}
                  className={`flex flex-col text-left p-4 rounded-2xl border transition-all duration-300 ${
                    bloomLevel === null
                      ? "border-emerald-500 bg-emerald-500/5 shadow-md"
                      : "border-border hover:border-muted bg-card"
                  }`}
                >
                  <span className="font-semibold text-sm">Tất cả cấp độ</span>
                  <span className="text-xs text-muted mt-1">Hệ thống sẽ sinh ngẫu nhiên các cấp độ câu hỏi phù hợp.</span>
                </button>
                {Object.keys(bloomConfig).map((level) => {
                  const cfg = bloomConfig[level];
                  const isSelected = bloomLevel === level;
                  return (
                    <button
                      key={level}
                      type="button"
                      onClick={() => setBloomLevel(level)}
                      className={`flex flex-col text-left p-4 rounded-2xl border transition-all duration-300 ${
                        isSelected
                          ? `border-emerald-500 bg-emerald-500/5 shadow-md`
                          : "border-border hover:border-muted bg-card"
                      }`}
                    >
                      <span className={`font-semibold text-sm flex items-center gap-1.5 ${cfg.color}`}>
                        <span className={`w-2 h-2 rounded-full ${cfg.bg}`} />
                        {cfg.name}
                      </span>
                      <span className="text-xs text-muted mt-1">{cfg.desc}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Question count Slider */}
            <div className="mb-8">
              <div className="flex justify-between items-center mb-2">
                <label className="text-sm font-semibold">Số lượng câu hỏi</label>
                <span className="text-sm font-bold text-emerald-500">{count} câu</span>
              </div>
              <input
                type="range"
                min="3"
                max="20"
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="w-full accent-emerald-500 bg-border h-2 rounded-lg cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-muted mt-1 px-1">
                <span>3 câu</span>
                <span>10 câu</span>
                <span>20 câu</span>
              </div>
            </div>

            {/* Submit Button */}
            <button
              onClick={handleStartQuiz}
              disabled={loading || documents.length === 0 || !selectedDocId}
              className="w-full flex items-center justify-center gap-2 py-4 bg-emerald-500 hover:bg-emerald-600 active:scale-[0.99] text-black font-bold rounded-full shadow-lg transition-premium-fast disabled:opacity-50 disabled:pointer-events-none"
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-black border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  Bắt đầu làm Quiz <ArrowRight weight="bold" className="w-5 h-5" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* PHASE 2: ACTIVE QUIZ */}
      {phase === "active" && activeQuestion && (
        <div className="w-full max-w-3xl mx-auto space-y-6">
          {/* Progress Bar & Header info */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between text-xs text-muted font-bold tracking-widest uppercase">
              <span>CÂU HỎI {currentIndex + 1} / {questions.length}</span>
              <span className={`px-2 py-0.5 rounded-full ${activeBloomBg} ${activeBloomColor}`}>
                Bloom: {activeQuestion.bloom_level.toUpperCase()}
              </span>
            </div>
            <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all duration-300 ${
                  activeQuestion.bloom_level === "remember" ? "bg-blue-500" :
                  activeQuestion.bloom_level === "understand" ? "bg-purple-500" :
                  activeQuestion.bloom_level === "apply" ? "bg-orange-500" : "bg-rose-500"
                }`}
                style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
              />
            </div>
          </div>

          {/* Question Card */}
          <div className="double-bezel-outer w-full">
            <div className="double-bezel-inner p-6 md:p-8 border border-border">
              <div className="prose prose-zinc dark:prose-invert max-w-none text-base md:text-lg font-medium leading-relaxed mb-6">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                  components={markdownComponents}
                >
                  {preprocessLaTeX(activeQuestion.question)}
                </ReactMarkdown>
              </div>

              {/* Options Grid */}
              <div className="grid grid-cols-1 gap-3.5 mb-6">
                {Object.keys(activeQuestion.options).map((key) => {
                  const optionText = activeQuestion.options[key];
                  const isSelected = selectedOption === key;
                  const isCorrectAnswer = activeQuestion.answer === key;
                  
                  let buttonClass = "border-border hover:border-muted hover:bg-foreground/5 bg-card";
                  let iconElement = null;

                  if (isAnswerSubmitted) {
                    if (isCorrectAnswer) {
                      buttonClass = "border-emerald-500 bg-emerald-500/10 text-emerald-500 font-semibold";
                      iconElement = <CheckCircle weight="fill" className="w-5 h-5 text-emerald-500 shrink-0" />;
                    } else if (isSelected) {
                      buttonClass = "border-rose-500 bg-rose-500/10 text-rose-500 font-semibold";
                      iconElement = <XCircle weight="fill" className="w-5 h-5 text-rose-500 shrink-0" />;
                    } else {
                      buttonClass = "border-border opacity-50 bg-card";
                    }
                  } else if (isSelected) {
                    buttonClass = "border-emerald-500 bg-emerald-500/5 shadow-md";
                  }

                  return (
                    <button
                      key={key}
                      onClick={() => handleOptionSelect(key)}
                      disabled={isAnswerSubmitted}
                      className={`flex items-start gap-3 w-full text-left px-5 py-4.5 rounded-2xl border transition-all duration-200 ${buttonClass}`}
                    >
                      <span className="font-bold border border-current/25 rounded-md px-1.5 text-xs mt-0.5">
                        {key}
                      </span>
                      <div className="flex-1 text-sm md:text-base leading-relaxed font-normal">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypeRaw]}
                          components={quizMarkdownComponents}
                        >
                          {preprocessLaTeX(optionText)}
                        </ReactMarkdown>
                      </div>
                      {iconElement}
                    </button>
                  );
                })}
              </div>

              {/* Action Buttons */}
              <div className="flex justify-between items-center gap-4">
                {isAnswerSubmitted && bktProbability !== null && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted">BKT Probability:</span>
                    <div className="flex items-center gap-1">
                      <div className="w-20 bg-border h-2 rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${bktProbability >= 80 ? "bg-emerald-500" : bktProbability < 60 ? "bg-rose-500" : "bg-amber-400"}`}
                          style={{ width: `${bktProbability}%` }}
                        />
                      </div>
                      <span className="text-xs font-bold">{bktProbability}%</span>
                    </div>
                  </div>
                )}
                <div className="flex items-center gap-3 ml-auto">
                  {!isAnswerSubmitted ? (
                    <button
                      onClick={handleSubmitAnswer}
                      disabled={!selectedOption}
                      className="px-6 py-3 bg-emerald-500 hover:bg-emerald-600 text-black font-bold rounded-full shadow-md active:scale-95 disabled:opacity-50 disabled:pointer-events-none transition-premium-fast"
                    >
                      Xác nhận
                    </button>
                  ) : (
                    <button
                      onClick={handleNextQuestion}
                      className="flex items-center gap-1.5 px-6 py-3 bg-foreground text-background font-bold rounded-full shadow-md active:scale-95 transition-premium-fast"
                    >
                      {currentIndex + 1 === questions.length ? "Xem kết quả" : "Câu tiếp theo"}
                      <CaretRight weight="bold" className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Explanation panel */}
          {isAnswerSubmitted && (
            <div className="bg-card/45 border border-border rounded-3xl p-6 space-y-4">
              <div>
                <h3 className="text-sm font-bold text-emerald-500 uppercase tracking-wider mb-1">Giải thích đáp án</h3>
                <div className="prose prose-sm prose-zinc dark:prose-invert max-w-none text-muted leading-relaxed">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={markdownComponents}
                  >
                    {preprocessLaTeX(activeQuestion.explanation || "")}
                  </ReactMarkdown>
                </div>
              </div>
              {activeQuestion.step_by_step_explanation && (
                <div className="border-t border-border pt-4">
                  <h3 className="text-sm font-bold text-accent-color uppercase tracking-wider mb-2">Lời giải chi tiết (CoT Math)</h3>
                  <div className="prose prose-sm prose-zinc dark:prose-invert max-w-none text-muted leading-relaxed">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={markdownComponents}
                    >
                      {preprocessLaTeX(activeQuestion.step_by_step_explanation)}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* PHASE 3: RESULTS */}
      {phase === "results" && (
        <div className="w-full max-w-3xl mx-auto space-y-8">
          {/* Summary Score Card */}
          <div className="double-bezel-outer w-full text-center">
            <div className="double-bezel-inner p-8 border border-border space-y-4">
              <h2 className="text-2xl font-bold">Kết quả bài Quiz</h2>
              <div className="flex justify-center items-center gap-1.5 text-5xl font-black">
                <span className="text-emerald-500">
                  {answersLog.filter((a) => a.isCorrect).length}
                </span>
                <span className="text-muted">/</span>
                <span>{questions.length}</span>
              </div>
              <p className="text-sm text-muted">
                Đúng {answersLog.filter((a) => a.isCorrect).length} câu hỏi.
                Tỷ lệ chính xác {Math.round((answersLog.filter((a) => a.isCorrect).length / questions.length) * 100)}%.
              </p>
            </div>
          </div>

          {/* Bloom Analytics Panel */}
          {bloomStats && (
            <div className="bg-card border border-border rounded-3xl p-6 md:p-8 space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Certificate className="w-5 h-5 text-emerald-500" /> Thống kê theo cấp độ Bloom
              </h3>
              
              <div className="space-y-5">
                {Object.keys(bloomConfig).map((level) => {
                  const cfg = bloomConfig[level];
                  const stats = bloomStats[level] || { correct: 0, total: 0, accuracy: 0.0 };
                  const pct = Math.round(stats.accuracy * 100);

                  return (
                    <div key={level} className="space-y-2">
                      <div className="flex justify-between items-center text-sm">
                        <span className="font-semibold">{cfg.name}</span>
                        <span className="text-xs text-muted">
                          {stats.correct}/{stats.total} đúng ({pct}%)
                        </span>
                      </div>
                      <div className="w-full bg-border h-4 rounded-full overflow-hidden relative">
                        <div 
                          className={`h-full transition-all duration-500 ${
                            level === "remember" ? "bg-blue-500" :
                            level === "understand" ? "bg-purple-500" :
                            level === "apply" ? "bg-orange-500" : "bg-rose-500"
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Insights */}
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-4.5 text-sm text-muted leading-relaxed">
                <span className="font-bold text-foreground">💡 Gợi ý học tập: </span>
                {(() => {
                  // Tìm Bloom level có accuracy thấp nhất
                  let lowestLvl = "";
                  let lowestAcc = 2.0;
                  Object.keys(bloomConfig).forEach((key) => {
                    const stats = bloomStats[key];
                    if (stats && stats.total > 0 && stats.accuracy < lowestAcc) {
                      lowestAcc = stats.accuracy;
                      lowestLvl = key;
                    }
                  });

                  if (lowestLvl && lowestAcc < 0.60) {
                    return `Hệ thống nhận thấy kết quả của bạn ở phần "${bloomConfig[lowestLvl].name}" còn chưa cao (${Math.round(lowestAcc * 100)}%). Bạn nên tập trung đọc kỹ lại các khái niệm tương quan và tạo Quiz ôn tập chuyên biệt cho cấp độ này.`;
                  }
                  return "Tuyệt vời! Bạn đang có phong độ làm bài rất đồng đều trên mọi cấp độ tư duy nhận thức.";
                })()}
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row justify-center items-center gap-4">
            <button
              onClick={handleRestart}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3.5 border border-border hover:border-muted rounded-full font-bold shadow-md bg-card transition-premium-fast"
            >
              <ArrowClockwise className="w-5 h-5" /> Làm lại Quiz
            </button>
            <Link
              href="/report"
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3.5 bg-emerald-500 hover:bg-emerald-600 text-black font-bold rounded-full shadow-lg transition-premium-fast"
            >
              <FileText className="w-5 h-5" /> Xem báo cáo học tập
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
