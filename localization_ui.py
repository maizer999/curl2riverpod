import json
import os
import re
import ssl
import threading
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox

API_URL = (
    "https://qapigw.tabadul.sa/tabadul/pmis2/mobileapi/lookupmaster/localization/"
    "locale-map?module=ALTCNF%2CCCM%2CDMR%2CDMRG%2CDRPT%2CExceptionMessages%2CGENERAL"
    "%2CLKP%2CMENU%2CRPA%2CTP%2CT_P%2CUSRMGMT%2CVCOM%2CVVM%2CV_I"
)
PROJECT_ROOT = os.path.expanduser("/Users/mohammadabumaizer/Documents/pmis-flutter")
BASE_URL_PREFIX = "https://qapigw.tabadul.sa/tabadul/pmis2"


def clean_string(s):
    return re.sub(r'[^a-zA-Z0-9]', '', str(s)).lower()


def to_camel_case(s):
    s = re.sub(r'[^a-zA-Z0-9 ]', ' ', s)
    words = s.split()
    if not words:
        return "emptyKey"
    camel = words[0].lower() + "".join(w.capitalize() for w in words[1:])
    if camel.endswith("id") and len(camel) > 2:
        camel = camel[:-2] + "Id"
    elif camel.endswith("rid") and len(camel) > 3:
        camel = camel[:-3] + "Rid"
    elif camel.endswith("no") and len(camel) > 2:
        camel = camel[:-2] + "No"
    return camel


def fetch_localization_map():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        API_URL,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    with urllib.request.urlopen(req, context=ctx) as response:
        return json.loads(response.read().decode('utf-8'))


def flatten_map(json_data):
    flat = {}

    def walk(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, (dict, list)):
                    walk(v)
                else:
                    flat[k] = v
        elif isinstance(d, list):
            for item in d:
                walk(item)

    walk(json_data)
    return flat


def find_ui_candidates():
    candidates = []
    lib_dir = os.path.join(PROJECT_ROOT, 'lib')
    if not os.path.isdir(lib_dir):
        return candidates
    for root, _, files in os.walk(lib_dir):
        for fname in files:
            if not fname.endswith('.dart'):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                if re.search(r'title:\s*"', content):
                    candidates.append(path)
            except Exception:
                continue
    return candidates


ENDPOINT_RE = re.compile(
    r"""endpoint\s*:\s*['"](https?://[^'"]+)['"]""", re.IGNORECASE
)


def find_endpoint_files():
    results = []
    lib_dir = os.path.join(PROJECT_ROOT, 'lib')
    if not os.path.isdir(lib_dir):
        return results
    for root, _, files in os.walk(lib_dir):
        for fname in files:
            if not fname.endswith('.dart'):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    content = fh.read()
            except Exception:
                continue
            matches = ENDPOINT_RE.findall(content)
            if matches:
                results.append((path, matches))
    return results


def url_to_variable_name(url):
    path = url
    if BASE_URL_PREFIX and path.startswith(BASE_URL_PREFIX):
        path = path[len(BASE_URL_PREFIX):]
    path = path.split('?')[0].strip('/')
    segs = [s for s in re.split(r'[/_\-]+', path) if s]
    # Use last up to 4 segments to keep names readable but unique
    tail = segs[-4:] if len(segs) > 4 else segs
    if not tail:
        return "endpoint"
    name = tail[0].lower() + "".join(w.capitalize() for w in tail[1:])
    name = re.sub(r'[^a-zA-Z0-9]', '', name)
    if not name or not name[0].isalpha():
        name = "ep" + name
    return name


def generate_endpoint_block(url):
    suffix = url[len(BASE_URL_PREFIX):] if url.startswith(BASE_URL_PREFIX) else url
    if not suffix.startswith('/'):
        suffix = '/' + suffix
    return f'"$baseURL{suffix}"'


def generate_class_for_file(ui_path, flat_json, class_name):
    with open(ui_path, 'r', encoding='utf-8') as f:
        ui_code = f.read()
    titles = re.findall(r'title:\s*"([^"]+)"', ui_code)
    matched = {}
    for title in titles:
        normalized = clean_string(title)
        found = False
        for k, v in flat_json.items():
            if normalized == clean_string(k) or normalized == clean_string(v):
                matched[to_camel_case(k)] = v
                found = True
                break
        if not found:
            matched[to_camel_case(title)] = title

    buf = f"class {class_name} {{\n"
    for key, val in sorted(matched.items()):
        safe_val = str(val).replace('"', '\\"')
        buf += f'  static const String {key:<25} = "{safe_val}";\n'
    buf += "}\n"
    return buf, len(titles)


class LocalizationApp:
    def __init__(self, root):
        self.root = root
        root.title("Flutter Localization Generator")
        root.geometry("1400x800")
        root.configure(background="#1e1e1e")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # ── Tab 1: Generator ──────────────────────────────────────────────
        tab1 = ttk.Frame(self.notebook)
        self.notebook.add(tab1, text="  Generator  ")

        top = ttk.Frame(tab1, padding=10)
        top.pack(fill=tk.X)

        self.run_btn = ttk.Button(top, text="Generate All", command=self.start)
        self.run_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)

        # Search bar
        search_frame = ttk.Frame(tab1, padding=(10, 4))
        search_frame.pack(fill=tk.X)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._do_search())
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=35)
        self.search_entry.pack(side=tk.LEFT, padx=(4, 2))

        ttk.Button(search_frame, text="▲ Prev", command=lambda: self._jump(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="▼ Next", command=lambda: self._jump(1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(search_frame, text="Clear", command=self._clear_search).pack(side=tk.LEFT, padx=2)
        self.match_var = tk.StringVar(value="")
        ttk.Label(search_frame, textvariable=self.match_var, foreground="#555").pack(side=tk.LEFT, padx=8)

        self._match_ranges = []
        self._match_index = -1

        prog_frame = ttk.Frame(tab1, padding=(10, 0))
        prog_frame.pack(fill=tk.X)

        self.progress = ttk.Progressbar(prog_frame, mode='determinate', maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.percent_var = tk.StringVar(value="0%")
        ttk.Label(prog_frame, textvariable=self.percent_var, width=6).pack(side=tk.LEFT, padx=8)

        paned = tk.PanedWindow(tab1, orient=tk.HORIZONTAL, sashwidth=6,
                               sashrelief=tk.RAISED, background="#ccc")
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        # Left: output text
        left_frame = ttk.Frame(paned, padding=(4, 4, 0, 4))
        paned.add(left_frame, stretch="always", minsize=400)

        self.text = tk.Text(left_frame, wrap=tk.NONE, font=("Menlo", 12),
                            background="#1e1e1e", foreground="#d4d4d4",
                            insertbackground="#d4d4d4", selectbackground="#264f78")
        yscroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.text.yview)
        xscroll = ttk.Scrollbar(left_frame, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.text.tag_configure("header", foreground="#569cd6",
                                font=("Menlo", 13, "bold"))
        self.text.tag_configure("info", foreground="#888")
        self.text.tag_configure("search_match", background="#5a4a00", foreground="#ffd54f")
        self.text.tag_configure("search_current", background="#ff8f00", foreground="#000")

        # Right: notes panel
        right_frame = ttk.Frame(paned, padding=(0, 4, 4, 4))
        paned.add(right_frame, stretch="never", minsize=280, width=350)

        notes_header = ttk.Frame(right_frame)
        notes_header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(notes_header, text="Notes", font=("Menlo", 12, "bold")).pack(side=tk.LEFT)
        ttk.Button(notes_header, text="Clear", command=lambda: self.notes.delete("1.0", tk.END)).pack(side=tk.RIGHT)

        self.notes = tk.Text(right_frame, wrap=tk.WORD, font=("Menlo", 12),
                             background="#252526", foreground="#d4d4d4",
                             insertbackground="#d4d4d4", selectbackground="#264f78",
                             relief=tk.FLAT, borderwidth=1)
        notes_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.notes.yview)
        self.notes.configure(yscrollcommand=notes_scroll.set)
        notes_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.notes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Tab 2: String Lookup ──────────────────────────────────────────
        tab2 = ttk.Frame(self.notebook)
        self.notebook.add(tab2, text="  String Lookup  ")
        self._build_lookup_tab(tab2)

    def _build_lookup_tab(self, parent):
        controls = ttk.Frame(parent, padding=12)
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="URL:").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.lookup_url_var = tk.StringVar(value=API_URL)
        ttk.Entry(controls, textvariable=self.lookup_url_var, width=90).grid(
            row=0, column=1, sticky=tk.EW, padx=(6, 0), pady=4)

        ttk.Label(controls, text="Search:").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.lookup_query_var = tk.StringVar()
        query_entry = ttk.Entry(controls, textvariable=self.lookup_query_var, width=50)
        query_entry.grid(row=1, column=1, sticky=tk.W, padx=(6, 0), pady=4)
        query_entry.bind("<Return>", lambda _: self._run_lookup())

        btn_row = ttk.Frame(controls)
        btn_row.grid(row=2, column=1, sticky=tk.W, padx=(6, 0), pady=6)
        self.lookup_btn = ttk.Button(btn_row, text="Search", command=self._run_lookup)
        self.lookup_btn.pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Clear", command=self._clear_lookup).pack(side=tk.LEFT, padx=6)
        self.lookup_status_var = tk.StringVar(value="")
        ttk.Label(btn_row, textvariable=self.lookup_status_var, foreground="#888").pack(side=tk.LEFT)

        controls.columnconfigure(1, weight=1)

        self.lookup_text = tk.Text(parent, wrap=tk.NONE, font=("Menlo", 12),
                                   background="#1e1e1e", foreground="#d4d4d4",
                                   insertbackground="#d4d4d4", selectbackground="#264f78")
        lscroll_y = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.lookup_text.yview)
        lscroll_x = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=self.lookup_text.xview)
        self.lookup_text.configure(yscrollcommand=lscroll_y.set, xscrollcommand=lscroll_x.set)
        lscroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        lscroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.lookup_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self.lookup_text.tag_configure("hit", foreground="#4ec9b0")
        self.lookup_text.tag_configure("info", foreground="#888")

    def _run_lookup(self):
        url = self.lookup_url_var.get().strip()
        query = self.lookup_query_var.get().strip()
        if not url or not query:
            return
        self.lookup_btn.config(state=tk.DISABLED)
        self.lookup_status_var.set("Fetching...")
        self.lookup_text.delete("1.0", tk.END)
        threading.Thread(target=self._do_lookup, args=(url, query), daemon=True).start()

    def _do_lookup(self, url, query):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, context=ctx) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            flat = flatten_map(data)
            q = query.lower()
            hits = {k: v for k, v in flat.items()
                    if q in str(k).lower() or q in str(v).lower()}
            self.root.after(0, self._show_lookup_results, hits, query)
        except Exception as e:
            self.root.after(0, lambda: self.lookup_status_var.set(f"Error: {e}"))
            self.root.after(0, lambda: self.lookup_btn.config(state=tk.NORMAL))

    def _show_lookup_results(self, hits, query):
        self.lookup_text.delete("1.0", tk.END)
        if not hits:
            self.lookup_text.insert(tk.END, f"// No matches for \"{query}\"\n", "info")
        else:
            self.lookup_text.insert(tk.END,
                f"// {len(hits)} result(s) for \"{query}\"\n\n", "info")
            for k, v in sorted(hits.items()):
                safe_v = str(v).replace('"', '\\"')
                line = f'  static const String {to_camel_case(k):<25} = "{safe_v}";\n'
                self.lookup_text.insert(tk.END, line, "hit")
        self.lookup_status_var.set(f"{len(hits)} result(s)")
        self.lookup_btn.config(state=tk.NORMAL)

    def _clear_lookup(self):
        self.lookup_text.delete("1.0", tk.END)
        self.lookup_query_var.set("")
        self.lookup_status_var.set("")

    def _do_search(self):
        query = self.search_var.get()
        self.text.tag_remove("search_match", "1.0", tk.END)
        self.text.tag_remove("search_current", "1.0", tk.END)
        self._match_ranges = []
        self._match_index = -1
        if not query:
            self.match_var.set("")
            return
        start = "1.0"
        while True:
            pos = self.text.search(query, start, stopindex=tk.END, nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self._match_ranges.append((pos, end))
            self.text.tag_add("search_match", pos, end)
            start = end
        count = len(self._match_ranges)
        self.match_var.set(f"{count} match{'es' if count != 1 else ''}" if count else "No matches")
        if count:
            self._match_index = 0
            self._highlight_current()

    def _jump(self, direction):
        if not self._match_ranges:
            return
        self._match_index = (self._match_index + direction) % len(self._match_ranges)
        self._highlight_current()

    def _highlight_current(self):
        self.text.tag_remove("search_current", "1.0", tk.END)
        if 0 <= self._match_index < len(self._match_ranges):
            pos, end = self._match_ranges[self._match_index]
            self.text.tag_add("search_current", pos, end)
            self.text.see(pos)
            total = len(self._match_ranges)
            self.match_var.set(f"{self._match_index + 1}/{total} match{'es' if total != 1 else ''}")

    def _clear_search(self):
        self.search_var.set("")
        self.search_entry.focus()

    def set_progress(self, pct, status=None):
        pct = max(0, min(100, pct))
        self.progress['value'] = pct
        self.percent_var.set(f"{int(pct)}%")
        if status:
            self.status_var.set(status)
        self.root.update_idletasks()

    def append(self, text, tag=None):
        if tag:
            self.text.insert(tk.END, text, tag)
        else:
            self.text.insert(tk.END, text)
        self.text.see(tk.END)
        if self.search_var.get():
            self._do_search()
        self.root.update_idletasks()

    def start(self):
        self.run_btn.config(state=tk.DISABLED)
        self.text.delete("1.0", tk.END)
        self.set_progress(0, "Starting...")
        threading.Thread(target=self._run_all, daemon=True).start()

    def _run_all(self):
        try:
            self._run_localizations(progress_start=0, progress_end=50)
            self.append("\n" + "=" * 80 + "\n\n", "info")
            self._run_endpoints_section(progress_start=50, progress_end=100)
            self.set_progress(100, "Done.")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.set_progress(0, "Failed")
        finally:
            self.run_btn.config(state=tk.NORMAL)

    def _run_endpoints_section(self, progress_start=50, progress_end=100):
        span = progress_end - progress_start
        self.set_progress(progress_start, "Scanning endpoints...")
        files = find_endpoint_files()
        if not files:
            self.append("No raw 'endpoint: \"https://...\"' usages found.\n", "info")
            self.set_progress(progress_end)
            return

        total = len(files)
        self.append(f"// === ENDPOINTS ({total} files) ===\n", "header")
        self.append(f"// Base URL stripped: {BASE_URL_PREFIX}\n\n", "info")

        global_seen = {}
        for i, (path, urls) in enumerate(files, 1):
            self.set_progress(
                progress_start + (i - 1) / total * span,
                f"Processing endpoints ({i}/{total}) {os.path.basename(path)}"
            )

            base = os.path.basename(path).replace('.dart', '')
            short = base.replace('_service', '').replace('_services', '').strip('_')
            class_name = ''.join(
                w.capitalize() for w in re.split(r'[^a-zA-Z0-9]', short) if w
            ) + 'Endpoints'

            self.append(f"// {path}\n", "header")
            self.append(f"class {class_name} {{\n")

            local_seen = {}
            for url in dict.fromkeys(urls):
                name = url_to_variable_name(url)
                candidate = name
                n = 2
                while candidate in local_seen and local_seen[candidate] != url:
                    candidate = f"{name}{n}"
                    n += 1
                local_seen[candidate] = url
                global_seen[candidate] = url

                value = generate_endpoint_block(url)
                self.append(f"  static String {candidate} = {value};\n")
            self.append("}\n\n")
            self.set_progress(progress_start + i / total * span)

    def _run_localizations(self, progress_start=0, progress_end=100):
        span = progress_end - progress_start
        self.set_progress(progress_start + 0.02 * span, "Downloading localization map...")
        data = fetch_localization_map()
        flat = flatten_map(data)
        self.set_progress(progress_start + 0.08 * span,
                          f"Downloaded {len(flat)} entries. Scanning UI files...")

        candidates = find_ui_candidates()
        if not candidates:
            self.append("No UI files with hardcoded 'title:' found.\n", "info")
            self.set_progress(progress_end)
            return

        total = len(candidates)
        self.append(f"// === LOCALIZATIONS ({total} files) ===\n\n", "header")

        for i, ui_path in enumerate(candidates, 1):
            base = os.path.basename(ui_path).replace('.dart', '')
            short = base.replace('_widget', '').replace('widget', '').strip('_')
            class_name = ''.join(
                w.capitalize() for w in re.split(r'[^a-zA-Z0-9]', short) if w
            ) + 'Local'

            self.set_progress(
                progress_start + (0.08 + (i - 1) / total * 0.92) * span,
                f"Processing localization ({i}/{total}) {os.path.basename(ui_path)}"
            )

            try:
                class_code, count = generate_class_for_file(ui_path, flat, class_name)
            except Exception as e:
                self.append(f"// ⚠️ Failed for {ui_path}: {e}\n\n", "info")
                continue

            self.append(f"// {ui_path}  ({count} titles)\n", "header")
            self.append(class_code + "\n")
            self.set_progress(progress_start + (0.08 + i / total * 0.92) * span)


if __name__ == "__main__":
    root = tk.Tk()
    LocalizationApp(root)
    root.mainloop()
