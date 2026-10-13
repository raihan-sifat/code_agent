import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from utils.config import Config
from utils.security import scrub_secrets
from parser.preprocessor import ArchitecturePreprocessor
from agent.core import CodeAgent
from api.deepseek_client import DeepSeekClient

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CodeAgentApp(ctk.CTk):
    """
    Main GUI application with:
    - API Key input field
    - Input file browser (Architecture docs)
    - Output directory browser
    - Generate button
    - Real-time log/progress area
    """
    def __init__(self):
        super().__init__()
        
        self.title("Code Agent - AI Code Generator")
        self.geometry("920x780")
        self.minsize(820, 640)
        
        self.config = Config()
        try:
            self.config.load()
        except Exception:
            pass

        # Pause/cancel controls for the running generation (checked by the agent
        # loop between turns).
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        
        # --- Top Section - Configuration ---
        self.frame_config = ctk.CTkFrame(self)
        self.frame_config.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.frame_config.grid_columnconfigure(1, weight=1)
        
        lbl_title = ctk.CTkLabel(self.frame_config, text="Code Agent - AI Code Generator", font=ctk.CTkFont(size=20, weight="bold"))
        lbl_title.grid(row=0, column=0, columnspan=4, pady=(10, 5))
        
        lbl_api_key = ctk.CTkLabel(self.frame_config, text="DeepSeek API Key:")
        lbl_api_key.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        self.entry_api_key = ctk.CTkEntry(self.frame_config, show="*")
        self.entry_api_key.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        self.btn_toggle_key = ctk.CTkButton(self.frame_config, text="Show", width=60, command=self._toggle_api_key)
        self.btn_toggle_key.grid(row=1, column=2, padx=5, pady=10)
        
        self.btn_save_key = ctk.CTkButton(self.frame_config, text="Save", width=60, command=self._save_api_key)
        self.btn_save_key.grid(row=1, column=3, padx=(5, 10), pady=10)
        
        self.btn_test_key = ctk.CTkButton(self.frame_config, text="Test Key", width=80, command=self._test_api_key)
        self.btn_test_key.grid(row=1, column=4, padx=(0, 10), pady=10)
        
        lbl_model = ctk.CTkLabel(self.frame_config, text="Model:")
        lbl_model.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        
        self.combo_model = ctk.CTkComboBox(self.frame_config, values=["deepseek-chat", "deepseek-reasoner"])
        self.combo_model.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        # --- Middle Section - File Selection ---
        self.frame_files = ctk.CTkFrame(self)
        self.frame_files.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_files.grid_columnconfigure(1, weight=1)
        
        lbl_doc = ctk.CTkLabel(self.frame_files, text="Architecture Doc (.md):")
        lbl_doc.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.entry_doc = ctk.CTkEntry(self.frame_files)
        self.entry_doc.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.btn_browse_doc = ctk.CTkButton(self.frame_files, text="Browse", width=80, command=self._browse_doc)
        self.btn_browse_doc.grid(row=0, column=2, padx=(5, 10), pady=10)
        
        lbl_views = ctk.CTkLabel(self.frame_files, text="Architecture Views (.md):")
        lbl_views.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        self.entry_views = ctk.CTkEntry(self.frame_files)
        self.entry_views.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        
        self.btn_browse_views = ctk.CTkButton(self.frame_files, text="Browse", width=80, command=self._browse_views)
        self.btn_browse_views.grid(row=1, column=2, padx=(5, 10), pady=10)
        
        lbl_out = ctk.CTkLabel(self.frame_files, text="Output Directory:")
        lbl_out.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        
        self.entry_out = ctk.CTkEntry(self.frame_files)
        self.entry_out.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        self.btn_browse_out = ctk.CTkButton(self.frame_files, text="Browse", width=80, command=self._browse_out)
        self.btn_browse_out.grid(row=2, column=2, padx=(5, 10), pady=10)
        
        # --- Quick-start instructions (shown under the input fields) ---
        divider = ctk.CTkFrame(self.frame_files, height=1, fg_color=("gray70", "gray30"))
        divider.grid(row=3, column=0, columnspan=3, padx=10, pady=(0, 5), sticky="ew")
        
        lbl_help = ctk.CTkLabel(
            self.frame_files,
            text=(
                "How to use:\n"
                "  1.  Paste your DeepSeek API key, click \u201cTest Key\u201d to confirm it works, then \u201cSave\u201d (optional).\n"
                "  2.  Browse to the Architecture Doc (.md) and the Architecture Views (.md) files.\n"
                "  3.  Choose an Output Directory \u2013 the native desktop game is written there.\n"
                "  4.  Click \u201cGenerate Project\u201d and follow the log below. "
                "Use Pause/Resume or Cancel at any time.\n"
                "  5.  Run the generated build.bat, then open the game .exe in dist. Source launch: run.bat."
            ),
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=("gray30", "gray75"),
            wraplength=820,
        )
        lbl_help.grid(row=4, column=0, columnspan=3, padx=10, pady=(0, 12), sticky="w")

        # Keep the help text wrapped to the panel width when the window resizes.
        self.frame_files.bind(
            "<Configure>",
            lambda e: lbl_help.configure(wraplength=max(400, e.width - 40)),
        )
        
        # --- Action Section ---
        self.frame_action = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_action.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.frame_action.grid_columnconfigure(0, weight=1)
        
        self.btn_generate = ctk.CTkButton(self.frame_action, text="Generate Project", font=ctk.CTkFont(size=16, weight="bold"), height=40, command=self._generate_project)
        self.btn_generate.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="ew")
        
        self.btn_pause = ctk.CTkButton(
            self.frame_action, text="Pause", width=100, height=40,
            state="disabled", command=self._toggle_pause,
        )
        self.btn_pause.grid(row=0, column=1, padx=(0, 10), pady=10)
        
        self.btn_cancel = ctk.CTkButton(
            self.frame_action, text="Cancel", width=100, height=40,
            fg_color="#8B1A1A", hover_color="#B22222",
            state="disabled", command=self._cancel_generation,
        )
        self.btn_cancel.grid(row=0, column=2, pady=10)
        
        self.progress = ctk.CTkProgressBar(self.frame_action, mode="indeterminate")
        self.progress.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        self.progress.set(0)
        
        # --- Bottom Section - Log Output ---
        self.frame_log = ctk.CTkFrame(self)
        self.frame_log.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.frame_log.grid_columnconfigure(0, weight=1)
        self.frame_log.grid_rowconfigure(0, weight=1)
        
        self.log_text = ctk.CTkTextbox(self.frame_log, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Configure text colors (tags)
        self.log_text.tag_config("info", foreground="white")
        self.log_text.tag_config("tool", foreground="cyan")
        self.log_text.tag_config("error", foreground="red")
        self.log_text.tag_config("success", foreground="green")

    def _load_config(self):
        try:
            if self.config.api_key:
                self.entry_api_key.insert(0, self.config.api_key)
            if hasattr(self.config, "model") and self.config.model:
                self.combo_model.set(self.config.model)
        except Exception:
            pass

    def _toggle_api_key(self):
        if self.entry_api_key.cget("show") == "*":
            self.entry_api_key.configure(show="")
            self.btn_toggle_key.configure(text="Hide")
        else:
            self.entry_api_key.configure(show="*")
            self.btn_toggle_key.configure(text="Show")

    def _save_api_key(self):
        api_key = self.entry_api_key.get().strip()
        model = self.combo_model.get().strip()
        if api_key:
            self.config.api_key = api_key
            self.config.model = model
            try:
                self.config.save()
                messagebox.showinfo(
                    "Success",
                    "Configuration saved to\n"
                    f"{self.config.config_file}"
                )
            except Exception as e:
                messagebox.showwarning("Warning", f"Could not save config: {e}")
        else:
            messagebox.showwarning("Warning", "API key cannot be empty.")

    def _test_api_key(self):
        api_key = self.entry_api_key.get().strip()
        model = self.combo_model.get().strip()
        if not api_key:
            messagebox.showwarning("Warning", "Enter an API key first.")
            return

        self.btn_test_key.configure(state="disabled", text="Testing...")
        self._log_message("Testing API key...", "info")

        def _run():
            try:
                client = DeepSeekClient(api_key=api_key, model=model)
                ok, msg = client.test_key()
            except Exception as e:
                ok, msg = False, scrub_secrets(str(e), api_key)

            def _done():
                self.btn_test_key.configure(state="normal", text="Test Key")
                self._log_message(
                    ("Key valid: " if ok else "Key check failed: ") + msg,
                    "success" if ok else "error",
                )
                if ok:
                    messagebox.showinfo("Test Key", "API key is valid.")
                else:
                    messagebox.showerror("Test Key", msg)

            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    def _browse_doc(self):
        path = filedialog.askopenfilename(filetypes=[("Markdown files", "*.md"), ("All files", "*.*")])
        if path:
            self.entry_doc.delete(0, tk.END)
            self.entry_doc.insert(0, path)

    def _browse_views(self):
        path = filedialog.askopenfilename(filetypes=[("Markdown files", "*.md"), ("All files", "*.*")])
        if path:
            self.entry_views.delete(0, tk.END)
            self.entry_views.insert(0, path)

    def _browse_out(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_out.delete(0, tk.END)
            self.entry_out.insert(0, path)

    def _log_message(self, message: str, tag: str = "info"):
        try:
            key = self.entry_api_key.get().strip()
        except Exception:
            key = ""
        message = scrub_secrets(message, key)

        def _update():
            self.log_text.insert(tk.END, message + "\n", tag)
            self.log_text.see(tk.END)
        self.after(0, _update)

    def _toggle_pause(self):
        """Pause/resume the running generation (checked at turn boundaries)."""
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.btn_pause.configure(text="Pause")
            self.progress.start()
            self._log_message("Resume requested.", "info")
        else:
            self._pause_event.set()
            self.btn_pause.configure(text="Resume")
            self.progress.stop()
            self._log_message(
                "Pause requested (takes effect after the current step).", "info"
            )

    def _cancel_generation(self):
        """Request cancellation; the agent stops at the next turn boundary."""
        self._cancel_event.set()
        self._pause_event.clear()  # wake the loop so it can observe the cancel
        self.btn_cancel.configure(state="disabled")
        self.btn_pause.configure(state="disabled", text="Pause")
        self._log_message("Cancel requested...", "info")

    def _generate_project(self):
        api_key = self.entry_api_key.get().strip()
        model = self.combo_model.get().strip()
        doc_path = self.entry_doc.get().strip()
        views_path = self.entry_views.get().strip()
        out_path = self.entry_out.get().strip()
        
        if not all([api_key, doc_path, views_path, out_path]):
            messagebox.showwarning("Warning", "All fields must be filled!")
            return
            
        if not os.path.isfile(doc_path):
            messagebox.showwarning("Warning", f"Architecture doc not found:\n{doc_path}")
            return
        if not os.path.isfile(views_path):
            messagebox.showwarning("Warning", f"Architecture views file not found:\n{views_path}")
            return

        # Fresh run: clear any previous pause/cancel state.
        self._cancel_event.clear()
        self._pause_event.clear()
            
        self._set_inputs_state("disabled")
        self.btn_generate.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="Pause")
        self.btn_cancel.configure(state="normal")
        self.progress.start()
        self.log_text.delete("1.0", tk.END)
        
        self._log_message("Generating a local desktop game (Python/tkinter, offline play, Windows .exe build script)...", "info")
        
        thread = threading.Thread(
            target=self._run_agent_task, 
            args=(api_key, model, doc_path, views_path, out_path), 
            daemon=True
        )
        thread.start()

    def _run_agent_task(self, api_key: str, model: str, doc_path: str, views_path: str, out_path: str):
        try:
            self._log_message("Parsing architecture documentation...", "info")
            preprocessor = ArchitecturePreprocessor()
            arch_data = preprocessor.preprocess(doc_path, views_path)
            
            doc_sections = arch_data.get("documentation", {}).get("sections", {})
            view_map = arch_data.get("views", {}).get("views", {})
            if not doc_sections or not view_map:
                self._log_message(
                    "Parsing failed: no sections/diagrams found. "
                    "Check that the selected files are valid architecture markdown.",
                    "error",
                )
                self.after(0, lambda: messagebox.showerror(
                    "Error", "Could not parse the selected architecture files."))
                return
            
            def on_message(msg: str):
                self._log_message(f"[Agent]: {msg}", "info")
                
            def on_tool(tool_name: str, result: str):
                self._log_message(f"[Tool - {tool_name}]: {result}", "tool")
                
            def on_error(err: str):
                self._log_message(f"[Error]: {err}", "error")
            
            self._log_message("Initializing Code Agent...", "info")
            agent = CodeAgent(api_key=api_key, model=model)
            
            self._log_message("Starting generation process...", "info")
            success = agent.generate_project(
                architecture_data=arch_data,
                output_dir=out_path,
                on_message=on_message,
                on_tool=on_tool,
                on_error=on_error,
                cancel_event=self._cancel_event,
                pause_event=self._pause_event,
            )
            
            if self._cancel_event.is_set():
                self._log_message("Project generation cancelled by user.", "error")
            elif success:
                self._log_message("Project generation completed successfully!", "success")
                self.after(0, lambda: messagebox.showinfo("Success", "Desktop game source generated successfully!\n\nRun build.bat in the generated project to create the game executable in dist.\nOr use run.bat to play from source with Python.\n\nBuild and gameplay still need to be verified."))
            else:
                self._log_message("Project generation failed. Check logs.", "error")
                self.after(0, lambda: messagebox.showerror("Error", "Project generation failed."))
                
        except Exception as e:
            self._log_message(f"Exception: {str(e)}", "error")
            self.after(0, lambda: messagebox.showerror("Error", f"An error occurred:\n{str(e)}"))
        finally:
            self.after(0, self._stop_generation)

    def _set_inputs_state(self, state: str):
        """Enable/disable all input widgets during generation."""
        for widget in (self.entry_api_key, self.combo_model,
                       self.entry_doc, self.entry_views, self.entry_out):
            widget.configure(state=state)
        for btn in (self.btn_toggle_key, self.btn_save_key, self.btn_test_key,
                    self.btn_browse_doc, self.btn_browse_views, self.btn_browse_out):
            btn.configure(state=state)

    def _stop_generation(self):
        self.progress.stop()
        self.progress.set(0)
        self.btn_generate.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="Pause")
        self.btn_cancel.configure(state="disabled")
        self._cancel_event.clear()
        self._pause_event.clear()
        self._set_inputs_state("normal")
