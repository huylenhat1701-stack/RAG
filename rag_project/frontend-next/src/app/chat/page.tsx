"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/dist/ScrollTrigger";
import { PaperPlaneRight, Trash, Plus } from "@phosphor-icons/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { preprocessLaTeX, markdownComponents } from "@/lib/latex";
if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

interface ChatMessage {
  id: string;
  role: string;
  content: string;
  timestamp: string;
}

export default function ChatPage() {
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [asking, setAsking] = useState(false);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(15);
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const leftPinRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchHistory = async () => {
    setLoading(true);
    const { data } = await api.get("/chat/history", { limit: 50 });
    let mappedHistory: ChatMessage[] = [];
    if (data && data.histories) {
      data.histories.reverse().forEach((h: any) => {
        mappedHistory.push({ id: `q-${h.id}`, role: "user", content: h.question, timestamp: h.created_at });
        mappedHistory.push({ id: `a-${h.id}`, role: "assistant", content: h.answer, timestamp: h.created_at });
      });
    }
    setHistory(mappedHistory);
    setLoading(false);
  };

  const fetchDocuments = async () => {
    const { data } = await api.get("/documents");
    if (data && data.documents) {
      setDocuments(data.documents);
    }
  };

  useEffect(() => {
    fetchHistory();
    fetchDocuments();
  }, []);

  // GSAP ScrollTrigger setup
  useEffect(() => {
    if (typeof window === "undefined" || !leftPinRef.current || !containerRef.current) return;
    
    // Refresh ScrollTrigger to ensure correct heights
    ScrollTrigger.refresh();

    const ctx = gsap.context(() => {
      ScrollTrigger.create({
        trigger: containerRef.current,
        start: "top top",
        end: "bottom bottom",
        pin: leftPinRef.current,
        pinSpacing: false,
      });
      
      // Image scale & fade scroll for message cards
      gsap.utils.toArray<HTMLElement>(".msg-card").forEach(card => {
        gsap.fromTo(card, 
          { opacity: 0, y: 50, scale: 0.95 },
          { 
            opacity: 1, 
            y: 0, 
            scale: 1,
            duration: 0.6,
            ease: "power2.out",
            scrollTrigger: {
              trigger: card,
              start: "top 90%",
              toggleActions: "play none none reverse"
            }
          }
        );
      });
    }, containerRef);

    return () => ctx.revert();
  }, [history.length]); // Re-run GSAP when history changes so it captures new cards

  useEffect(() => {
    // Scroll to bottom softly whenever history changes
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
    // Give DOM time to update layout before refreshing ScrollTrigger
    setTimeout(() => {
      ScrollTrigger.refresh();
    }, 100);
  }, [history]);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    const currentInput = input.trim();
    if (!currentInput || asking) return;
    
    if (currentInput.length < 3) {
      alert("Câu hỏi phải có ít nhất 3 ký tự (yêu cầu từ server).");
      return;
    }

    const userMessage: ChatMessage = { id: Date.now().toString(), role: "user", content: currentInput, timestamp: new Date().toISOString() };
    setHistory(prev => [...prev, userMessage]);
    setInput("");
    setAsking(true);

    const askPayload = {
      question: currentInput,
      top_k: topK,
      history: history.slice(-8).map(m => ({ role: m.role, content: m.content })),
      doc_ids: selectedDocs.length > 0 ? selectedDocs : null,
    };

    const { data } = await api.post("/chat/ask", askPayload);
    
    if (data && data.answer) {
      const assistantMessage: ChatMessage = { 
        id: (Date.now() + 1).toString(), 
        role: "assistant", 
        content: data.answer, 
        timestamp: new Date().toISOString() 
      };
      setHistory(prev => [...prev, assistantMessage]);
    }
    
    setAsking(false);
  };

  const handleClear = async () => {
    await api.delete("/chat/history");
    setHistory([]);
  };

  return (
    <main className="min-h-screen bg-background text-foreground relative transition-colors duration-300">
      {/* Background ambient light */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] mesh-glow-violet opacity-30 dark:opacity-60"></div>
        <div className="absolute bottom-[-10%] right-[-10%] mesh-glow-emerald opacity-30 dark:opacity-60"></div>
      </div>

      <div ref={containerRef} className="max-w-[1400px] mx-auto w-full flex flex-col lg:flex-row relative z-10">
        
        {/* Left Side: Pinned Content */}
        <div className="lg:w-1/3 p-8 lg:p-16 h-[50vh] lg:h-screen flex flex-col justify-between" ref={leftPinRef}>
          <div>
            <div className="inline-block p-3 bg-card rounded-2xl border border-border mb-8 shadow-sm">
              <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <div className="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
              </div>
            </div>
            
            <h1 className="text-[clamp(2.5rem,4vw,3.5rem)] font-bold tracking-tight leading-[1.1] mb-6 text-foreground">
              Đối thoại<br/>Trí tuệ.
            </h1>
            <p className="text-muted text-base max-w-sm mb-8 leading-relaxed">
              Đặt câu hỏi liên quan đến tài liệu trong cơ sở tri thức của bạn. AI sẽ phân tích và phản hồi chính xác dựa trên nguồn dẫn.
            </p>
            
            <div className="flex gap-3 mb-10">
              <button 
                onClick={fetchHistory}
                className="flex items-center gap-2 bg-foreground text-background px-5 py-2.5 rounded-full font-bold text-sm hover:scale-105 active:scale-[0.98] transition-premium cursor-pointer shadow-md"
              >
                <Plus weight="bold" /> Hội thoại mới
              </button>
              <button 
                onClick={handleClear} 
                className="flex items-center gap-2 bg-card text-foreground px-5 py-2.5 rounded-full font-bold text-sm hover:bg-red-500/10 hover:text-red-500 border border-border transition-premium cursor-pointer hover:scale-105 active:scale-[0.98]"
              >
                <Trash weight="bold" /> Xóa lịch sử
              </button>
            </div>

            {/* Slider with Double Bezel */}
            <div className="double-bezel-outer max-w-sm">
              <div className="double-bezel-inner p-5">
                <div className="flex justify-between items-center mb-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-muted">Phạm vi tìm kiếm (Top K)</label>
                  <span className="text-accent-color font-bold bg-accent-color/10 px-2 py-0.5 rounded text-xs border border-accent-color/20">{topK}</span>
                </div>
                <p className="text-[11px] text-muted mb-4 leading-normal">Mức độ quét chi tiết tài liệu (RAG). Số càng lớn, AI càng đọc nhiều trang nhưng phản hồi có thể chậm hơn.</p>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-muted font-bold">3</span>
                  <input 
                    type="range" 
                    min="3" 
                    max="50" 
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    className="w-full h-1.5 bg-foreground/10 rounded-lg appearance-none cursor-pointer accent-accent-color"
                  />
                  <span className="text-[10px] text-muted font-bold">50</span>
                </div>
              </div>
            </div>

            {/* Filter by Documents with Double Bezel */}
            <div className="double-bezel-outer max-w-sm mt-6">
              <div className="double-bezel-inner p-5 flex flex-col gap-3">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-bold uppercase tracking-wider text-muted">Lọc nguồn tài liệu</label>
                  {selectedDocs.length > 0 && (
                    <button 
                      onClick={() => setSelectedDocs([])} 
                      className="text-[10px] font-bold text-accent-color hover:underline cursor-pointer"
                    >
                      Bỏ lọc ({selectedDocs.length})
                    </button>
                  )}
                </div>
                <p className="text-[11px] text-muted leading-normal">Chọn các tài liệu cụ thể bạn muốn AI đọc để trả lời. Nếu không chọn, AI sẽ tìm trên toàn bộ cơ sở tri thức.</p>
                
                {documents.length === 0 ? (
                  <p className="text-xs text-muted italic">Không tìm thấy tài liệu nào trong thư viện.</p>
                ) : (
                  <div className="flex flex-col gap-2 max-h-[160px] overflow-y-auto pr-1">
                    {documents.map((doc) => {
                      const isChecked = selectedDocs.includes(Number(doc.id));
                      return (
                        <button
                          key={doc.id}
                          onClick={() => {
                            const docIdNum = Number(doc.id);
                            if (isChecked) {
                              setSelectedDocs(prev => prev.filter(id => id !== docIdNum));
                            } else {
                              setSelectedDocs(prev => [...prev, docIdNum]);
                            }
                          }}
                          className={`flex items-center gap-3 text-left w-full p-2.5 rounded-xl border text-xs font-semibold transition-premium-fast hover:scale-[1.01] cursor-pointer
                            ${isChecked 
                              ? 'bg-accent-color/10 border-accent-color/30 text-foreground' 
                              : 'bg-foreground/5 border-border hover:border-foreground/10 text-muted hover:text-foreground'
                            }
                          `}
                        >
                          <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center transition-premium-fast
                            ${isChecked 
                              ? 'bg-accent-color border-accent-color' 
                              : 'border-muted'
                            }
                          `}>
                            {isChecked && <div className="w-1.5 h-1.5 bg-background rounded-full"></div>}
                          </div>
                          <span className="truncate flex-1">{doc.file_name}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Scrolling Chat History */}
        <div className="lg:w-2/3 p-4 lg:p-16 pb-64 lg:pb-64 min-h-screen flex flex-col justify-end">
          <div className="flex flex-col gap-6 w-full max-w-3xl mx-auto">
            {loading && history.length === 0 ? (
              <div className="text-muted text-center py-20 flex flex-col items-center gap-3">
                <div className="w-6 h-6 border-2 border-foreground border-t-transparent rounded-full animate-spin"></div>
                <span className="text-sm font-semibold">Đang thiết lập kết nối dữ liệu...</span>
              </div>
            ) : history.length === 0 ? (
              <div className="text-muted text-center py-20 text-lg font-bold tracking-tight">Chưa có tin nhắn nào. Hãy bắt đầu cuộc trò chuyện.</div>
            ) : (
              history.map((msg, idx) => (
                <div key={idx} className={`msg-card flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'user' ? (
                    <div className="max-w-[85%] bg-foreground text-background rounded-3xl px-6 py-4.5 rounded-tr-sm shadow-md">
                      <div className="text-sm font-semibold leading-relaxed whitespace-pre-wrap">{msg.content}</div>
                    </div>
                  ) : (
                    <div className="max-w-[85%] double-bezel-outer w-full min-w-0">
                      <div className="double-bezel-inner p-6 border border-border w-full min-w-0 overflow-hidden">
                        <div className="flex items-center gap-2 mb-2 opacity-50">
                          <span className="text-[10px] uppercase tracking-widest font-bold text-accent-color">AI Assistant</span>
                        </div>
                        <div className="prose prose-zinc dark:prose-invert max-w-none text-base leading-relaxed w-full max-w-full overflow-x-auto">
                          <ReactMarkdown 
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw]}
                            components={markdownComponents}
                          >
                            {preprocessLaTeX(msg.content)}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
            
            {asking && (
              <div className="msg-card flex w-full justify-start">
                <div className="max-w-[85%] double-bezel-outer w-full">
                  <div className="double-bezel-inner p-6 border border-border w-full">
                    <div className="flex gap-1 items-center h-6">
                      <div className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce" style={{animationDelay: '0ms'}}></div>
                      <div className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce" style={{animationDelay: '150ms'}}></div>
                      <div className="w-1.5 h-1.5 rounded-full bg-muted animate-bounce" style={{animationDelay: '300ms'}}></div>
                    </div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} className="h-4" />
          </div>
        </div>
        
      </div>

      {/* Pinned Input Area at bottom */}
      <div className="fixed bottom-24 left-0 lg:left-[33.33%] w-full lg:w-[66.67%] p-4 lg:p-8 bg-gradient-to-t from-background via-background/90 to-transparent pointer-events-none z-40 transition-all duration-300">
        <div className="max-w-3xl mx-auto pointer-events-auto">
          <form onSubmit={handleAsk} className="relative flex items-center">
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Hỏi bất kỳ điều gì về tài liệu của bạn..."
              className="w-full bg-card border border-border rounded-full py-4.5 pl-6 pr-16 text-base text-foreground placeholder:text-muted focus:outline-none focus:border-foreground transition-colors shadow-xl"
              disabled={asking}
            />
            <button 
              type="submit"
              disabled={asking || !input.trim()}
              className="absolute right-2.5 w-11 h-11 bg-foreground text-background rounded-full flex items-center justify-center hover:scale-105 active:scale-[0.98] transition-premium disabled:opacity-50 disabled:hover:scale-100 cursor-pointer shadow-md"
            >
              <PaperPlaneRight weight="fill" className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
