#!/usr/bin/env python3
import threading, customtkinter as ctk
from config_loader import load_config
from llm_engine import ToolAugmentedLLM
from mcp_protocol import MCPClient
from tools import create_math_tools
from logger import get_logger

try:
    from auth.auth_manager import AuthManager
    from dev_tools.dev_dashboard import DevDashboard
    from dev_tools.feedback_mode import FeedbackStore
    DEV_AVAILABLE = True
except ImportError:
    DEV_AVAILABLE = False

class ChatGUI:
    def __init__(self):
        ctk.set_appearance_mode("System"); ctk.set_default_color_theme("blue")
        self.root = ctk.CTk(); self.root.title("Tool-Augmented LLM"); self.root.geometry("1000x780"); self.root.minsize(800,600)
        self.config = load_config(); self.log = get_logger(self.config)
        self.server = create_math_tools(); self.client = MCPClient(self.server)
        self.llm = None; self.history = []; self.is_generating = False
        self.auth = AuthManager() if DEV_AVAILABLE else None
        self.feedback_store = FeedbackStore() if DEV_AVAILABLE else None
        self.dev_dashboard = None; self.current_user = None; self.is_admin = False; self.feedback_mode = False
        self._build_ui(); self._load_model_async(); self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.root.grid_columnconfigure(0, weight=1); self.root.grid_rowconfigure(0, weight=1)
        self.main_frame = ctk.CTkFrame(self.root, corner_radius=15)
        self.main_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Header
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=40)
        header.grid(row=0, column=0, padx=10, pady=(5,0), sticky="ew")
        self.login_btn = ctk.CTkButton(header, text="🔐 Login", width=100, corner_radius=10, command=self._show_login)
        self.login_btn.grid(row=0, column=1, padx=5)
        self.dev_btn = ctk.CTkButton(header, text="🔧 Dev", width=100, corner_radius=10, command=self._open_dev_dashboard, state="disabled")
        self.dev_btn.grid(row=0, column=2, padx=5)
        self.feedback_btn = ctk.CTkButton(header, text="⭐ FB: OFF", width=120, corner_radius=10, command=self._toggle_feedback_mode, state="disabled")
        self.feedback_btn.grid(row=0, column=3, padx=5)

        # Chat
        chat_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        chat_container.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        chat_container.grid_columnconfigure(0, weight=1); chat_container.grid_rowconfigure(0, weight=1)
        self.chat_display = ctk.CTkTextbox(chat_container, font=("SF Mono",12), wrap="word", corner_radius=12, border_width=2,
            border_color=("gray80","gray30"), fg_color=("gray95","gray17"), text_color=("gray10","gray90"), state="disabled")
        self.chat_display.grid(row=0, column=0, sticky="nsew")

        # Input
        input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        input_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)
        self.input_box = ctk.CTkEntry(input_frame, placeholder_text="Nachricht eingeben...", font=("SF Pro",13), height=44, corner_radius=12, border_width=2)
        self.input_box.grid(row=0, column=0, padx=(0,10), sticky="ew")
        self.input_box.bind("<Return>", lambda e: self._on_send())
        self.send_btn = ctk.CTkButton(input_frame, text="➤  Senden", command=self._on_send, width=110, height=44, corner_radius=12, font=("SF Pro",13,"bold"))
        self.send_btn.grid(row=0, column=1)

        # Buttons
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=10, pady=(0,5), sticky="ew")
        ctk.CTkButton(btn_frame, text="🗑  Leeren", command=self._clear_chat, width=100, corner_radius=10).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_frame, text="🔧  Tools", command=self._show_tools, width=100, corner_radius=10).pack(side="left", padx=(0,8))
        ctk.CTkButton(btn_frame, text="⏹  Stopp", command=self._stop_generation, width=100, corner_radius=10, fg_color="#c0392b").pack(side="left")

        # Status
        self.status_var = ctk.StringVar(value="⏳  Modell wird geladen...")
        self.status_bar = ctk.CTkLabel(self.main_frame, textvariable=self.status_var, font=("SF Pro",11), anchor="w", height=30,
            corner_radius=10, fg_color=("gray90","gray20"), text_color=("gray50","gray60"), padx=12)
        self.status_bar.grid(row=4, column=0, padx=10, pady=(0,10), sticky="ew")
        self.input_box.focus()

    def _on_close(self): self.log.info("GUI geschlossen"); self.root.destroy()

    def _load_model_async(self):
        def load():
            try:
                self._insert_system("⏳  Modell wird geladen...\n")
                self.llm = ToolAugmentedLLM(config=self.config)
                d = "🖥️  GPU" if self.llm.device=="cuda" else "💻  CPU"
                self.log.info(f"Bereit | {d} | {self.llm.model_name.split('/')[-1]}")
                self.root.after(0, lambda: self.status_var.set(f"✅  Bereit  |  {d}  |  {self.llm.model_name.split('/')[-1]}"))
                self.root.after(0, lambda: self._insert_system(f"✅  Bereit! ({d})\n\n"))
            except Exception as e:
                self.log.error(f"Ladefehler: {e}")
                self.root.after(0, lambda: self.status_var.set(f"❌  {str(e)[:60]}"))
                self.root.after(0, lambda: self._show_error(str(e)))
        threading.Thread(target=load, daemon=True).start()

    # --- Login System ---
    def _show_login(self):
        if not DEV_AVAILABLE: messagebox.showinfo("Info", "Dev-Module nicht verfügbar."); return
        win = ctk.CTkToplevel(self.root); win.title("🔐 Login"); win.geometry("400x300"); win.transient(self.root); win.grab_set()
        ctk.CTkLabel(win, text="Entwickler-Login", font=("SF Pro",18,"bold")).pack(pady=15)
        ctk.CTkLabel(win, text="Benutzername:").pack()
        ue = ctk.CTkEntry(win, width=250); ue.pack(pady=5); ue.insert(0,"Admin")
        ctk.CTkLabel(win, text="Passwort:").pack()
        pe = ctk.CTkEntry(win, width=250, show="*"); pe.pack(pady=5); pe.insert(0,"1234")
        def do_login():
            res = self.auth.authenticate(ue.get().strip(), pe.get().strip())
            if res:
                self.current_user = res["username"]; self.is_admin = (res["role"]=="admin"); win.destroy()
                if res.get("force_password_change"): self._show_password_change()
                else: self._on_login_success()
            else: ctk.CTkLabel(win, text="❌ Login fehlgeschlagen", text_color="red").pack()
        ctk.CTkButton(win, text="Einloggen", command=do_login).pack(pady=15)

    def _show_password_change(self):
        win = ctk.CTkToplevel(self.root); win.title("🔑 Erstanmeldung"); win.geometry("450x350"); win.transient(self.root); win.grab_set()
        ctk.CTkLabel(win, text="Zugangsdaten ändern", font=("SF Pro",16,"bold")).pack(pady=15)
        ctk.CTkLabel(win, text="Neuer Benutzername:").pack()
        nu = ctk.CTkEntry(win, width=250); nu.pack(pady=5)
        ctk.CTkLabel(win, text="Neues Passwort:").pack()
        np = ctk.CTkEntry(win, width=250, show="*"); np.pack(pady=5)
        ctk.CTkLabel(win, text="Wiederholen:").pack()
        np2 = ctk.CTkEntry(win, width=250, show="*"); np2.pack(pady=5)
        def save():
            if np.get()!=np2.get(): ctk.CTkLabel(win, text="❌ Passwörter stimmen nicht überein", text_color="red").pack(); return
            if len(np.get())<4: ctk.CTkLabel(win, text="❌ Mindestens 4 Zeichen", text_color="red").pack(); return
            if self.auth.change_credentials("Admin", nu.get() or "Admin", np.get()):
                self.auth.mark_first_login_done(); win.destroy(); self._on_login_success(); messagebox.showinfo("Erfolg","Gespeichert!")
        ctk.CTkButton(win, text="Speichern", command=save).pack(pady=15)

    def _on_login_success(self):
        self.login_btn.configure(text=f"👤 {self.current_user}", state="disabled")
        if self.is_admin:
            self.dev_btn.configure(state="normal"); self.feedback_btn.configure(state="normal")
            self.log.info(f"Admin-Login: {self.current_user}")
        else: self.log.info(f"User-Login: {self.current_user}")

    def _open_dev_dashboard(self):
        if not self.is_admin or not DEV_AVAILABLE: return
        self.dev_dashboard = DevDashboard(self.root, llm_engine=self.llm, config=self.config)

    def _toggle_feedback_mode(self):
        if not self.feedback_store: return
        self.feedback_mode = not self.feedback_mode
        s,c = ("ON","green") if self.feedback_mode else ("OFF","default")
        self.feedback_btn.configure(text=f"⭐ FB: {s}", fg_color=c)

    # --- Chat ---
    def _on_send(self):
        if self.is_generating or not self.llm: return
        text = self.input_box.get().strip()
        if not text: return
        self.input_box.delete(0,"end"); self._insert_user(text); self._set_input_state(False); self.is_generating = True; self.status_var.set("🤔  Denke...")
        threading.Thread(target=self._generate_async, args=(text,), daemon=True).start()

    def _generate_async(self, text: str):
        try:
            result = self.llm.chat_with_tools(text, self.client, self.history)
            def update_ui():
                self._insert_bot(result["response"])
                if result["tool_calls"]:
                    names = [t.tool_name for t in result["tool_calls"]]
                    self._insert_tool(f"Tools: {', '.join(names)}")
                if self.feedback_mode and self.feedback_store:
                    self._show_feedback_row(text, result["response"])
                self.history = result["conversation"]
                if len(self.history)>20: self.history = self.history[-20:]
                self.is_generating = False; self._set_input_state(True); self.status_var.set("✅  Bereit")
            self.root.after(0, update_ui)
        except Exception as e:
            self.log.error(f"Fehler: {e}")
            self.root.after(0, lambda: self._insert_system(f"❌  {e}\n"))
            self.root.after(0, lambda: self._set_input_state(True))
            self.root.after(0, lambda: self.status_var.set("❌  Fehler"))

    def _show_feedback_row(self, prompt: str, response: str):
        fb = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        fb.grid(row=5, column=0, padx=10, pady=(0,5), sticky="e")
        def rate(r):
            self.feedback_store.add_feedback(prompt, response, r, model_name=self.llm.model_name)
            fb.destroy(); self._insert_system("Feedback gespeichert.\n")
        ctk.CTkButton(fb, text="👍", width=40, command=lambda: rate(1)).pack(side="left", padx=2)
        ctk.CTkButton(fb, text="👎", width=40, command=lambda: rate(-1)).pack(side="left", padx=2)

    def _stop_generation(self):
        if self.is_generating: self.log.warning("Abbruch"); self.status_var.set("⏹  Abbruch...")

    def _clear_chat(self):
        self.chat_display.configure(state="normal"); self.chat_display.delete("0.0","end"); self.chat_display.configure(state="disabled")
        self.history = []; self.log.info("Chat geleert"); self.status_var.set("✅  Chat geleert")

    def _show_tools(self):
        schemas = self.server.get_tool_schemas()
        dialog = ctk.CTkToplevel(self.root); dialog.title("Tools"); dialog.geometry("420x320"); dialog.transient(self.root); dialog.grab_set()
        tb = ctk.CTkTextbox(dialog, wrap="word", font=("SF Pro",12), corner_radius=10)
        tb.pack(padx=15, pady=15, fill="both", expand=True)
        tb.insert("0.0", "\n".join([f"• {s['function']['name']}: {s['function']['description']}" for s in schemas]))
        tb.configure(state="disabled")
        ctk.CTkButton(dialog, text="Schließen", command=dialog.destroy).pack(pady=(0,15))

    def _show_error(self, msg: str):
        d = ctk.CTkToplevel(self.root); d.title("Fehler"); d.geometry("520x220"); d.transient(self.root)
        ctk.CTkLabel(d, text=f"❌  {msg}", font=("SF Pro",13), wraplength=480).pack(padx=20, pady=20, expand=True)
        ctk.CTkButton(d, text="OK", command=d.destroy).pack(pady=(0,20))

    def _insert_user(self, t): self._insert_text(f"🧑‍💻  Du\n{t}\n\n")
    def _insert_bot(self, t): self._insert_text(f"🤖  Assistent\n{t}\n\n")
    def _insert_tool(self, t): self._insert_text(f"🔧  {t}\n\n")
    def _insert_system(self, t): self._insert_text(f"ℹ️  {t}\n")
    def _insert_text(self, t):
        self.chat_display.configure(state="normal"); self.chat_display.insert("end", t); self.chat_display.configure(state="disabled")
        try: self.chat_display._textbox.see("end")
        except: pass
    def _set_input_state(self, e):
        if e: self.input_box.configure(state="normal"); self.send_btn.configure(state="normal", text="➤  Senden"); self.input_box.focus()
        else: self.input_box.configure(state="disabled"); self.send_btn.configure(state="disabled", text="⏳  ...")

def run_gui():
    app = ChatGUI(); app.root.mainloop()

if __name__ == "__main__":
    run_gui()