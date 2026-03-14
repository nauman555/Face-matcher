"""
Face Matcher — Desktop Application
=================================================================
Install dependencies:
    pip install "numpy<2.0" face-recognition Pillow

Run:
    python face_matcher_app.py
"""

import os
import sys
import json
import shutil
import threading
import multiprocessing
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from functools import partial

try:
    from PIL import Image, ImageTk, ImageDraw
    import numpy as np
    import face_recognition
except ImportError as e:
    root = tk.Tk(); root.withdraw()
    messagebox.showerror("Missing Dependency", f"{e}\n\nRun:\n  pip install \"numpy<2.0\" face-recognition Pillow")
    sys.exit(1)

# ─── Constants ────────────────────────────────────────────────────
SUPPORTED  = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
CACHE_FILE = "face_encodings_cache.json"
BG         = "#0f0f13"
BG2        = "#1a1a24"
BG3        = "#22223a"
ACCENT     = "#7c6af7"
ACCENT2    = "#a78bfa"
SUCCESS    = "#34d399"
WARNING    = "#fbbf24"
ERROR_C    = "#f87171"
TEXT       = "#f1f0ff"
TEXT2      = "#9894b8"
BORDER     = "#2e2b4a"
MAX_DIM    = 800   # resize large images to speed up detection


# ─── Image Utilities ──────────────────────────────────────────────
def load_image_safe(path: str):
    """Load and resize image — smaller = faster face detection."""
    try:
        pil = Image.open(path).convert("RGB")
        # Resize if too large — speeds up detection significantly
        w, h = pil.size
        if max(w, h) > MAX_DIM:
            scale = MAX_DIM / max(w, h)
            pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return np.ascontiguousarray(np.array(pil, dtype=np.uint8))
    except Exception:
        return None


def get_already_processed(output_folder: str) -> set:
    p = Path(output_folder)
    if not p.exists():
        return set()
    return {f.name for f in p.rglob("*") if f.suffix.lower() in SUPPORTED}


def make_thumbnail(path: str, size=(180, 180)):
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail(size, Image.LANCZOS)
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, img.size[0]-1, img.size[1]-1], radius=10, fill=255)
        result = Image.new("RGBA", img.size, (0, 0, 0, 0))
        result.paste(img, mask=mask)
        return ImageTk.PhotoImage(result)
    except Exception:
        return None


# ─── Encoding Cache ───────────────────────────────────────────────
def load_cache(search_folder: str) -> dict:
    """Load cached encodings from disk."""
    cache_path = Path(search_folder) / CACHE_FILE
    if cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(search_folder: str, cache: dict):
    """Save encodings cache to disk."""
    cache_path = Path(search_folder) / CACHE_FILE
    try:
        with open(cache_path, "w") as f:
            json.dump(cache, f)
    except Exception:
        pass


# ─── Worker Function (runs in separate process) ───────────────────
def process_image(img_path_str: str):
    """
    Process a single image — encode all faces found.
    Returns (path_str, list_of_encodings) or (path_str, None) on failure.
    Designed to run in a worker process.
    """
    try:
        from PIL import Image
        import numpy as np
        import face_recognition

        pil = Image.open(img_path_str).convert("RGB")
        w, h = pil.size
        if max(w, h) > MAX_DIM:
            scale = MAX_DIM / max(w, h)
            pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        img = np.ascontiguousarray(np.array(pil, dtype=np.uint8))
        locs = face_recognition.face_locations(img, model="hog")
        if not locs:
            return (img_path_str, [])
        encs = face_recognition.face_encodings(img, locs)
        return (img_path_str, [e.tolist() for e in encs])
    except Exception:
        return (img_path_str, None)


# ─── Main Application ─────────────────────────────────────────────
class FaceMatcherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Face Matcher")
        self.geometry("860x820")
        self.minsize(860, 820)
        self.configure(bg=BG)
        self.resizable(True, True)

        self.sample_path   = tk.StringVar()
        self.search_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.tolerance     = tk.DoubleVar(value=0.55)
        self.workers       = tk.IntVar(value=max(2, multiprocessing.cpu_count() - 1))
        self.running       = False
        self._thumb        = None

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        w, h = 860, 820
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI Builder ────────────────────────────────────────────────
    def _build_ui(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=30, pady=(24, 0))
        tk.Label(header, text="⬡  Face Matcher", font=("Segoe UI", 20, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(header, text="Facial Recognition · Image Sorter",
                 font=("Segoe UI", 10), bg=BG, fg=TEXT2).pack(side="left", padx=(12, 0), pady=(6, 0))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(14, 0))

        content = tk.Frame(self, bg=BG)
        content.pack(fill="both", expand=True, padx=30, pady=16)

        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(content, bg=BG, width=210)
        right.pack(side="right", fill="y", padx=(20, 0))
        right.pack_propagate(False)
        self._build_preview(right)

        self._build_path_row(left, "Sample Image",  self.sample_path,   self._browse_sample, "📷")
        self._build_path_row(left, "Search Folder", self.search_folder, self._browse_search, "📁")
        self._build_path_row(left, "Output Folder", self.output_folder, self._browse_output, "📂")
        self._build_tolerance(left)
        self._build_workers(left)
        self._build_buttons(left)
        self._build_progress(left)
        self._build_log(left)

    def _build_preview(self, parent):
        tk.Label(parent, text="Sample Preview", font=("Segoe UI", 10, "bold"),
                 bg=BG, fg=TEXT2).pack(anchor="w", pady=(0, 8))
        self.preview_frame = tk.Frame(parent, bg=BG3, width=190, height=190)
        self.preview_frame.pack()
        self.preview_frame.pack_propagate(False)
        self.preview_label = tk.Label(self.preview_frame, bg=BG3,
                                       text="No image\nselected",
                                       font=("Segoe UI", 9), fg=TEXT2)
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")

    def _build_path_row(self, parent, label, var, cmd, icon):
        frame = tk.Frame(parent, bg=BG2, padx=14, pady=10)
        frame.pack(fill="x", pady=(0, 8))
        frame.columnconfigure(1, weight=1)
        tk.Label(frame, text=icon, font=("Segoe UI", 13), bg=BG2, fg=ACCENT2).grid(row=0, column=0, padx=(0, 10))
        inner = tk.Frame(frame, bg=BG2)
        inner.grid(row=0, column=1, sticky="ew")
        inner.columnconfigure(0, weight=1)
        tk.Label(inner, text=label, font=("Segoe UI", 9, "bold"), bg=BG2, fg=TEXT2).grid(row=0, column=0, sticky="w")
        ef = tk.Frame(inner, bg=BORDER, padx=1, pady=1)
        ef.grid(row=1, column=0, sticky="ew", pady=(3, 0))
        tk.Entry(ef, textvariable=var, font=("Segoe UI", 9),
                 bg=BG3, fg=TEXT, bd=0, relief="flat",
                 insertbackground=ACCENT, highlightthickness=0).pack(fill="x", padx=6, pady=4)
        tk.Button(frame, text="Browse", font=("Segoe UI", 9, "bold"),
                  bg=ACCENT, fg="white", bd=0, relief="flat",
                  padx=14, pady=6, cursor="hand2",
                  activebackground=ACCENT2, activeforeground="white",
                  command=cmd).grid(row=0, column=2, padx=(10, 0))

    def _build_tolerance(self, parent):
        frame = tk.Frame(parent, bg=BG2, padx=14, pady=10)
        frame.pack(fill="x", pady=(0, 8))
        top = tk.Frame(frame, bg=BG2)
        top.pack(fill="x")
        tk.Label(top, text="🎯  Match Tolerance", font=("Segoe UI", 9, "bold"), bg=BG2, fg=TEXT2).pack(side="left")
        self.tol_label = tk.Label(top, text="0.55", font=("Segoe UI", 9, "bold"), bg=BG2, fg=ACCENT2)
        self.tol_label.pack(side="right")
        hint = tk.Frame(frame, bg=BG2)
        hint.pack(fill="x", pady=(2, 4))
        tk.Label(hint, text="Strict (0.40)", font=("Segoe UI", 8), bg=BG2, fg=TEXT2).pack(side="left")
        tk.Label(hint, text="Lenient (0.65)", font=("Segoe UI", 8), bg=BG2, fg=TEXT2).pack(side="right")
        tk.Scale(frame, from_=0.40, to=0.65, resolution=0.01,
                 orient="horizontal", variable=self.tolerance,
                 bg=BG2, fg=TEXT, troughcolor=BG3,
                 activebackground=ACCENT, highlightthickness=0,
                 showvalue=False, bd=0,
                 command=lambda v: self.tol_label.config(text=f"{float(v):.2f}")).pack(fill="x")

    def _build_workers(self, parent):
        frame = tk.Frame(parent, bg=BG2, padx=14, pady=10)
        frame.pack(fill="x", pady=(0, 8))
        top = tk.Frame(frame, bg=BG2)
        top.pack(fill="x")
        tk.Label(top, text="⚡  CPU Workers", font=("Segoe UI", 9, "bold"), bg=BG2, fg=TEXT2).pack(side="left")
        self.workers_label = tk.Label(top, text=str(self.workers.get()),
                                       font=("Segoe UI", 9, "bold"), bg=BG2, fg=ACCENT2)
        self.workers_label.pack(side="right")
        cpu_count = multiprocessing.cpu_count()
        tk.Label(frame, text=f"More workers = faster  (your CPU has {cpu_count} cores)",
                 font=("Segoe UI", 8), bg=BG2, fg=TEXT2).pack(anchor="w", pady=(2, 4))
        tk.Scale(frame, from_=1, to=cpu_count, resolution=1,
                 orient="horizontal", variable=self.workers,
                 bg=BG2, fg=TEXT, troughcolor=BG3,
                 activebackground=ACCENT, highlightthickness=0,
                 showvalue=False, bd=0,
                 command=lambda v: self.workers_label.config(text=str(int(float(v))))).pack(fill="x")

    def _build_buttons(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", pady=(4, 8))
        self.run_btn = tk.Button(frame, text="▶   Start Matching",
                                  font=("Segoe UI", 11, "bold"),
                                  bg=ACCENT, fg="white", bd=0, relief="flat",
                                  padx=28, pady=11, cursor="hand2",
                                  activebackground=ACCENT2, activeforeground="white",
                                  command=self._start)
        self.run_btn.pack(side="left")

        self.cache_btn = tk.Button(frame, text="🗑  Clear Cache",
                                    font=("Segoe UI", 10), bg=BG3, fg=TEXT2, bd=0, relief="flat",
                                    padx=18, pady=11, cursor="hand2",
                                    activebackground=BORDER, activeforeground=TEXT,
                                    command=self._clear_cache)
        self.cache_btn.pack(side="left", padx=(8, 0))

        tk.Button(frame, text="Clear Log",
                  font=("Segoe UI", 10), bg=BG3, fg=TEXT2, bd=0, relief="flat",
                  padx=18, pady=11, cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=self._clear_log).pack(side="left", padx=(8, 0))

        tk.Button(frame, text="📂  Open Output",
                  font=("Segoe UI", 10), bg=BG3, fg=TEXT2, bd=0, relief="flat",
                  padx=18, pady=11, cursor="hand2",
                  activebackground=BORDER, activeforeground=TEXT,
                  command=self._open_output).pack(side="right")

    def _build_progress(self, parent):
        pf = tk.Frame(parent, bg=BG)
        pf.pack(fill="x", pady=(0, 4))
        self.progress_bar_bg = tk.Frame(pf, bg=BG3, height=6)
        self.progress_bar_bg.pack(fill="x")
        self.progress_bar = tk.Frame(self.progress_bar_bg, bg=ACCENT, height=6)
        self.progress_bar.place(x=0, y=0, relheight=1, width=0)
        self.status_label = tk.Label(pf, text="Ready", font=("Segoe UI", 9), bg=BG, fg=TEXT2)
        self.status_label.pack(anchor="w", pady=(3, 0))

    def _build_log(self, parent):
        frame = tk.Frame(parent, bg=BG2, padx=2, pady=2)
        frame.pack(fill="both", expand=True)
        self.log = tk.Text(frame, font=("Consolas", 9), bg=BG2, fg=TEXT2,
                            bd=0, relief="flat", wrap="word",
                            insertbackground=ACCENT, state="disabled",
                            highlightthickness=0, pady=8, padx=10)
        scroll = tk.Scrollbar(frame, command=self.log.yview, bg=BG2,
                               troughcolor=BG2, bd=0, relief="flat")
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("match",   foreground=SUCCESS)
        self.log.tag_config("skip",    foreground=WARNING)
        self.log.tag_config("error",   foreground=ERROR_C)
        self.log.tag_config("info",    foreground=TEXT2)
        self.log.tag_config("heading", foreground=ACCENT2, font=("Consolas", 9, "bold"))

    # ── Handlers ──────────────────────────────────────────────────
    def _browse_sample(self):
        path = filedialog.askopenfilename(
            title="Select Sample Image",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"), ("All Files", "*.*")])
        if path:
            self.sample_path.set(path)
            thumb = make_thumbnail(path)
            if thumb:
                self._thumb = thumb
                self.preview_label.config(image=thumb, text="")

    def _browse_search(self):
        path = filedialog.askdirectory(title="Select Search Folder")
        if path: self.search_folder.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path: self.output_folder.set(path)

    def _open_output(self):
        path = self.output_folder.get()
        if path and os.path.isdir(path):
            os.startfile(path)
        else:
            messagebox.showwarning("No Output", "Output folder not set or doesn't exist yet.")

    def _clear_cache(self):
        search = self.search_folder.get()
        if not search:
            messagebox.showwarning("No Folder", "Select a search folder first.")
            return
        cache_path = Path(search) / CACHE_FILE
        if cache_path.exists():
            cache_path.unlink()
            self._log("  Cache cleared. Next run will re-encode all images.", "skip")
        else:
            self._log("  No cache found.", "info")

    def _log(self, msg, tag="info"):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_status(self, msg, color=TEXT2):
        self.status_label.config(text=msg, fg=color)

    def _set_progress(self, pct):
        self.progress_bar_bg.update_idletasks()
        w = self.progress_bar_bg.winfo_width()
        self.progress_bar.place(x=0, y=0, relheight=1, width=int(w * pct))

    def _validate(self):
        if not self.sample_path.get() or not os.path.isfile(self.sample_path.get()):
            messagebox.showerror("Missing", "Please select a valid sample image."); return False
        if not self.search_folder.get() or not os.path.isdir(self.search_folder.get()):
            messagebox.showerror("Missing", "Please select a valid search folder."); return False
        if not self.output_folder.get():
            messagebox.showerror("Missing", "Please select an output folder."); return False
        return True

    def _start(self):
        if self.running: return
        if not self._validate(): return
        self.running = True
        self.run_btn.config(text="⏳  Processing...", state="disabled", bg=BG3)
        self._clear_log()
        self._set_progress(0)
        threading.Thread(target=self._run_matching, daemon=True).start()

    def _finish(self, matched, total, skipped, cached):
        self.running = False
        self.run_btn.config(text="▶   Start Matching", state="normal", bg=ACCENT)
        self._set_progress(1.0)
        self._set_status(
            f"Done — {matched} match(es) · {total} total · {cached} from cache · {skipped} skipped",
            SUCCESS
        )

    # ── Core Matching ─────────────────────────────────────────────
    def _run_matching(self):
        sample  = self.sample_path.get()
        search  = self.search_folder.get()
        output  = self.output_folder.get()
        tol     = self.tolerance.get()
        n_workers = self.workers.get()

        self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "heading")
        self._log(f"  Sample    : {sample}", "heading")
        self._log(f"  Search    : {search}", "heading")
        self._log(f"  Output    : {output}", "heading")
        self._log(f"  Tolerance : {tol:.2f}  |  Workers: {n_workers}", "heading")
        self._log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n", "heading")

        # ── Encode sample ──────────────────────────────────────────
        self._set_status("Encoding sample face...", ACCENT2)
        try:
            img = load_image_safe(sample)
            if img is None: raise ValueError("Could not load sample image.")
            locs = face_recognition.face_locations(img, model="hog")
            if not locs: raise ValueError("No face detected in sample image.")
            if len(locs) > 1:
                locs = [max(locs, key=lambda l: (l[2]-l[0]) * abs(l[1]-l[3]))]
            encs = face_recognition.face_encodings(img, locs)
            if not encs: raise ValueError("Could not encode face.")
            sample_enc = encs[0]
            self._log("  ✔ Sample face encoded.\n", "match")
        except Exception as e:
            self._log(f"  ✘ Error: {e}", "error")
            self._set_status(f"Error: {e}", ERROR_C)
            self.running = False
            self.run_btn.config(text="▶   Start Matching", state="normal", bg=ACCENT)
            return

        # ── Load cache & find new images ───────────────────────────
        cache    = load_cache(search)
        already  = get_already_processed(output)
        all_imgs = [p for p in Path(search).rglob("*") if p.suffix.lower() in SUPPORTED]
        new_imgs = [p for p in all_imgs if p.name not in already]
        skipped  = len(all_imgs) - len(new_imgs)
        total    = len(all_imgs)

        # Split into cached and uncached
        to_encode = [p for p in new_imgs if str(p) not in cache]
        cached_imgs = [p for p in new_imgs if str(p) in cache]
        cached_count = len(cached_imgs)

        if skipped:
            self._log(f"  Skipping {skipped} already copied image(s).", "skip")
        if cached_count:
            self._log(f"  Using cached encodings for {cached_count} image(s).", "skip")
        if to_encode:
            self._log(f"  Encoding {len(to_encode)} new image(s) using {n_workers} CPU workers...\n", "info")

        # ── Multiprocessing encode new images ──────────────────────
        if to_encode:
            paths_str = [str(p) for p in to_encode]
            with multiprocessing.Pool(processes=n_workers) as pool:
                for i, (path_str, encodings) in enumerate(
                    pool.imap_unordered(process_image, paths_str, chunksize=10)
                ):
                    pct = (i + 1) / len(to_encode) * 0.8
                    self._set_progress(pct)
                    self._set_status(f"Encoding {i+1}/{len(to_encode)}: {Path(path_str).name}", ACCENT2)
                    if encodings is not None:
                        cache[path_str] = encodings

            # Save updated cache
            save_cache(search, cache)
            self._log(f"  ✔ Encoding complete. Cache saved.\n", "match")

        # ── Match against sample ───────────────────────────────────
        self._log("Comparing faces against sample...\n", "info")
        self._set_status("Comparing faces...", ACCENT2)
        matches = []

        for i, img_path in enumerate(new_imgs):
            encodings = cache.get(str(img_path), [])
            if not encodings:
                continue
            enc_arrays = [np.array(e) for e in encodings]
            results = face_recognition.compare_faces(enc_arrays, sample_enc, tolerance=tol)
            if any(results):
                matches.append(img_path)
                self._log(f"  ✔ MATCH  →  {img_path.name}", "match")

        self._set_progress(0.95)

        # ── Copy matches ───────────────────────────────────────────
        if matches:
            self._log(f"\nCopying {len(matches)} matched image(s)...", "info")
            Path(output).mkdir(parents=True, exist_ok=True)
            for src in matches:
                try:
                    dest = Path(output) / src.relative_to(Path(search))
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        shutil.copy2(src, dest)
                        self._log(f"  Saved: {src.name}", "info")
                    else:
                        self._log(f"  Already exists: {src.name}", "skip")
                except Exception as e:
                    self._log(f"  Error copying {src.name}: {e}", "error")
        else:
            self._log("\n  No matching faces found.", "skip")

        self._log(f"\n━━━  Done! {len(matches)} match(es) from {total} image(s)  ━━━", "heading")
        self.after(0, lambda: self._finish(len(matches), total, skipped, cached_count))


# ─── Entry Point ──────────────────────────────────────────────────
if __name__ == "__main__":
    multiprocessing.freeze_support()   # Required for PyInstaller --onefile
    app = FaceMatcherApp()
    app.mainloop()
