"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChatCircle, FileText, ChartBar, House, SignOut, Clock, Sun, Moon, Brain, Certificate, Graph } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

export default function Navigation() {
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    setMounted(true);
    const savedTheme = localStorage.getItem("theme") as "dark" | "light" | null;
    if (savedTheme) {
      setTheme(savedTheme);
    } else {
      const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      setTheme(systemDark ? "dark" : "light");
    }
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("theme", nextTheme);
    
    const root = document.documentElement;
    if (nextTheme === "dark") {
      root.classList.remove("light");
      root.classList.add("dark");
      root.setAttribute("data-theme", "dark");
    } else {
      root.classList.remove("dark");
      root.classList.add("light");
      root.setAttribute("data-theme", "light");
    }
  };

  const navItems = [
    { name: "Trang chủ", href: "/", icon: House },
    { name: "Tài liệu", href: "/documents", icon: FileText },
    { name: "Hội thoại", href: "/chat", icon: ChatCircle },
    { name: "Lịch sử", href: "/history", icon: Clock },
    { name: "Đánh giá", href: "/evaluation", icon: ChartBar },
    { name: "Quiz", href: "/quiz", icon: Brain },
    { name: "Báo cáo", href: "/report", icon: Certificate },
    // { name: "Bản đồ", href: "/knowledge-graph", icon: Graph },
  ];

  if (!mounted || pathname === "/login") return null;

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user");
    router.push("/login");
  };

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 max-w-[95vw]">
      <nav className="flex flex-row flex-nowrap items-center gap-1 p-1.5 sm:gap-1.5 sm:p-2 rounded-full bg-card/75 backdrop-blur-xl border border-border shadow-2xl transition-premium overflow-x-auto no-scrollbar">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-full transition-premium-fast hover:scale-105 active:scale-[0.98]
                ${
                  isActive
                    ? "bg-foreground text-background shadow-md font-semibold"
                    : "text-muted hover:text-foreground hover:bg-foreground/5"
                }
              `}
            >
              <Icon weight={isActive ? "fill" : "light"} className="w-5 h-5" />
              <span className="text-sm font-medium hidden lg:block whitespace-nowrap">{item.name}</span>
            </Link>
          );
        })}
        
        <div className="w-[1px] h-6 bg-border mx-1" />

        <button
          onClick={toggleTheme}
          className="flex items-center justify-center p-2.5 rounded-full transition-premium-fast text-muted hover:text-foreground hover:bg-foreground/5 hover:scale-105 active:scale-[0.98]"
          title="Chuyển đổi giao diện"
        >
          {theme === "dark" ? (
            <Sun weight="light" className="w-5 h-5 text-amber-400" />
          ) : (
            <Moon weight="light" className="w-5 h-5 text-indigo-500" />
          )}
        </button>

        <button
          onClick={handleLogout}
          className="flex items-center gap-2 px-4 py-2.5 rounded-full transition-premium-fast text-red-500 hover:text-red-400 hover:bg-red-500/10 hover:scale-105 active:scale-[0.98]"
        >
          <SignOut weight="light" className="w-5 h-5" />
          <span className="text-sm font-medium hidden lg:block whitespace-nowrap">Đăng xuất</span>
        </button>
      </nav>
    </div>
  );
}
