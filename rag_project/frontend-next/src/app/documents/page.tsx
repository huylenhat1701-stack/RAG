"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { UploadSimple, FileText, Trash, TrendUp } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";

interface Document {
  id: string;
  file_name: string;
  file_size: number;
  status: string;
  chunk_count: number;
  page_count: number;
  uploaded_at: string;
}

export default function DocumentsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const fetchDocuments = async () => {
    setLoading(true);
    const { data } = await api.get("/documents");
    if (data && data.documents) {
      setDocuments(data.documents);
    }
    setLoading(false);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    const { data } = await api.post("/documents/upload", formData, true);
    if (data) {
      fetchDocuments();
    }
    setUploading(false);
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm("Bạn có chắc chắn muốn xóa tài liệu này không?")) {
      await api.delete(`/documents/${id}`);
      fetchDocuments();
    }
  };

  const handleSummarize = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await api.post(`/documents/${id}/summarize`);
    router.push(`/documents/${id}?tab=summary`);
  };

  const formatDateTime = (dateStr: string) => {
    try {
      const dt = new Date(dateStr.endsWith("Z") ? dateStr : dateStr + "Z");
      return dt.toLocaleString("vi-VN");
    } catch {
      return dateStr;
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  return (
    <main className="min-h-screen bg-background text-foreground p-8 md:p-16 pb-36 relative overflow-hidden transition-colors duration-300">
      {/* Background ambient light */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] mesh-glow-violet opacity-40 dark:opacity-70"></div>
        <div className="absolute bottom-[-10%] right-[-10%] mesh-glow-emerald opacity-40 dark:opacity-70"></div>
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-16 gap-6">
          <div>
            <span className="rounded-full px-3 py-1 text-[10px] uppercase tracking-[0.2em] font-bold text-muted bg-foreground/5 border border-border mb-4 inline-block">
              Hệ thống lưu trữ
            </span>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4 text-foreground">
              Cơ sở tri thức
            </h1>
            <p className="text-muted text-lg max-w-xl">
              Quản lý tài liệu đã tải lên, trích xuất thông tin chuyên sâu và chuẩn bị cơ sở dữ liệu cho RAG.
            </p>
          </div>
          
          <label className="flex items-center gap-2 bg-foreground text-background px-6 py-3.5 rounded-full font-semibold cursor-pointer hover:scale-[1.03] active:scale-[0.98] transition-premium shadow-xl text-sm">
            {uploading ? (
              <div className="w-5 h-5 border-2 border-background border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <UploadSimple weight="bold" className="w-5 h-5" />
            )}
            <span>{uploading ? "Đang tải lên..." : "Tải tài liệu mới"}</span>
            <input 
              type="file" 
              className="hidden" 
              onChange={handleUpload}
              accept=".pdf,.txt,.docx,.md"
              disabled={uploading}
            />
          </label>
        </div>

        {/* Bento Grid layout */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 auto-rows-[270px]">
          {loading ? (
            <div className="col-span-full flex justify-center items-center py-20">
              <div className="w-8 h-8 rounded-full bg-foreground/5 flex items-center justify-center">
                <div className="w-3 h-3 bg-accent-color rounded-full animate-pulse"></div>
              </div>
            </div>
          ) : documents.length === 0 ? (
            <div className="col-span-full text-center py-20 bg-card/50 rounded-[2rem] border border-border border-dashed flex flex-col items-center justify-center">
              <FileText className="w-12 h-12 text-muted mb-4" weight="light" />
              <p className="text-foreground text-xl font-bold mb-2">Chưa có tài liệu nào</p>
              <p className="text-muted text-sm">Tải lên tệp đầu tiên của bạn để bắt đầu trò chuyện</p>
            </div>
          ) : (
            documents.map((doc, index) => {
              const isLarge = index === 0 || index % 5 === 0;
              const spanClass = isLarge ? "md:col-span-2 xl:col-span-2" : "col-span-1";

              return (
                <div 
                  key={doc.id} 
                  onClick={() => router.push(`/documents/${doc.id}`)}
                  className={`group cursor-pointer relative double-bezel-outer transition-premium hover:scale-[1.01] ${spanClass}`}
                >
                  <div className="double-bezel-inner p-6 flex flex-col justify-between h-full relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-br from-foreground/5 to-transparent opacity-0 group-hover:opacity-100 transition-premium pointer-events-none"></div>
                    
                    <div className="relative z-10 flex justify-between items-start">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-foreground/5 flex items-center justify-center group-hover:bg-foreground/10 transition-premium-fast text-muted group-hover:text-foreground">
                          <FileText className="w-5 h-5" weight="light" />
                        </div>
                        <div>
                          <p className="text-[10px] text-muted font-bold tracking-wider uppercase mb-1">
                            {(doc.file_size / 1024 / 1024).toFixed(2)} MB • {doc.chunk_count} đoạn • {doc.page_count} trang • {formatDateTime(doc.uploaded_at)}
                          </p>
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                            doc.status === 'INDEXED' 
                              ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' 
                              : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                          }`}>
                            {doc.status === 'INDEXED' ? 'Đã lập chỉ mục' : doc.status}
                          </span>
                        </div>
                      </div>
                      
                      <button onClick={(e) => handleDelete(e, doc.id)} className="p-2 text-muted hover:text-red-500 hover:bg-red-500/10 rounded-full transition-premium-fast cursor-pointer">
                        <Trash className="w-5 h-5" weight="light" />
                      </button>
                    </div>

                    <div className="relative z-10 mt-6">
                      <h3 className={`font-bold text-foreground tracking-tight leading-tight line-clamp-2 transition-premium-fast group-hover:text-accent-color ${isLarge ? 'text-2xl md:text-3xl' : 'text-lg md:text-xl'}`}>
                        {doc.file_name}
                      </h3>
                    </div>

                    <div className="relative z-10 flex gap-2 mt-auto pt-4">
                      <button onClick={(e) => handleSummarize(e, doc.id)} className="w-full py-2.5 bg-foreground/5 hover:bg-foreground hover:text-background text-foreground font-semibold rounded-xl text-xs transition-premium flex items-center justify-center gap-2 cursor-pointer border border-border">
                        <TrendUp className="w-4 h-4" weight="light" /> Tóm tắt bằng AI
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
        
      </div>
    </main>
  );
}
