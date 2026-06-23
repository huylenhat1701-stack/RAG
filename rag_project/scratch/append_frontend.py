import sys
sys.stdout.reconfigure(encoding='utf-8')
path = r'c:\project\new\RAG\rag_project\frontend\app.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Restore tabs definition + add new tab
old_tabs_section = '# ============================================================\n\n# TAB 1'
new_tabs_section = '''# ============================================================
# Tabs
# ============================================================
tab_docs, tab_read, tab_summary, tab_exercise, tab_chat, tab_history, tab_evaluate = st.tabs([
    "📁 Tai Lieu",
    "📖 Doc",
    "📝 Tom Tat",
    "🏆 Bai Tap",
    "💬 Hoi & Dap",
    "🕐 Lich Su",
    "📊 Danh Gia AI",
])


# TAB 1'''

content = content.replace(old_tabs_section, new_tabs_section, 1)

# 2. Append the new evaluate tab at the end of file
tab_evaluate_code = '''

# ============================================================
# TAB 7: Danh Gia Do Chinh Xac AI
# ============================================================
with tab_evaluate:
    st.markdown(\'<p class="section-heading">📊 Danh Gia Do Chinh Xac He Thong AI</p>\', unsafe_allow_html=True)
    st.markdown(\'<p class="section-caption">Do luong chat luong 3 tang: RAG (Hoi Dap), BKT (Theo doi kien thuc), Quiz (Tao cau hoi).</p>\', unsafe_allow_html=True)

    col_refresh, _ = st.columns([1, 4])
    with col_refresh:
        do_refresh = st.button("Lam Moi Du Lieu", use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ─── TANG 2: BKT Stats (tu DB, nhanh nhat) ─────────────────
    st.markdown("### Tang 2: Thuat Toan BKT (Bayesian Knowledge Tracing)")

    bkt_data, bkt_err = api_get("/evaluate/bkt")
    if bkt_err:
        st.error(f"Khong the lay du lieu BKT: {bkt_err}")
    elif bkt_data:
        total_ans = bkt_data.get("total_answers", 0)
        if total_ans == 0:
            st.info("Chua co du lieu. Hay de hoc sinh lam bai thi de thu thap lich su.")
        else:
            acc   = bkt_data.get("accuracy", 0)
            auc   = bkt_data.get("auc_roc", 0)
            ll    = bkt_data.get("log_loss", 0)
            corr  = bkt_data.get("correct_total", 0)
            wrong = bkt_data.get("wrong_total", 0)

            # Xep hang danh gia
            if acc >= 0.75:
                acc_grade, acc_color = "Tot", "#22c55e"
            elif acc >= 0.60:
                acc_grade, acc_color = "Kha", "#f59e0b"
            else:
                acc_grade, acc_color = "Can Cai Thien", "#ef4444"

            if auc >= 0.75:
                auc_grade, auc_color = "Tot", "#22c55e"
            elif auc >= 0.60:
                auc_grade, auc_color = "Kha", "#f59e0b"
            else:
                auc_grade, auc_color = "Yeu", "#ef4444"

            # Metric cards
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:1rem 1.2rem;text-align:center;border-top:4px solid {acc_color};">
                    <div style="font-size:1.8rem;font-weight:800;color:{acc_color};">{acc:.1%}</div>
                    <div style="font-size:0.8rem;color:#6b7280;margin-top:0.2rem;">Accuracy</div>
                    <div style="font-size:0.7rem;font-weight:600;color:{acc_color};">{acc_grade}</div>
                </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:1rem 1.2rem;text-align:center;border-top:4px solid {auc_color};">
                    <div style="font-size:1.8rem;font-weight:800;color:{auc_color};">{auc:.3f}</div>
                    <div style="font-size:0.8rem;color:#6b7280;margin-top:0.2rem;">AUC-ROC</div>
                    <div style="font-size:0.7rem;font-weight:600;color:{auc_color};">{auc_grade}</div>
                </div>
                """, unsafe_allow_html=True)
            with m3:
                ll_color = "#22c55e" if ll <= 0.5 else ("#f59e0b" if ll <= 0.8 else "#ef4444")
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:1rem 1.2rem;text-align:center;border-top:4px solid {ll_color};">
                    <div style="font-size:1.8rem;font-weight:800;color:{ll_color};">{ll:.3f}</div>
                    <div style="font-size:0.8rem;color:#6b7280;margin-top:0.2rem;">Log-Loss</div>
                    <div style="font-size:0.7rem;font-weight:600;color:{ll_color};">{"Tot" if ll <= 0.5 else ("Kha" if ll <= 0.8 else "Cao")}</div>
                </div>
                """, unsafe_allow_html=True)
            with m4:
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:1rem 1.2rem;text-align:center;border-top:4px solid #1e40af;">
                    <div style="font-size:1.8rem;font-weight:800;color:#1e40af;">{total_ans}</div>
                    <div style="font-size:0.8rem;color:#6b7280;margin-top:0.2rem;">Tong lan tra loi</div>
                    <div style="font-size:0.7rem;color:#6b7280;">{corr} dung / {wrong} sai</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Phan bo diem BKT
            dist = bkt_data.get("distribution", {})
            low_c  = dist.get("low_count", 0)
            mid_c  = dist.get("mid_count", 0)
            high_c = dist.get("high_count", 0)
            total_chunks = bkt_data.get("total_chunks_tracked", 0) or 1

            st.markdown("**Phan bo diem hieu bai BKT:**")
            col_l, col_m, col_h = st.columns(3)
            with col_l:
                pct_l = int(low_c / total_chunks * 100)
                st.markdown(f"""
                <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:10px;padding:0.8rem;text-align:center;">
                    <div style="font-size:1.4rem;font-weight:700;color:#dc2626;">{low_c}</div>
                    <div style="font-size:0.75rem;color:#991b1b;">Yeu (&lt;40%) — {pct_l}%</div>
                </div>
                """, unsafe_allow_html=True)
            with col_m:
                pct_m = int(mid_c / total_chunks * 100)
                st.markdown(f"""
                <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:10px;padding:0.8rem;text-align:center;">
                    <div style="font-size:1.4rem;font-weight:700;color:#d97706;">{mid_c}</div>
                    <div style="font-size:0.75rem;color:#92400e;">Trung binh (40-70%) — {pct_m}%</div>
                </div>
                """, unsafe_allow_html=True)
            with col_h:
                pct_h = int(high_c / total_chunks * 100)
                st.markdown(f"""
                <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:0.8rem;text-align:center;">
                    <div style="font-size:1.4rem;font-weight:700;color:#16a34a;">{high_c}</div>
                    <div style="font-size:0.75rem;color:#166534;">Tot (&gt;=70%) — {pct_h}%</div>
                </div>
                """, unsafe_allow_html=True)

            # Accuracy theo nhom
            grp = bkt_data.get("group_accuracy", {})
            st.markdown("<br>**Accuracy theo nhom BKT:**", unsafe_allow_html=True)
            g1, g2, g3 = st.columns(3)
            for col, key, label in [(g1, "low", "Nhom Yeu"), (g2, "mid", "Nhom Trung Binh"), (g3, "high", "Nhom Tot")]:
                val = grp.get(key, 0)
                with col:
                    bar_w = int(val * 100)
                    bar_c = "#22c55e" if val >= 0.7 else ("#f59e0b" if val >= 0.5 else "#ef4444")
                    st.markdown(f"""
                    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:0.8rem;">
                        <div style="font-size:0.8rem;color:#374151;margin-bottom:0.4rem;">{label}</div>
                        <div style="font-size:1.3rem;font-weight:700;color:{bar_c};">{val:.1%}</div>
                        <div style="height:6px;background:#e5e7eb;border-radius:9999px;margin-top:0.4rem;">
                            <div style="height:100%;width:{bar_w}%;background:{bar_c};border-radius:9999px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            # Khuyen nghi
            st.markdown("<br>", unsafe_allow_html=True)
            recs = []
            if acc < 0.60:
                recs.append("Accuracy thap: Dieu chinh nguong BKT (hien tai 60%) hoac tang p_transit.")
            if auc < 0.60:
                recs.append("AUC-ROC thap: BKT gan nhu du doan ngau nhien. Giam p_guess hoac tang p_transit.")
            if ll > 0.8:
                recs.append("Log-Loss cao: Xac suat BKT lech xa thuc te. Nen review cong thuc cap nhat.")
            if recs:
                st.markdown(f"""
                <div style="background:#fef3c7;border:1px solid #fcd34d;border-left:4px solid #f59e0b;border-radius:0 10px 10px 0;padding:0.8rem 1rem;">
                    <strong>Khuyen nghi cai thien:</strong><br>
                    {"<br>".join(f"• {r}" for r in recs)}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background:#f0fdf4;border:1px solid #86efac;border-left:4px solid #22c55e;border-radius:0 10px 10px 0;padding:0.8rem 1rem;">
                    <strong>Ket qua tot!</strong> He thong BKT dang hoat dong hieu qua.
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # ─── TANG 1: RAG Stats (tu ChatHistory) ─────────────────
    st.markdown("### Tang 1: Chat Luong RAG (Hoi Dap)")

    rag_data, rag_err = api_get("/evaluate/rag-stats")
    if rag_err:
        st.error(f"Khong the lay du lieu RAG: {rag_err}")
    elif rag_data:
        total_q = rag_data.get("total_questions", 0)
        if total_q == 0:
            st.info("Chua co cau hoi nao trong lich su. Hay su dung tab Hoi & Dap truoc.")
        else:
            r1, r2, r3 = st.columns(3)
            with r1:
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:1rem;text-align:center;border-top:4px solid #1e40af;">
                    <div style="font-size:1.8rem;font-weight:800;color:#1e40af;">{total_q}</div>
                    <div style="font-size:0.8rem;color:#6b7280;">Tong cau hoi da hoi</div>
                </div>
                """, unsafe_allow_html=True)
            with r2:
                avg_a = rag_data.get("avg_answer_length", 0)
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:1rem;text-align:center;border-top:4px solid #7c3aed;">
                    <div style="font-size:1.8rem;font-weight:800;color:#7c3aed;">{avg_a:,}</div>
                    <div style="font-size:0.8rem;color:#6b7280;">TB ky tu / cau tra loi</div>
                </div>
                """, unsafe_allow_html=True)
            with r3:
                ms_pct = rag_data.get("multi_source_pct", 0)
                st.markdown(f"""
                <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:1rem;text-align:center;border-top:4px solid #0891b2;">
                    <div style="font-size:1.8rem;font-weight:800;color:#0891b2;">{ms_pct}%</div>
                    <div style="font-size:0.8rem;color:#6b7280;">Da nguon trich dan</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.info("De danh gia chinh xac Faithfulness & Relevancy bang LLM-as-a-Judge, chay: "
                    "`python -m backend.scripts.evaluate_rag` trong thu muc rag_project.")

    st.divider()

    # ─── TANG 3: Quiz Info ───────────────────────────────────
    st.markdown("### Tang 3: Chat Luong Quiz (Tao Cau Hoi)")
    st.markdown("""
    <div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px;padding:1rem 1.2rem;">
        <p style="margin:0;color:#374151;font-size:0.88rem;">
            <strong>Chat luong quiz</strong> duoc danh gia qua 2 tieu chi:<br>
            • <strong>Groundedness</strong>: Cau hoi co xuat phat tu tai lieu goc khong?<br>
            • <strong>Plausibility</strong>: Cac lua chon sai co hop ly, kho doan khong?<br><br>
            De chay danh gia day du, thuc hien lenh:<br>
            <code>cd rag_project && python -m backend.scripts.run_all_evaluations</code>
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Ket qua CSV neu da chay
    import os as _os
    csv_files = {
        "RAG Q&A": "evaluation_rag.csv",
        "BKT Chi Tiet": "evaluation_bkt.csv",
        "Quiz": "evaluation_quiz.csv",
    }
    for label, fname in csv_files.items():
        fpath = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), fname)
        if _os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8-sig") as f_csv:
                csv_content = f_csv.read()
            st.download_button(
                label=f"Tai ket qua {label} (CSV)",
                data=csv_content,
                file_name=fname,
                mime="text/csv",
            )
'''

with open(path, 'a', encoding='utf-8') as f:
    f.write(tab_evaluate_code)

print("OK - Tab Evaluate appended")
