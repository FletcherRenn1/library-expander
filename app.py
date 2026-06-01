import sys

if len(sys.argv) > 1 and sys.argv[1] == "--_gdl":
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    from gallery_dl import main as _gdl_main
    _gdl_main()
    sys.exit(0)

import io
import json
import os
import queue as q_mod
import re
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BG        = "#0f0f0f"
SURFACE   = "#1a1a1a"
INPUT_BG  = "#242424"
BORDER    = "#333333"
FG        = "#e8e8e8"
FG_MUTED  = "#888888"
ACCENT    = "#c084fc"
ACCENT_H  = "#a855f7"
SUCCESS   = "#4ade80"
WARNING   = "#facc15"
ERR       = "#f87171"
ACTIVE_BG = "#2a2040"

BROWSERS = ["Chrome", "Firefox", "Edge", "Brave", "None (no cookies)"]

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(APP_DIR, "settings.json")

STATUS_COLORS = {
    "Waiting":     FG_MUTED,
    "Downloading": ACCENT,
    "Converting":  ACCENT,
    "Done":        SUCCESS,
    "Failed":      ERR,
    "Cancelled":   FG_MUTED,
}


def _is_image(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            h = f.read(12)
        return (
            h[:3] == b"\xff\xd8\xff" or          # JPEG
            h[:8] == b"\x89PNG\r\n\x1a\n" or     # PNG
            h[:4] == b"RIFF" and h[8:12] == b"WEBP" or  # WebP
            h[:6] in (b"GIF87a", b"GIF89a")      # GIF
        )
    except Exception:
        return False


def parse_chapter(name: str):
    s = re.sub(r"^(?:chapter|ch\.?|vol\.?)\s*", "", name.strip(), flags=re.IGNORECASE).strip()
    m = re.match(r"^(\d+(?:\.\d+)?)", s)
    if not m:
        return None, None
    num  = m.group(1)
    rest = s[m.end():].strip()
    if rest.startswith("-"):
        t     = rest[1:].strip()
        title = t if t else None
    else:
        title = None
    if "." in num:
        i, d   = num.split(".", 1)
        padded = f"{int(i):03d}.{d}"
    else:
        padded = f"{int(num):03d}"
    return padded, title


def chapter_pdf_name(folder: str) -> str:
    padded, title = parse_chapter(folder)
    if padded is None:
        return re.sub(r'[<>:"/\\|?*]', "_", folder) + ".pdf"
    return f"{padded} - {title}.pdf" if title else f"{padded}.pdf"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Library Expander")
        self.geometry("600x750")
        self.resizable(False, False)
        self.configure(bg=BG)

        self._ui_q       = q_mod.Queue()
        self.jobs        = []
        self._active_idx = None
        self._running    = False
        self._stop_req   = False
        self._cur_proc   = None

        self._load_settings()
        self._build_ui()
        self.after(50, self._poll_ui)

    def _load_settings(self):
        self._cfg = {"output_dir": "", "browser": "Chrome"}
        try:
            with open(SETTINGS) as f:
                self._cfg.update(json.load(f))
        except Exception:
            pass

    def _save_settings(self):
        try:
            with open(SETTINGS, "w") as f:
                json.dump(self._cfg, f, indent=2)
        except Exception:
            pass

    def _entry(self, parent, var):
        return tk.Entry(
            parent, textvariable=var, font=("Segoe UI", 10),
            bg=INPUT_BG, fg=FG, insertbackground=FG,
            relief="flat", bd=0,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
        )

    def _hover(self, w, normal, hovered):
        w.bind("<Enter>", lambda _e: w.configure(bg=hovered))
        w.bind("<Leave>", lambda _e: w.configure(bg=normal))

    def _build_ui(self):
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True, padx=16, pady=10)

        tk.Label(outer, text="Library Expander", font=("Segoe UI", 18, "bold"),
                 bg=BG, fg=ACCENT).pack(anchor="w")
        tk.Label(outer, text="Download manga series and convert to PDF",
                 font=("Segoe UI", 9), bg=BG, fg=FG_MUTED).pack(anchor="w", pady=(0, 8))

        card  = tk.Frame(outer, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(0, 8))
        inner = tk.Frame(card, bg=SURFACE)
        inner.pack(fill="x", padx=14, pady=8)

        tk.Label(inner, text="Series URL", font=("Segoe UI", 10), bg=SURFACE, fg=FG).pack(anchor="w")
        self._url_var = tk.StringVar()
        self._entry(inner, self._url_var).pack(fill="x", ipady=4, pady=(2, 7))

        tk.Label(inner, text="Series folder name", font=("Segoe UI", 10), bg=SURFACE, fg=FG).pack(anchor="w")
        self._folder_var = tk.StringVar()
        self._entry(inner, self._folder_var).pack(fill="x", ipady=4, pady=(2, 7))

        self._resume_var = tk.BooleanVar()
        tk.Checkbutton(
            inner, text="Resume / add new chapters to existing folder",
            variable=self._resume_var, font=("Segoe UI", 10),
            bg=SURFACE, fg=FG, selectcolor=INPUT_BG,
            activebackground=SURFACE, activeforeground=FG,
            command=self._check_resume,
        ).pack(anchor="w")
        self._resume_warn = tk.Label(inner, text="", font=("Segoe UI", 9),
                                     bg=SURFACE, fg=WARNING)
        self._resume_warn.pack(anchor="w", padx=(22, 0))

        tk.Label(inner, text="Output directory", font=("Segoe UI", 10),
                 bg=SURFACE, fg=FG).pack(anchor="w", pady=(6, 0))
        dir_row = tk.Frame(inner, bg=SURFACE)
        dir_row.pack(fill="x", pady=(2, 7))
        self._outdir_var = tk.StringVar(value=self._cfg.get("output_dir", ""))
        self._entry(dir_row, self._outdir_var).pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(dir_row, text="Browse", font=("Segoe UI", 9),
                  bg=INPUT_BG, fg=FG, activebackground=BORDER, activeforeground=FG,
                  relief="flat", bd=0, padx=10, cursor="hand2",
                  command=self._browse).pack(side="left", padx=(6, 0))

        tk.Label(inner, text="Browser (for cookies)", font=("Segoe UI", 10),
                 bg=SURFACE, fg=FG).pack(anchor="w")
        self._browser_var = tk.StringVar(value=self._cfg.get("browser", "Chrome"))
        st = ttk.Style()
        st.theme_use("clam")
        st.configure("D.TCombobox", fieldbackground=INPUT_BG, background=INPUT_BG,
                     foreground=FG, arrowcolor=FG, borderwidth=0,
                     selectbackground=INPUT_BG, selectforeground=FG)
        st.map("D.TCombobox",
               fieldbackground=[("readonly", INPUT_BG)],
               foreground=[("readonly", FG)],
               background=[("readonly", INPUT_BG)])
        ttk.Combobox(inner, textvariable=self._browser_var, values=BROWSERS,
                     state="readonly", font=("Segoe UI", 10), style="D.TCombobox",
                     width=28).pack(anchor="w", pady=(2, 0))

        btn_row = tk.Frame(outer, bg=BG)
        btn_row.pack(fill="x", pady=(0, 8))

        self._add_btn = tk.Button(
            btn_row, text="Add to Queue", font=("Segoe UI", 10),
            bg=SURFACE, fg=FG, activebackground=BORDER, activeforeground=FG,
            relief="flat", bd=0, height=2, cursor="hand2",
            command=self._add_to_queue,
        )
        self._add_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self._start_btn = tk.Button(
            btn_row, text="Start Queue", font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_H, activeforeground="white",
            relief="flat", bd=0, height=2, cursor="hand2",
            command=self._toggle_queue,
        )
        self._start_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))
        self._hover(self._start_btn, ACCENT, ACCENT_H)

        tk.Label(outer, text="Queue", font=("Segoe UI", 9),
                 bg=BG, fg=FG_MUTED).pack(anchor="w")
        q_outer = tk.Frame(outer, bg=SURFACE, highlightthickness=1,
                           highlightbackground=BORDER, height=148)
        q_outer.pack(fill="x", pady=(2, 8))
        q_outer.pack_propagate(False)

        self._q_canvas = tk.Canvas(q_outer, bg=SURFACE, highlightthickness=0, bd=0)
        q_sb = tk.Scrollbar(q_outer, orient="vertical", command=self._q_canvas.yview)
        self._q_canvas.configure(yscrollcommand=q_sb.set)
        q_sb.pack(side="right", fill="y")
        self._q_canvas.pack(side="left", fill="both", expand=True)

        self._q_frame = tk.Frame(self._q_canvas, bg=SURFACE)
        self._q_win   = self._q_canvas.create_window((0, 0), window=self._q_frame, anchor="nw")
        self._q_frame.bind("<Configure>",
                           lambda e: self._q_canvas.configure(scrollregion=self._q_canvas.bbox("all")))
        self._q_canvas.bind("<Configure>",
                            lambda e: self._q_canvas.itemconfig(self._q_win, width=e.width))
        self._q_canvas.bind("<MouseWheel>",
                            lambda e: self._q_canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        tk.Label(self._q_frame, text="No jobs queued", font=("Segoe UI", 9),
                 bg=SURFACE, fg=FG_MUTED, pady=16).pack()

        st.configure("D.Horizontal.TProgressbar",
                     background=ACCENT, troughcolor=INPUT_BG, borderwidth=0)
        self._prog_var = tk.DoubleVar()
        self._prog = ttk.Progressbar(outer, variable=self._prog_var, maximum=100,
                                     mode="indeterminate", style="D.Horizontal.TProgressbar")
        self._prog.pack(fill="x", pady=(0, 6))

        tk.Label(outer, text="Log", font=("Segoe UI", 9),
                 bg=BG, fg=FG_MUTED).pack(anchor="w")
        log_frame = tk.Frame(outer, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        log_frame.pack(fill="both", expand=True, pady=(2, 0))

        self._log = tk.Text(
            log_frame, font=("Consolas", 9), bg=INPUT_BG, fg=FG,
            insertbackground=FG, relief="flat", bd=0, wrap="word", state="disabled",
        )
        log_sb = tk.Scrollbar(log_frame, orient="vertical", command=self._log.yview)
        self._log.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        self._log.tag_configure("ok",    foreground=SUCCESS)
        self._log.tag_configure("done",  foreground=SUCCESS, font=("Consolas", 9, "bold"))
        self._log.tag_configure("warn",  foreground=WARNING)
        self._log.tag_configure("err",   foreground=ERR)
        self._log.tag_configure("muted", foreground=FG_MUTED)
        self._log.tag_configure("norm",  foreground=FG)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self._outdir_var.get() or os.path.expanduser("~"))
        if d:
            self._outdir_var.set(d)
            self._cfg["output_dir"] = d
            self._save_settings()

    def _check_resume(self):
        if self._resume_var.get():
            folder = self._folder_var.get().strip()
            outdir = self._outdir_var.get().strip()
            if folder and outdir and not os.path.isdir(os.path.join(outdir, folder)):
                self._resume_warn.configure(text="⚠ Folder not found — will be created as new")
                return
        self._resume_warn.configure(text="")

    def _add_to_queue(self):
        url    = self._url_var.get().strip()
        folder = self._folder_var.get().strip()
        outdir = self._outdir_var.get().strip()
        if not url:
            messagebox.showwarning("Missing input", "Series URL is required.")
            return
        if not folder:
            messagebox.showwarning("Missing input", "Series folder name is required.")
            return
        if not outdir:
            messagebox.showwarning("Missing input", "Output directory is required.")
            return
        browser = self._browser_var.get()
        self._cfg.update({"browser": browser, "output_dir": outdir})
        self._save_settings()
        self.jobs.append({
            "url": url, "folder": folder, "outdir": outdir,
            "browser": browser, "resume": self._resume_var.get(),
            "status": "Waiting",
        })
        self._url_var.set("")
        self._folder_var.set("")
        self._resume_warn.configure(text="")
        self._refresh_queue()

    def _refresh_queue(self):
        for w in self._q_frame.winfo_children():
            w.destroy()
        if not self.jobs:
            tk.Label(self._q_frame, text="No jobs queued", font=("Segoe UI", 9),
                     bg=SURFACE, fg=FG_MUTED, pady=16).pack()
            return
        for i, job in enumerate(self.jobs):
            self._build_row(i, job)

    def _build_row(self, idx, job):
        active = (idx == self._active_idx)
        row_bg = ACTIVE_BG if active else (SURFACE if idx % 2 == 0 else "#1e1e1e")
        fg_c   = FG_MUTED if job["status"] in ("Done", "Cancelled", "Failed") else FG

        row = tk.Frame(self._q_frame, bg=row_bg)
        row.pack(fill="x", padx=2, pady=1)

        info = tk.Frame(row, bg=row_bg)
        info.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=4)
        tk.Label(info, text=job["folder"], font=("Segoe UI", 10),
                 bg=row_bg, fg=fg_c, anchor="w").pack(anchor="w")
        url = job["url"]
        tk.Label(info, text=(url if len(url) <= 52 else url[:49] + "…"),
                 font=("Segoe UI", 8), bg=row_bg, fg=FG_MUTED, anchor="w").pack(anchor="w")

        right = tk.Frame(row, bg=row_bg)
        right.pack(side="right", padx=6, pady=4)
        tk.Label(right, text=job["status"], font=("Segoe UI", 8, "bold"),
                 bg=row_bg, fg=STATUS_COLORS.get(job["status"], FG_MUTED)).pack(anchor="e")
        if job["status"] == "Waiting":
            tk.Button(right, text="✕ Remove", font=("Segoe UI", 8),
                      bg=row_bg, fg=ERR, activebackground=row_bg, activeforeground=ERR,
                      relief="flat", bd=0, cursor="hand2",
                      command=lambda i=idx: self._remove_job(i)).pack(anchor="e")

    def _remove_job(self, idx):
        if 0 <= idx < len(self.jobs) and self.jobs[idx]["status"] == "Waiting":
            self.jobs.pop(idx)
            self._refresh_queue()

    def _toggle_queue(self):
        if self._running:
            self._stop_req = True
            self._start_btn.configure(text="Stopping…", state="disabled")
        else:
            if not any(j["status"] == "Waiting" for j in self.jobs):
                return
            self._running  = True
            self._stop_req = False
            self._start_btn.configure(text="Stop", bg=ERR, state="normal")
            self._hover(self._start_btn, ERR, "#dc2626")
            self._prog.configure(mode="indeterminate")
            self._prog.start(10)
            self._run_next()

    def _run_next(self):
        if self._stop_req:
            self._reset_ui()
            return
        waiting = [i for i, j in enumerate(self.jobs) if j["status"] == "Waiting"]
        if not waiting:
            self._reset_ui()
            return
        idx = waiting[0]
        self._active_idx = idx
        self._refresh_queue()
        self._clear_log()
        threading.Thread(target=self._run_job, args=(idx,), daemon=True).start()

    def _reset_ui(self):
        self._running    = False
        self._stop_req   = False
        self._active_idx = None
        self._start_btn.configure(text="Start Queue", bg=ACCENT, state="normal")
        self._hover(self._start_btn, ACCENT, ACCENT_H)
        self._prog.stop()
        self._prog.configure(mode="determinate")
        self._prog_var.set(0)
        self._refresh_queue()

    def _run_job(self, idx):
        job = self.jobs[idx]
        try:
            self._set_status(idx, "Downloading")
            ok = self._step_download(job)
            if self._stop_req:
                self._set_status(idx, "Cancelled")
                return
            if not ok:
                self._set_status(idx, "Failed")
                return
            self._set_status(idx, "Converting")
            count = self._step_convert(job)
            if self._stop_req:
                self._set_status(idx, "Cancelled")
                return
            self._step_cleanup(job)
            self._emit(f"✔ Done! {count} chapter(s) converted.", "done")
            self._set_status(idx, "Done")
        except Exception as exc:
            self._emit(f"✗ Unexpected error: {exc}", "err")
            self._set_status(idx, "Failed" if not self._stop_req else "Cancelled")
        finally:
            self._ui_q.put(("next", None))

    @staticmethod
    def _find_gdl():
        if getattr(sys, "frozen", False):
            return [sys.executable, "--_gdl"]

        for py in ("python3.13", "python3.12", "python3.11", "python3", "python", "py"):
            try:
                r = subprocess.run(
                    [py, "-m", "gallery_dl", "--version"],
                    capture_output=True, timeout=8,
                )
                if r.returncode == 0:
                    return [py, "-m", "gallery_dl"]
            except (FileNotFoundError, OSError):
                pass

        return None

    def _step_download(self, job) -> bool:
        conf = {
            "extractor": {
                "skip": True,
                "retries": 3,
                "retry-codes": [429, 500, 502, 503],
                "sleep-request": 0.1,
                "workers": 8,
            }
        }
        fd, conf_path = tempfile.mkstemp(suffix=".json", prefix="gdl_")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(conf, f)

            raw_dir = os.path.join(job["outdir"], job["folder"], "raw")
            os.makedirs(raw_dir, exist_ok=True)

            base_cmd = self._find_gdl()
            if base_cmd is None:
                self._emit(
                    "✗ gallery-dl not found. Open a terminal and run:\n"
                    "    pip install gallery-dl\n"
                    "Then restart the app.", "err"
                )
                return False

            cmd = base_cmd + [
                "--config", conf_path,
                "--dest", raw_dir,
            ]
            if job["browser"] != "None (no cookies)":
                cmd += ["--cookies-from-browser", job["browser"].lower()]
            cmd.append(job["url"])

            self._emit(f"▶ Downloading: {job['url']}", "norm")

            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            proc  = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", creationflags=flags,
            )
            self._cur_proc = proc

            for raw_line in proc.stdout:
                line = raw_line.rstrip()
                if not line:
                    continue
                if self._stop_req:
                    proc.terminate()
                    break
                ll = line.lower()
                if "cookie" in ll and any(w in ll for w in ("error", "fail", "unable", "cannot")):
                    self._emit(
                        f'⚠ Could not read cookies from {job["browser"]}. '
                        'Try a different browser or "None (no cookies)".', "warn"
                    )
                else:
                    self._emit(line, "norm")

            proc.wait()
            self._cur_proc = None
            if self._stop_req:
                return False
            if proc.returncode != 0:
                self._emit(f"✗ gallery-dl exited with code {proc.returncode}", "err")
                return False
            return True
        finally:
            try:
                os.unlink(conf_path)
            except Exception:
                pass

    def _step_convert(self, job) -> int:
        try:
            import img2pdf
            from PIL import Image as PILImg
        except ImportError:
            self._emit("✗ img2pdf or Pillow not installed. Run install.bat.", "err")
            return 0

        raw_dir = os.path.join(job["outdir"], job["folder"], "raw")
        out_dir = os.path.join(job["outdir"], job["folder"])
        os.makedirs(out_dir, exist_ok=True)

        if not os.path.isdir(raw_dir):
            self._emit("⚠ raw/ not found — nothing to convert", "warn")
            return 0

        chapter_map = {}
        for root, dirs, files in os.walk(raw_dir):
            imgs = sorted(f for f in files if _is_image(os.path.join(root, f)))
            if imgs:
                rel = os.path.relpath(root, raw_dir)
                chapter_map[rel] = (root, imgs)

        chapters = sorted(chapter_map)
        if not chapters:
            self._emit("⚠ No chapter folders found in raw/", "warn")
            return 0

        count = 0
        for ch in chapters:
            if self._stop_req:
                break
            ch_path, imgs = chapter_map[ch]
            ch_label = os.path.basename(ch)
            pdf_name = chapter_pdf_name(ch_label)
            pdf_path = os.path.join(out_dir, pdf_name)

            if job["resume"] and os.path.exists(pdf_path):
                self._emit(f"⭭ Skipped (already exists): {pdf_name}", "muted")
                continue

            try:
                pages = []
                for img_file in imgs:
                    img_path = os.path.join(ch_path, img_file)
                    with open(img_path, "rb") as f:
                        data = f.read()
                    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                        with PILImg.open(io.BytesIO(data)) as im:
                            buf = io.BytesIO()
                            im.convert("RGB").save(buf, format="JPEG", quality=95)
                            pages.append(buf.getvalue())
                    else:
                        pages.append(data)

                with open(pdf_path, "wb") as f:
                    f.write(img2pdf.convert(pages))

                self._emit(f"✓ {pdf_name}", "ok")
                count += 1
            except Exception as exc:
                self._emit(f"✗ Failed to convert {ch_label}: {exc}", "err")

        return count

    def _step_cleanup(self, job):
        raw_dir = os.path.join(job["outdir"], job["folder"], "raw")
        if os.path.isdir(raw_dir):
            try:
                shutil.rmtree(raw_dir)
                self._emit("Cleaned up raw/ folder.", "muted")
            except Exception as exc:
                self._emit(f"⚠ Could not delete raw/: {exc}", "warn")

    def _set_status(self, idx, status):
        self._ui_q.put(("status", (idx, status)))

    def _emit(self, msg, tag="norm"):
        self._ui_q.put(("log", (msg, tag)))

    def _poll_ui(self):
        try:
            while True:
                kind, data = self._ui_q.get_nowait()
                if kind == "log":
                    msg, tag = data
                    self._log.configure(state="normal")
                    self._log.insert("end", msg + "\n", tag)
                    self._log.see("end")
                    self._log.configure(state="disabled")
                elif kind == "status":
                    idx, status = data
                    self.jobs[idx]["status"] = status
                    self._refresh_queue()
                elif kind == "next":
                    if self._stop_req:
                        self._reset_ui()
                    else:
                        self._run_next()
        except q_mod.Empty:
            pass
        self.after(50, self._poll_ui)

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _on_close(self):
        if self._running:
            self._stop_req = True
            if self._cur_proc:
                try:
                    self._cur_proc.terminate()
                except Exception:
                    pass
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
