import customtkinter as ctk
from tkinter import messagebox
from typing import Optional

class DevDashboard(ctk.CTkToplevel):
    def __init__(self, parent, llm_engine=None, config=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent
        self.llm = llm_engine
        self.config = config or {}
        self.title("🔧 Entwickler-Bereich")
        self.geometry("1200x850")
        self.minsize(1000, 700)

        from auth.auth_manager import AuthManager
        from dev_tools.feedback_mode import FeedbackStore
        from dev_tools.metrics_tracker import MetricsTracker
        from dev_tools.layer_trainer import LayerTrainer
        from dev_tools.benchmarker import Benchmarker
        from dev_tools.checkpoint_manager import CheckpointManager

        self.auth = AuthManager()
        self.feedback = FeedbackStore()
        self.metrics = MetricsTracker()
        self.benchmarker = Benchmarker()
        self.checkpoints = CheckpointManager()
        self.layer_trainer = LayerTrainer(self.llm.model) if self.llm and hasattr(self.llm,'model') else None

        self.feedback_enabled = ctk.BooleanVar(value=False)
        self.metrics_enabled = ctk.BooleanVar(value=False)
        self.layer_mode_enabled = ctk.BooleanVar(value=False)
        self.auto_benchmark_enabled = ctk.BooleanVar(value=False)

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1); self.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(self, height=50, corner_radius=10)
        header.grid(row=0, column=0, padx=15, pady=(15,5), sticky="ew")
        ctk.CTkLabel(header, text="🔧 Entwickler-Dashboard", font=("SF Pro",20,"bold")).pack(side="left", padx=15, pady=10)
        ctk.CTkLabel(header, text="Admin-Modus", font=("SF Pro",12), text_color="orange").pack(side="right", padx=15)

        self.tabs = ctk.CTkTabview(self, corner_radius=12)
        self.tabs.grid(row=1, column=0, padx=15, pady=5, sticky="nsew")
        for t in ["Toggles","Feedback","Metrics","Layer Soup","Checkpoints","Benchmarks"]: self.tabs.add(t)

        self._build_toggles_tab()
        self._build_feedback_tab()
        self._build_metrics_tab()
        self._build_layer_tab()
        self._build_checkpoints_tab()
        self._build_benchmarks_tab()

    def _build_toggles_tab(self):
        tab = self.tabs.tab("Toggles"); tab.grid_columnconfigure(0, weight=1)
        for i,(text,desc,var,cmd) in enumerate([
            ("📝 Feedback-Modus aktivieren","Bewertung jeder Antwort (👍/👎)",self.feedback_enabled,self._on_toggle_feedback),
            ("📊 Metrics-Tracking aktivieren","Genauigkeit, Trainingszeit, Token-Usage",self.metrics_enabled,self._on_toggle_metrics),
            ("🧪 Layer-Soup Modus aktivieren","Freeze/unfreeze + Soup-Modifikationen",self.layer_mode_enabled,self._on_toggle_layer),
            ("⚡ Automatische Benchmarks aktivieren","Nach Training automatisch benchmarken",self.auto_benchmark_enabled,self._on_toggle_benchmark)
        ]):
            f = ctk.CTkFrame(tab, corner_radius=12); f.pack(fill="x", padx=10, pady=10)
            ctk.CTkSwitch(f, text=text, variable=var, command=cmd, font=("SF Pro",14)).pack(side="left", padx=15, pady=12)
            ctk.CTkLabel(f, text=desc, font=("SF Pro",11), text_color="gray").pack(side="right", padx=15)

    def _build_feedback_tab(self):
        tab = self.tabs.tab("Feedback")
        ctk.CTkLabel(tab, text="Gesammeltes Feedback (RLHF-Daten)", font=("SF Pro",16,"bold")).pack(pady=(10,5))
        self.feedback_text = ctk.CTkTextbox(tab, wrap="word", corner_radius=10, height=400)
        self.feedback_text.pack(fill="both", expand=True, padx=10, pady=5)
        bf = ctk.CTkFrame(tab, fg_color="transparent"); bf.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(bf, text="🔄 Aktualisieren", command=self._refresh_feedback).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="💾 Exportieren", command=self._export_feedback).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="🗑 Leeren", fg_color="#c0392b", command=self._clear_feedback).pack(side="left", padx=5)

    def _build_metrics_tab(self):
        tab = self.tabs.tab("Metrics"); tab.grid_columnconfigure(0, weight=1); tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="📈 Trainings-Metriken", font=("SF Pro",16,"bold")).grid(row=0, column=0, pady=(10,5))
        self.metrics_table = ctk.CTkTextbox(tab, wrap="none", corner_radius=10)
        self.metrics_table.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        bf = ctk.CTkFrame(tab, fg_color="transparent"); bf.grid(row=2, column=0, pady=5)
        ctk.CTkButton(bf, text="🔄 Aktualisieren", command=self._refresh_metrics).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="📊 Graph", command=self._show_metrics_graph).pack(side="left", padx=5)

    def _build_layer_tab(self):
        tab = self.tabs.tab("Layer Soup"); tab.grid_columnconfigure(0, weight=1); tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="🧪 Layer-Manipulation & Soup", font=("SF Pro",16,"bold")).grid(row=0, column=0, pady=(10,5))
        if not self.layer_trainer:
            ctk.CTkLabel(tab, text="Kein Modell geladen.", text_color="red").grid(row=1, column=0); return
        self.layer_list = ctk.CTkScrollableFrame(tab, corner_radius=10, height=400)
        self.layer_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.layer_vars = {}
        for name in self.layer_trainer.list_layers()[:50]:
            var = ctk.BooleanVar(value=True); self.layer_vars[name] = var
            r = ctk.CTkFrame(self.layer_list, fg_color="transparent"); r.pack(fill="x", pady=1)
            ctk.CTkCheckBox(r, text=name, variable=var, font=("SF Mono",10)).pack(side="left", padx=5)
        ctrl = ctk.CTkFrame(tab, fg_color="transparent"); ctrl.grid(row=2, column=0, pady=10)
        ctk.CTkButton(ctrl, text="❄️ Freeze unmarkierte", command=self._freeze_unselected).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="🔥 Unfreeze alle", command=self._unfreeze_all).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="🎲 Noise (Soup)", command=self._apply_soup_noise).pack(side="left", padx=5)

    def _build_checkpoints_tab(self):
        tab = self.tabs.tab("Checkpoints"); tab.grid_columnconfigure(0, weight=1); tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="💾 Modell-Checkpoints", font=("SF Pro",16,"bold")).grid(row=0, column=0, pady=(10,5))
        self.cp_list = ctk.CTkTextbox(tab, wrap="word", corner_radius=10)
        self.cp_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        bf = ctk.CTkFrame(tab, fg_color="transparent"); bf.grid(row=2, column=0, pady=10)
        ctk.CTkButton(bf, text="🔄 Aktualisieren", command=self._refresh_checkpoints).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="💾 Jetzt speichern", command=self._save_now).pack(side="left", padx=5)

    def _build_benchmarks_tab(self):
        tab = self.tabs.tab("Benchmarks"); tab.grid_columnconfigure(0, weight=1); tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="⚡ Benchmark-Ergebnisse", font=("SF Pro",16,"bold")).grid(row=0, column=0, pady=(10,5))
        self.bench_text = ctk.CTkTextbox(tab, wrap="word", corner_radius=10)
        self.bench_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        bf = ctk.CTkFrame(tab, fg_color="transparent"); bf.grid(row=2, column=0, pady=10)
        ctk.CTkButton(bf, text="🔄 Aktualisieren", command=self._refresh_benchmarks).pack(side="left", padx=5)
        ctk.CTkButton(bf, text="▶️ Benchmark starten", command=self._run_benchmark_now).pack(side="left", padx=5)

    def _on_toggle_feedback(self): print(f"[DEV] Feedback: {'ON' if self.feedback_enabled.get() else 'OFF'}")
    def _on_toggle_metrics(self): print(f"[DEV] Metrics: {'ON' if self.metrics_enabled.get() else 'OFF'}")
    def _on_toggle_layer(self): print(f"[DEV] Layer-Soup: {'ON' if self.layer_mode_enabled.get() else 'OFF'}")
    def _on_toggle_benchmark(self): print(f"[DEV] Auto-Bench: {'ON' if self.auto_benchmark_enabled.get() else 'OFF'}")

    def _refresh_feedback(self):
        self.feedback_text.delete("0.0","end")
        for e in self.feedback.get_all()[-20:]:
            r = "👍" if e["rating"]==1 else "👎" if e["rating"]==-1 else "➖"
            self.feedback_text.insert("end", f"{r} {e['timestamp']}\nPrompt: {e['prompt'][:80]}...\n\n")
    def _export_feedback(self): messagebox.showinfo("Export", f"Gespeichert unter:\n{self.feedback.export_for_training()}")
    def _clear_feedback(self): self.feedback.clear(); self._refresh_feedback()

    def _refresh_metrics(self):
        self.metrics_table.delete("0.0","end")
        sessions = self.metrics.get_latest(20)
        self.metrics_table.insert("end", f"{'Zeit':<20} {'Modell':<25} {'Acc':<8} {'Loss':<8} {'Tokens':<10} {'Sek':<8}\n{'='*80}\n")
        for s in sessions:
            self.metrics_table.insert("end", f"{s['timestamp']:<20} {s['model']:<25} {s['accuracy']:<8} {s['loss']:<8} {s['tokens_used']:<10} {s['train_time_sec']:<8}\n")

    def _show_metrics_graph(self):
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            sessions = self.metrics.get_all_sessions()
            if len(sessions) < 2: messagebox.showinfo("Info", "Mindestens 2 Sessions nötig."); return
            fig, axes = plt.subplots(2,2, figsize=(10,8)); fig.suptitle("Trainings-Metriken", fontsize=14)
            x = list(range(len(sessions)))
            for ax, key, title, color in [(axes[0,0],"accuracy","Genauigkeit","g"),(axes[0,1],"loss","Loss","r"),
                                          (axes[1,0],"tokens_used","Token-Usage","b"),(axes[1,1],"train_time_sec","Zeit (s)","orange")]:
                ax.plot(x, [s[key] for s in sessions], f'{color}-o'); ax.set_title(title); ax.grid(True)
            plt.tight_layout()
            win = ctk.CTkToplevel(self); win.title("📊 Metrics Graph"); win.geometry("900x700")
            canvas = FigureCanvasTkAgg(fig, master=win); canvas.draw(); canvas.get_tk_widget().pack(fill="both", expand=True)
        except ImportError: messagebox.showerror("Fehler", "pip install matplotlib")

    def _freeze_unselected(self):
        if not self.layer_trainer: return
        self.layer_trainer.freeze_all()
        for name, var in self.layer_vars.items():
            if var.get(): self.layer_trainer.unfreeze_layer(name)
        messagebox.showinfo("Layer", "Unmarkierte Layer gefreezed.")
    def _unfreeze_all(self):
        if self.layer_trainer: self.layer_trainer.unfreeze_all(); messagebox.showinfo("Layer", "Alle unfreezed.")
    def _apply_soup_noise(self):
        if not self.layer_trainer: return
        for name, var in self.layer_vars.items():
            if var.get(): self.layer_trainer.apply_soup_noise(name, 0.005)
        messagebox.showinfo("Soup", "Noise angewendet.")

    def _refresh_checkpoints(self):
        self.cp_list.delete("0.0","end")
        for cp in self.checkpoints.list_checkpoints():
            self.cp_list.insert("end", f"💾 {cp['name']} ({cp['timestamp']})\n   {cp['path']}\n\n")
    def _save_now(self):
        if not self.llm or not hasattr(self.llm,'model'): messagebox.showerror("Fehler","Kein Modell geladen."); return
        p = self.checkpoints.save_checkpoint(self.llm.model, self.llm.tokenizer, "manual_save", {"device":self.llm.device})
        self._refresh_checkpoints(); messagebox.showinfo("Checkpoint", f"Gespeichert:\n{p}")

    def _refresh_benchmarks(self):
        self.bench_text.delete("0.0","end")
        for r in self.benchmarker.get_all_results()[-10:]:
            self.bench_text.insert("end", f"🕐 {r['timestamp']} | {r['avg_inference_time_ms']}ms | {r['avg_tokens_per_sec']} tok/s | PPL: {r.get('perplexity','N/A')}\n\n")
    def _run_benchmark_now(self):
        if not self.llm or not hasattr(self.llm,'model'): messagebox.showerror("Fehler","Kein Modell."); return
        self.bench_text.insert("end","⏳ Benchmark läuft...\n"); self.update()
        try:
            res = self.benchmarker.run_benchmark(self.llm.model, self.llm.tokenizer,
                ["Was ist 2+2?","Erkläre Quantenphysik.","Schreibe Hello World in Python.","Hauptstadt von Frankreich?"])
            self._refresh_benchmarks(); messagebox.showinfo("Benchmark", f"Avg: {res['avg_inference_time_ms']}ms\nTok/s: {res['avg_tokens_per_sec']}")
        except Exception as e: messagebox.showerror("Fehler", str(e))