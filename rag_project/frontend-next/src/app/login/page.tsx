"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setLoading(true);

    if (isLogin) {
      const { data, error } = await api.post("/auth/login", { username, password });
      if (data && data.access_token) {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("user", JSON.stringify(data.user || {}));
        router.push("/documents");
      } else {
        setErrorMsg(error || "Đăng nhập thất bại");
      }
    } else {
      const { data, error } = await api.post("/auth/register", { username, password, full_name: fullName });
      if (data && data.access_token) {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("user", JSON.stringify(data.user || {}));
        router.push("/documents");
      } else {
        setErrorMsg(error || "Đăng ký thất bại");
      }
    }
    setLoading(false);
  };

  return (
    <main className="min-h-[100dvh] bg-background text-foreground flex items-center justify-center relative overflow-hidden transition-colors duration-300">
      {/* Background radial mesh glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] mesh-glow-violet opacity-60 dark:opacity-100"></div>
        <div className="absolute bottom-[-10%] right-[-10%] mesh-glow-emerald opacity-60 dark:opacity-100"></div>
      </div>

      <div className="relative z-10 w-full max-w-md double-bezel-outer">
        <div className="double-bezel-inner p-8 backdrop-blur-xl">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold tracking-tight text-foreground mb-2">
              {isLogin ? "Chào mừng trở lại" : "Tạo tài khoản"}
            </h1>
            <p className="text-muted text-sm leading-relaxed">
              {isLogin ? "Đăng nhập để truy cập cơ sở tri thức của bạn." : "Tham gia cùng chúng tôi để bắt đầu trò chuyện với tài liệu."}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {!isLogin && (
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-muted mb-1.5">Họ và tên</label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-background border border-border rounded-2xl px-4 py-3.5 text-foreground placeholder:text-muted focus:outline-none focus:border-accent-color transition-premium-fast text-sm"
                  placeholder="Nguyễn Văn A"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-muted mb-1.5">Tên đăng nhập</label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-background border border-border rounded-2xl px-4 py-3.5 text-foreground placeholder:text-muted focus:outline-none focus:border-accent-color transition-premium-fast text-sm"
                placeholder="username"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-muted mb-1.5">Mật khẩu</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-background border border-border rounded-2xl px-4 py-3.5 text-foreground placeholder:text-muted focus:outline-none focus:border-accent-color transition-premium-fast text-sm"
                placeholder="••••••••"
              />
            </div>

            {errorMsg && (
              <div className="text-red-500 text-sm text-center font-medium bg-red-500/10 py-2.5 rounded-2xl border border-red-500/20">
                {errorMsg === "Invalid credentials" ? "Tên đăng nhập hoặc mật khẩu không chính xác" : errorMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-4 bg-foreground text-background py-3.5 rounded-full font-semibold hover:scale-[1.02] active:scale-[0.98] transition-premium-fast disabled:opacity-50 disabled:hover:scale-100 cursor-pointer shadow-lg text-sm"
            >
              {loading ? "Đang xử lý..." : isLogin ? "Đăng Nhập" : "Đăng Ký"}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-muted">
            {isLogin ? "Chưa có tài khoản? " : "Đã có tài khoản? "}
            <button
              type="button"
              onClick={() => {
                setIsLogin(!isLogin);
                setErrorMsg("");
              }}
              className="text-foreground font-semibold hover:underline focus:outline-none cursor-pointer"
            >
              {isLogin ? "Đăng ký ngay" : "Đăng nhập"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
