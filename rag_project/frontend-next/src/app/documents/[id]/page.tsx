"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, apiClient } from "@/lib/api";
import { CaretLeft, BookOpen, MagicWand, Trophy, FileText, CheckCircle, XCircle } from "@phosphor-icons/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { preprocessLaTeX, markdownComponents, quizMarkdownComponents } from "@/lib/latex";

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const docId = params.id as string;

  const [activeTab, setActiveTab] = useState<"read" | "summary" | "quiz">("read");
  const [loading, setLoading] = useState(false);

  // Content Data
  const [content, setContent] = useState("");
  const [fileType, setFileType] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  
  // Preview States
  const [viewMode, setViewMode] = useState<"text" | "preview">("preview");
  const [docBlob, setDocBlob] = useState<Blob | null>(null);
  const [blobUrl, setBlobUrl] = useState<string>("");
  const [blobLoading, setBlobLoading] = useState(false);
  
  // Summary Data
  const [summary, setSummary] = useState("");
  
  // Quiz Data
  const [quizCount, setQuizCount] = useState(5);
  const [quizData, setQuizData] = useState<any[]>([]);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, string>>({});
  const [quizSubmitted, setQuizSubmitted] = useState<Record<number, boolean>>({});

  useEffect(() => {
    fetchContent();
  }, [docId]);

  const fetchContent = async () => {
    setLoading(true);
    const { data } = await api.get(`/documents/${docId}/content`);
    if (data) {
      if (data.content) {
        setContent(data.content);
      }
      if (data.file_type) {
        setFileType(data.file_type);
        if (data.file_type === "pdf" || data.file_type === "docx") {
          setViewMode("preview");
        } else {
          setViewMode("text");
        }
      }
      if (data.file_name) {
        setFileName(data.file_name);
      }
    }
    setLoading(false);
  };

  const fetchBlob = async () => {
    if (docBlob) return docBlob;
    setBlobLoading(true);
    try {
      const response = await apiClient.get(`/documents/${docId}/download?source=original`, {
        responseType: 'blob'
      });
      const blob = response.data;
      setDocBlob(blob);
      if (fileType === "pdf") {
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
      }
      setBlobLoading(false);
      return blob;
    } catch (error) {
      console.error("Failed to fetch document blob:", error);
      setBlobLoading(false);
      return null;
    }
  };

  useEffect(() => {
    if (activeTab === "read" && viewMode === "preview" && (fileType === "pdf" || fileType === "docx")) {
      fetchBlob();
    }
  }, [docId, activeTab, viewMode, fileType]);

  useEffect(() => {
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [blobUrl]);

  useEffect(() => {
    let active = true;
    if (activeTab === "read" && viewMode === "preview" && fileType === "docx" && docBlob && !blobLoading) {
      const renderDocx = async () => {
        try {
          const docx = await import("docx-preview");
          if (!active) return;
          const container = document.getElementById("docx-container");
          if (container) {
            container.innerHTML = "";
            await docx.renderAsync(docBlob, container, undefined, {
              className: "docx",
              inWrapper: true,
              ignoreWidth: false,
              ignoreHeight: false,
              ignoreFonts: false,
              breakPages: true,
              debug: false,
            });
          }
        } catch (error) {
          console.error("docx-preview rendering failed:", error);
        }
      };
      
      const timer = setTimeout(renderDocx, 50);
      return () => {
        active = false;
        clearTimeout(timer);
      };
    }
  }, [activeTab, viewMode, fileType, docBlob, blobLoading]);

  const handleSummarize = async () => {
    setLoading(true);
    const { data } = await api.post(`/documents/${docId}/summarize`);
    if (data && data.summary) {
      setSummary(data.summary);
      setActiveTab("summary");
    }
    setLoading(false);
  };

  const handleGenerateQuiz = async () => {
    setLoading(true);
    const { data } = await api.post(`/documents/${docId}/quiz`, { count: quizCount });
    if (data && data.questions && Array.isArray(data.questions)) {
      setQuizData(data.questions);
      setQuizAnswers({});
      setQuizSubmitted({});
    }
    setLoading(false);
  };

  const handleAnswerSelect = (qIndex: number, optionKey: string) => {
    if (quizSubmitted[qIndex]) return;
    setQuizAnswers(prev => ({ ...prev, [qIndex]: optionKey }));
  };

  const handleQuizSubmit = async (qIndex: number) => {
    const question = quizData[qIndex];
    const chosen = quizAnswers[qIndex];
    if (!chosen) return;

    const isCorrect = chosen === question.correct_option;
    
    // Call backend to update BKT
    if (question.chunk_id) {
      await api.post(`/documents/${docId}/quiz/submit`, {
        chunk_id: question.chunk_id,
        is_correct: isCorrect
      });
    }

    setQuizSubmitted(prev => ({ ...prev, [qIndex]: true }));
  };

  return (
    <main className="min-h-screen bg-background text-foreground p-8 md:p-16 pb-36 relative overflow-hidden transition-colors duration-300">
      {/* Background ambient light */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] mesh-glow-violet opacity-40 dark:opacity-70"></div>
        <div className="absolute bottom-[-10%] right-[-10%] mesh-glow-emerald opacity-40 dark:opacity-70"></div>
      </div>

      <div className="max-w-5xl mx-auto relative z-10">
        
        {/* Header */}
        <button 
          onClick={() => router.push("/documents")}
          className="flex items-center gap-2 text-muted hover:text-foreground transition-premium mb-8 font-semibold text-sm hover:scale-105 active:scale-[0.98] cursor-pointer"
        >
          <CaretLeft weight="bold" /> Quay lại danh sách tài liệu
        </button>

        {/* Double Bezel for Details Header */}
        <div className="double-bezel-outer mb-8">
          <div className="double-bezel-inner p-8">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
              <div>
                <span className="rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.2em] font-bold text-muted bg-foreground/5 border border-border mb-3 inline-block">
                  Thông tin tệp tin
                </span>
                <h1 className="text-3xl font-bold tracking-tight text-foreground line-clamp-1">{fileName || "Chi tiết tài liệu"}</h1>
                <p className="text-xs text-muted mt-2 font-mono">ID: {docId}</p>
              </div>
              
              <div className="flex bg-foreground/5 border border-border p-1 rounded-full overflow-x-auto">
                <button 
                  onClick={() => setActiveTab("read")}
                  className={`px-5 py-2 rounded-full text-xs font-bold transition-premium flex items-center gap-2 whitespace-nowrap hover:scale-105 active:scale-[0.98] ${
                    activeTab === "read" 
                      ? "bg-foreground text-background shadow-md" 
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  <BookOpen weight="light" className="w-4 h-4" /> Đọc tài liệu
                </button>
                <button 
                  onClick={() => setActiveTab("summary")}
                  className={`px-5 py-2 rounded-full text-xs font-bold transition-premium flex items-center gap-2 whitespace-nowrap hover:scale-105 active:scale-[0.98] ${
                    activeTab === "summary" 
                      ? "bg-foreground text-background shadow-md" 
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  <MagicWand weight="light" className="w-4 h-4" /> Tóm tắt AI
                </button>
                {/* <button 
                  onClick={() => setActiveTab("quiz")}
                  className={`px-5 py-2 rounded-full text-xs font-bold transition-premium flex items-center gap-2 whitespace-nowrap hover:scale-105 active:scale-[0.98] ${
                    activeTab === "quiz" 
                      ? "bg-foreground text-background shadow-md" 
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  <Trophy weight="light" className="w-4 h-4" /> Trắc nghiệm BKT
                </button> */}
              </div>
            </div>
          </div>
        </div>

        {/* Content Area wrapped in Double Bezel */}
        <div className="double-bezel-outer min-h-[500px]">
          <div className="double-bezel-inner p-6 md:p-8">
            {loading && (
              <div className="flex flex-col justify-center items-center h-64 gap-4">
                <div className="w-8 h-8 rounded-full bg-foreground/5 flex items-center justify-center">
                  <div className="w-3 h-3 bg-accent-color rounded-full animate-pulse"></div>
                </div>
                <div className="text-muted text-sm font-medium">Đang xử lý...</div>
              </div>
            )}
            
            {!loading && activeTab === "read" && (
              <div className="prose prose-zinc dark:prose-invert max-w-none">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4 mb-6">
                  <h2 className="flex items-center gap-2 text-xl font-bold m-0 text-foreground">
                    <FileText className="text-accent-color w-6 h-6" weight="light" /> Nội dung đầy đủ
                  </h2>
                  
                  {/* View Mode Toggle */}
                  {(fileType === "pdf" || fileType === "docx") && (
                    <div className="flex bg-foreground/5 border border-border p-1 rounded-full">
                      <button
                        onClick={() => setViewMode("preview")}
                        className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-premium-fast hover:scale-105 active:scale-[0.98] ${
                          viewMode === "preview"
                            ? "bg-foreground text-background shadow-sm"
                            : "text-muted hover:text-foreground cursor-pointer"
                        }`}
                      >
                        Bản xem trước gốc
                      </button>
                      <button
                        onClick={() => setViewMode("text")}
                        className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-premium-fast hover:scale-105 active:scale-[0.98] ${
                          viewMode === "text"
                            ? "bg-foreground text-background shadow-sm"
                            : "text-muted hover:text-foreground cursor-pointer"
                        }`}
                      >
                        Văn bản trích xuất
                      </button>
                    </div>
                  )}
                </div>

                {/* Preview Content */}
                {viewMode === "preview" && (fileType === "pdf" || fileType === "docx") ? (
                  <div className="bg-background/50 p-2 rounded-2xl border border-border shadow-inner relative min-h-[600px] overflow-hidden">
                    {blobLoading && (
                      <div className="absolute inset-0 flex flex-col justify-center items-center gap-4 bg-background/80 z-10 rounded-2xl">
                        <div className="w-8 h-8 rounded-full bg-foreground/5 flex items-center justify-center">
                          <div className="w-3 h-3 bg-accent-color rounded-full animate-pulse"></div>
                        </div>
                        <div className="text-muted text-sm font-medium">Đang tải bản xem trước...</div>
                      </div>
                    )}

                    {fileType === "pdf" && blobUrl && (
                      <iframe
                        src={blobUrl}
                        className="w-full h-[750px] rounded-xl border border-border bg-card shadow-lg"
                        title="PDF Preview"
                      />
                    )}

                    {fileType === "docx" && (
                      <div className="w-full bg-card border border-border rounded-xl p-4 overflow-auto flex justify-center h-[750px] docx-preview-container">
                        <div 
                          id="docx-container" 
                          className="w-full max-w-[850px] min-h-full shadow-lg rounded-lg overflow-y-auto"
                        />
                      </div>
                    )}

                    {!blobLoading && !blobUrl && fileType === "pdf" && (
                      <div className="text-center py-20 text-muted font-medium">
                        Không thể tải file PDF gốc.
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap text-foreground/80 leading-relaxed font-sans text-base bg-background/50 p-6 md:p-8 rounded-2xl border border-border shadow-inner max-h-[750px] overflow-y-auto">
                    {content || <span className="text-muted italic">Không có nội dung tài liệu.</span>}
                  </div>
                )}
              </div>
            )}

            {!loading && activeTab === "summary" && (
              <div>
                <div className="flex justify-between items-center border-b border-border pb-4 mb-6">
                  <h2 className="flex items-center gap-2 text-xl font-bold text-foreground m-0"><MagicWand className="text-purple-500 w-6 h-6" weight="light" /> AI Tóm tắt</h2>
                  {!summary && (
                    <button onClick={handleSummarize} className="bg-foreground text-background px-5 py-2.5 rounded-full text-xs font-bold hover:scale-[1.03] active:scale-[0.98] transition-premium cursor-pointer shadow-md">
                      Tạo tóm tắt
                    </button>
                  )}
                </div>
                {summary ? (
                  <div className="prose prose-purple dark:prose-invert max-w-none bg-purple-500/5 p-6 md:p-8 rounded-2xl border border-purple-500/20 shadow-inner">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                      components={markdownComponents}
                    >
                      {preprocessLaTeX(summary)}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-20 text-muted font-medium">Nhấp vào nút Tạo tóm tắt để tạo tóm tắt tài liệu bằng AI.</div>
                )}
              </div>
            )}

            {!loading && activeTab === "quiz" && (
              <div>
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-border pb-4 mb-6 gap-4">
                  <h2 className="flex items-center gap-2 text-xl font-bold text-foreground m-0"><Trophy className="text-orange-500 w-6 h-6" weight="light"/> Luyện tập (BKT)</h2>
                  <div className="flex items-center gap-6 w-full sm:w-auto justify-between sm:justify-end">
                    <div className="flex flex-col items-start sm:items-end">
                      <div className="flex justify-between w-full text-xs mb-1 font-semibold text-muted gap-2">
                        <span>Số câu hỏi:</span>
                        <span className="text-orange-500 font-bold">{quizCount}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] text-muted font-bold">3</span>
                        <input 
                          type="range" 
                          min="3" 
                          max="20" 
                          value={quizCount}
                          onChange={e => setQuizCount(Number(e.target.value))}
                          className="w-24 md:w-32 h-1.5 bg-foreground/10 rounded-lg appearance-none cursor-pointer accent-orange-500"
                        />
                        <span className="text-[10px] text-muted font-bold">20</span>
                      </div>
                    </div>
                    
                    <button onClick={handleGenerateQuiz} className="bg-orange-500 hover:bg-orange-600 text-white px-5 py-2.5 rounded-full text-xs font-bold hover:scale-[1.03] active:scale-[0.98] transition-premium shadow-sm whitespace-nowrap cursor-pointer">
                      Tạo câu hỏi
                    </button>
                  </div>
                </div>

                {quizData.length > 0 ? (
                  <div className="space-y-8">
                    {quizData.map((q, idx) => {
                      const submitted = quizSubmitted[idx];
                      const chosen = quizAnswers[idx];
                      const isCorrect = chosen === q.correct_option;
                      
                      return (
                        <div key={idx} className="double-bezel-outer">
                          <div className="double-bezel-inner p-6 md:p-8">
                            <p className="font-semibold text-lg mb-6 text-foreground leading-relaxed flex items-start">
                              <span className="text-orange-500 mr-2 bg-orange-500/10 px-2 py-0.5 rounded text-sm font-bold mt-0.5">Câu {idx + 1}.</span> 
                              <span>
                                <span className="inline-block align-middle">
                                  <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    rehypePlugins={[rehypeRaw]}
                                    components={quizMarkdownComponents}
                                  >
                                    {preprocessLaTeX(q.question)}
                                  </ReactMarkdown>
                                </span>
                              </span>
                            </p>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              {["A", "B", "C", "D"].map(key => {
                                const isSelected = chosen === key;
                                let btnClass = "border-border bg-background text-foreground hover:border-foreground/20 hover:bg-foreground/5";
                                
                                if (submitted) {
                                  if (key === q.correct_option) btnClass = "border-emerald-500/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold ring-1 ring-emerald-500/30";
                                  else if (isSelected && !isCorrect) btnClass = "border-red-500/50 bg-red-500/10 text-red-600 dark:text-red-400 font-semibold ring-1 ring-red-500/30";
                                  else btnClass = "border-border bg-background opacity-30 text-muted";
                                } else if (isSelected) {
                                  btnClass = "border-orange-500 bg-orange-500/10 text-orange-600 dark:text-orange-400 font-semibold ring-1 ring-orange-500/30";
                                }

                                return (
                                  <button
                                    key={key}
                                    onClick={() => handleAnswerSelect(idx, key)}
                                    disabled={submitted}
                                    className={`text-left px-5 py-4 rounded-2xl border transition-premium-fast cursor-pointer text-sm flex items-center gap-1 ${btnClass}`}
                                  >
                                    <span className="font-bold opacity-75">{key}.</span>
                                    <span className="inline-block align-middle flex-1">
                                      <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        rehypePlugins={[rehypeRaw]}
                                        components={quizMarkdownComponents}
                                      >
                                        {preprocessLaTeX(q.options[key])}
                                      </ReactMarkdown>
                                    </span>
                                  </button>
                                );
                              })}
                            </div>
                            
                            {/* Submit Row */}
                            <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
                              {!submitted ? (
                                <button 
                                  onClick={() => handleQuizSubmit(idx)}
                                  disabled={!chosen}
                                  className="bg-foreground text-background px-6 py-2.5 rounded-full text-xs font-bold disabled:opacity-50 hover:scale-[1.03] active:scale-[0.98] transition-premium cursor-pointer shadow-md"
                                >
                                  Nộp câu trả lời
                                </button>
                              ) : (
                                <div className={`flex items-center gap-2 font-bold text-sm ${isCorrect ? "text-emerald-500" : "text-red-500"}`}>
                                  {isCorrect ? (
                                    <><CheckCircle weight="fill" className="w-5 h-5 text-emerald-500"/> Trả lời chính xác!</>
                                  ) : (
                                    <><XCircle weight="fill" className="w-5 h-5 text-red-500"/> Chưa chính xác. Đáp án đúng là {q.correct_option}.</>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="text-center py-20 text-muted font-medium">Chọn số lượng câu hỏi và nhấp vào Tạo câu hỏi để bắt đầu bài ôn tập.</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
