"""
Professional UI for Slab System Design
Clean, modern design following UI/UX best practices
Includes visual plan view of slab layout
"""
import tkinter as tk
from tkinter import ttk, messagebox

from system_solver import SlabSystem
from models import InputData
from core import choose_single_layer_rebar, calc_K_and_As_from_M
from diagrams_cad import generate_system_dxf


class SlabDesignUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Döşeme Sistemi Tasarımı")
        self.root.geometry("1300x950")
        self.root.minsize(1150, 800)
        
        # Data
        self.slabs = {}
        self.connections = []
        self.slab_counter = 1
        
        # Design tokens
        self.theme = {
            "bg": "#f8fafc",
            "surface": "#ffffff",
            "surface_alt": "#f1f5f9",
            "primary": "#3b82f6",
            "primary_hover": "#2563eb",
            "success": "#22c55e",
            "danger": "#ef4444",
            "warning": "#f59e0b",
            "text": "#0f172a",
            "text_secondary": "#64748b",
            "text_muted": "#94a3b8",
            "border": "#e2e8f0",
            "border_focus": "#3b82f6",
            
            "font_xl": ("Segoe UI", 18, "bold"),
            "font_lg": ("Segoe UI", 13, "bold"),
            "font_md": ("Segoe UI", 11),
            "font_sm": ("Segoe UI", 10),
            "font_xs": ("Segoe UI", 9),
            
            "pad_xl": 24,
            "pad_lg": 16,
            "pad_md": 12,
            "pad_sm": 8,
            "pad_xs": 4,
        }
        
        self.root.configure(bg=self.theme["bg"])
        self.configure_styles()
        self.create_layout()
        self.load_defaults()
    
    def configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        t = self.theme
        
        style.configure("TFrame", background=t["bg"])
        style.configure("Card.TFrame", background=t["surface"])
        style.configure("TLabel", background=t["surface"], foreground=t["text"], font=t["font_sm"])
        style.configure("Title.TLabel", background=t["bg"], foreground=t["text"], font=t["font_xl"])
        style.configure("Subtitle.TLabel", background=t["surface"], foreground=t["text"], font=t["font_lg"])
        style.configure("Secondary.TLabel", background=t["surface"], foreground=t["text_secondary"], font=t["font_xs"])
        
        style.configure("TNotebook", background=t["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=t["surface_alt"], foreground=t["text_secondary"],
                       padding=(20, 10), font=t["font_sm"])
        style.map("TNotebook.Tab", background=[("selected", t["surface"])],
                 foreground=[("selected", t["primary"])])
        
        style.configure("Treeview", background=t["surface"], foreground=t["text"],
                       fieldbackground=t["surface"], rowheight=32, font=t["font_sm"])
        style.configure("Treeview.Heading", background=t["surface_alt"],
                       foreground=t["text"], font=t["font_sm"], padding=8)
        style.map("Treeview", background=[("selected", "#dbeafe")],
                 foreground=[("selected", t["primary"])])
    
    def create_button(self, parent, text, command, style="primary", size="md"):
        t = self.theme
        styles = {
            "primary": {"bg": t["primary"], "fg": "white", "hover": t["primary_hover"]},
            "success": {"bg": t["success"], "fg": "white", "hover": "#16a34a"},
            "danger": {"bg": t["danger"], "fg": "white", "hover": "#dc2626"},
            "ghost": {"bg": t["surface"], "fg": t["text_secondary"], "hover": t["surface_alt"]},
        }
        sizes = {
            "sm": {"font": t["font_xs"], "padx": 12, "pady": 6},
            "md": {"font": t["font_sm"], "padx": 16, "pady": 8},
            "lg": {"font": t["font_md"], "padx": 24, "pady": 12},
        }
        s, sz = styles[style], sizes[size]
        
        btn = tk.Button(parent, text=text, font=sz["font"], bg=s["bg"], fg=s["fg"],
                       activebackground=s["hover"], activeforeground=s["fg"],
                       relief=tk.FLAT, cursor="hand2", bd=0,
                       padx=sz["padx"], pady=sz["pady"], command=command)
        btn.bind("<Enter>", lambda e: btn.config(bg=s["hover"]))
        btn.bind("<Leave>", lambda e: btn.config(bg=s["bg"]))
        return btn
    
    def create_card(self, parent, title=None, subtitle=None):
        t = self.theme
        card = tk.Frame(parent, bg=t["surface"], highlightbackground=t["border"], highlightthickness=1)
        if title:
            header = tk.Frame(card, bg=t["surface"])
            header.pack(fill=tk.X, padx=t["pad_lg"], pady=(t["pad_lg"], t["pad_sm"]))
            tk.Label(header, text=title, font=t["font_lg"], bg=t["surface"], fg=t["text"]).pack(side=tk.LEFT)
            if subtitle:
                tk.Label(header, text=subtitle, font=t["font_xs"], bg=t["surface"], fg=t["text_muted"]).pack(side=tk.LEFT, padx=(t["pad_sm"], 0))
        return card
    
    def create_layout(self):
        t = self.theme
        
        # Create scrollable container
        container = tk.Frame(self.root, bg=t["bg"])
        container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(container, bg=t["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        
        self.scrollable_frame = tk.Frame(canvas, bg=t["bg"])
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind canvas resize to adjust inner frame width
        def resize_frame(event):
            canvas.itemconfig(canvas.find_all()[0], width=event.width)
        canvas.bind("<Configure>", resize_frame)
        
        main = tk.Frame(self.scrollable_frame, bg=t["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=t["pad_xl"], pady=t["pad_lg"])
        
        # Header
        header = tk.Frame(main, bg=t["bg"])
        header.pack(fill=tk.X, pady=(0, t["pad_sm"]))
        tk.Label(header, text="🏗️ Döşeme Sistemi Tasarımı", font=t["font_xl"], bg=t["bg"], fg=t["text"]).pack(side=tk.LEFT)
        
        # Global Parameters
        self.create_global_params(main)
        
        # Middle: Left (Slabs + Connections) | Right (Plan View) - FIXED HEIGHT
        middle = tk.Frame(main, bg=t["bg"], height=200)
        middle.pack(fill=tk.X, pady=t["pad_xs"])
        middle.pack_propagate(False)  # Keep fixed height
        middle.columnconfigure(0, weight=1)
        middle.columnconfigure(1, weight=1)
        middle.rowconfigure(0, weight=1)
        
        # Left column
        left_col = tk.Frame(middle, bg=t["bg"])
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, t["pad_sm"]))
        left_col.rowconfigure(0, weight=1)
        left_col.rowconfigure(1, weight=1)
        left_col.columnconfigure(0, weight=1)
        
        self.create_slabs_panel(left_col)
        self.create_connections_panel(left_col)
        
        # Right column: Plan View
        self.create_plan_view(middle)
        
        # Action Bar
        self.create_action_bar(main)
        
        # Results - THIS SHOULD EXPAND
        self.create_results_panel(main)
    
    def create_global_params(self, parent):
        t = self.theme
        card = self.create_card(parent, "⚙️ Genel Parametreler")
        card.pack(fill=tk.X, pady=(0, t["pad_sm"]))
        
        grid = tk.Frame(card, bg=t["surface"])
        grid.pack(fill=tk.X, padx=t["pad_lg"], pady=(0, t["pad_lg"]))
        
        self.global_entries = {}
        params = [("Beton", "conc", "C25", ""), ("Çelik", "steel", "S420", ""),
                  ("g", "g_add", "1.5", "kN/m²"), ("q", "q", "3.5", "kN/m²"),
                  ("h", "h", "140", "mm"), ("Pas Payı", "cover", "20", "mm")]
        
        for i, (label, key, default, unit) in enumerate(params):
            frame = tk.Frame(grid, bg=t["surface"])
            frame.grid(row=0, column=i, padx=t["pad_md"], pady=t["pad_xs"])
            tk.Label(frame, text=label, font=t["font_xs"], bg=t["surface"], fg=t["text_secondary"]).pack(anchor=tk.W)
            input_row = tk.Frame(frame, bg=t["surface"])
            input_row.pack(fill=tk.X)
            entry = ttk.Entry(input_row, width=8, font=t["font_sm"])
            entry.insert(0, default)
            entry.pack(side=tk.LEFT)
            if unit:
                tk.Label(input_row, text=unit, font=t["font_xs"], bg=t["surface"], fg=t["text_muted"]).pack(side=tk.LEFT, padx=(4, 0))
            self.global_entries[key] = entry
    
    def create_slabs_panel(self, parent):
        t = self.theme
        card = self.create_card(parent, "📋 Döşemeler")
        card.grid(row=0, column=0, sticky="nsew", pady=(0, t["pad_xs"]))
        
        toolbar = tk.Frame(card, bg=t["surface"])
        toolbar.pack(fill=tk.X, padx=t["pad_lg"], pady=(0, t["pad_xs"]))
        self.create_button(toolbar, "+ Ekle", self.show_add_slab_dialog, "success", "sm").pack(side=tk.LEFT)
        self.create_button(toolbar, "✏️", self.edit_slab, "ghost", "sm").pack(side=tk.LEFT, padx=(t["pad_xs"], 0))
        self.create_button(toolbar, "🗑️", self.delete_slab, "ghost", "sm").pack(side=tk.LEFT, padx=(t["pad_xs"], 0))
        
        table_frame = tk.Frame(card, bg=t["surface"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=t["pad_lg"], pady=(0, t["pad_md"]))
        
        cols = ("id", "boyut", "mesnet", "kiris")
        self.slab_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=4)
        for col, text, w in [("id", "ID", 70), ("boyut", "Boyut", 80), ("mesnet", "Mesnet", 55), ("kiris", "Kirişler", 140)]:
            self.slab_tree.heading(col, text=text, anchor=tk.W)
            self.slab_tree.column(col, width=w, anchor=tk.W)
        
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.slab_tree.yview)
        self.slab_tree.configure(yscrollcommand=vsb.set)
        self.slab_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection to update plan view
        self.slab_tree.bind("<<TreeviewSelect>>", lambda e: self.draw_plan())
    
    def create_connections_panel(self, parent):
        t = self.theme
        card = self.create_card(parent, "🔗 Bağlantılar")
        card.grid(row=1, column=0, sticky="nsew", pady=(t["pad_xs"], 0))
        
        toolbar = tk.Frame(card, bg=t["surface"])
        toolbar.pack(fill=tk.X, padx=t["pad_lg"], pady=(0, t["pad_xs"]))
        self.create_button(toolbar, "+ Ekle", self.show_add_connection_dialog, "success", "sm").pack(side=tk.LEFT)
        self.create_button(toolbar, "🗑️", self.delete_connection, "ghost", "sm").pack(side=tk.LEFT, padx=(t["pad_xs"], 0))
        
        table_frame = tk.Frame(card, bg=t["surface"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=t["pad_lg"], pady=(0, t["pad_md"]))
        
        self.conn_tree = ttk.Treeview(table_frame, columns=("conn",), show="headings", height=4)
        self.conn_tree.heading("conn", text="Bağlantı", anchor=tk.W)
        self.conn_tree.column("conn", width=280, anchor=tk.W)
        self.conn_tree.pack(fill=tk.BOTH, expand=True)
    
    def create_plan_view(self, parent):
        """Create the visual plan view canvas."""
        t = self.theme
        card = self.create_card(parent, "🗺️ Plan Görünümü", "(Döşeme yerleşimi)")
        card.grid(row=0, column=1, sticky="nsew", padx=(t["pad_sm"], 0))
        
        # Canvas for drawing
        canvas_frame = tk.Frame(card, bg=t["surface"])
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=t["pad_lg"], pady=(0, t["pad_lg"]))
        
        self.plan_canvas = tk.Canvas(canvas_frame, bg="#f8fafc", highlightthickness=1,
                                     highlightbackground=t["border"])
        self.plan_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind resize
        self.plan_canvas.bind("<Configure>", lambda e: self.draw_plan())
    
    def draw_plan(self):
        """Draw the slab plan view based on connections."""
        canvas = self.plan_canvas
        canvas.delete("all")
        
        if not self.slabs:
            canvas.create_text(canvas.winfo_width()//2, canvas.winfo_height()//2,
                              text="Döşeme ekleyin", font=self.theme["font_md"],
                              fill=self.theme["text_muted"])
            return
        
        t = self.theme
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        if cw < 50 or ch < 50:
            return
        
        # Calculate positions based on connections
        positions = self.calculate_slab_positions()
        
        # Find bounds
        all_x = [p[0] for p in positions.values()] + [p[0] + self.slabs[s]["lx"] for s, p in positions.items()]
        all_y = [p[1] for p in positions.values()] + [p[1] + self.slabs[s]["ly"] for s, p in positions.items()]
        
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        total_w = max_x - min_x
        total_h = max_y - min_y
        
        # Scale to fit canvas with padding
        pad = 40
        scale_x = (cw - 2*pad) / total_w if total_w > 0 else 1
        scale_y = (ch - 2*pad) / total_h if total_h > 0 else 1
        scale = min(scale_x, scale_y, 50)  # Max 50px per meter
        
        # Center offset
        off_x = (cw - total_w * scale) / 2 - min_x * scale
        off_y = (ch - total_h * scale) / 2 - min_y * scale
        
        # Colors for slabs
        slab_colors = ["#dbeafe", "#fef3c7", "#dcfce7", "#fce7f3", "#e0e7ff", "#fef9c3"]
        
        # Draw slabs
        for i, (slab_id, (px, py)) in enumerate(positions.items()):
            data = self.slabs[slab_id]
            lx, ly = data["lx"], data["ly"]
            
            x1 = off_x + px * scale
            y1 = off_y + py * scale
            x2 = x1 + lx * scale
            y2 = y1 + ly * scale
            
            color = slab_colors[i % len(slab_colors)]
            
            # Rectangle
            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=t["primary"], width=2)
            
            # Label
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            canvas.create_text(cx, cy - 8, text=slab_id, font=t["font_sm"], fill=t["text"])
            canvas.create_text(cx, cy + 8, text=f"{lx}×{ly}m", font=t["font_xs"], fill=t["text_secondary"])
            
            # Edge indicators for beams (0 = no beam = cantilever)
            if data["bw_lx"] == 0:
                canvas.create_line(x1, y1+5, x1, y2-5, fill=t["danger"], width=3, dash=(4,2))
            if data["bw_rx"] == 0:
                canvas.create_line(x2, y1+5, x2, y2-5, fill=t["danger"], width=3, dash=(4,2))
            if data["bw_ly"] == 0:
                canvas.create_line(x1+5, y1, x2-5, y1, fill=t["danger"], width=3, dash=(4,2))
            if data["bw_ry"] == 0:
                canvas.create_line(x1+5, y2, x2-5, y2, fill=t["danger"], width=3, dash=(4,2))
        
        # Draw connections as lines between edges
        edge_positions = {
            "left": lambda x1, y1, x2, y2: (x1, (y1+y2)/2),
            "right": lambda x1, y1, x2, y2: (x2, (y1+y2)/2),
            "top": lambda x1, y1, x2, y2: ((x1+x2)/2, y1),
            "bottom": lambda x1, y1, x2, y2: ((x1+x2)/2, y2),
        }
        
        for s1, e1, s2, e2 in self.connections:
            if s1 in positions and s2 in positions:
                d1, d2 = self.slabs[s1], self.slabs[s2]
                p1, p2 = positions[s1], positions[s2]
                
                x1_1, y1_1 = off_x + p1[0] * scale, off_y + p1[1] * scale
                x1_2, y1_2 = x1_1 + d1["lx"] * scale, y1_1 + d1["ly"] * scale
                
                x2_1, y2_1 = off_x + p2[0] * scale, off_y + p2[1] * scale
                x2_2, y2_2 = x2_1 + d2["lx"] * scale, y2_1 + d2["ly"] * scale
                
                cx1, cy1 = edge_positions[e1](x1_1, y1_1, x1_2, y1_2)
                cx2, cy2 = edge_positions[e2](x2_1, y2_1, x2_2, y2_2)
                
                # Draw connection line
                canvas.create_line(cx1, cy1, cx2, cy2, fill=t["warning"], width=2, dash=(6, 3))
        
        # Legend
        canvas.create_rectangle(10, ch-50, 20, ch-40, fill="#dbeafe", outline=t["primary"])
        canvas.create_text(25, ch-45, text="Döşeme", font=t["font_xs"], fill=t["text_secondary"], anchor=tk.W)
        
        canvas.create_line(10, ch-30, 30, ch-30, fill=t["danger"], width=2, dash=(4,2))
        canvas.create_text(35, ch-30, text="Konsol", font=t["font_xs"], fill=t["text_secondary"], anchor=tk.W)
        
        canvas.create_line(10, ch-15, 30, ch-15, fill=t["warning"], width=2, dash=(6,3))
        canvas.create_text(35, ch-15, text="Bağlantı", font=t["font_xs"], fill=t["text_secondary"], anchor=tk.W)
    
    def calculate_slab_positions(self):
        """Calculate slab positions based on connections."""
        if not self.slabs:
            return {}
        
        positions = {}
        placed = set()
        
        # Start with first slab at origin
        first_slab = list(self.slabs.keys())[0]
        positions[first_slab] = (0, 0)
        placed.add(first_slab)
        
        # Process connections to place remaining slabs
        changed = True
        while changed:
            changed = False
            for s1, e1, s2, e2 in self.connections:
                if s1 in placed and s2 not in placed:
                    # Place s2 relative to s1
                    p1 = positions[s1]
                    d1, d2 = self.slabs[s1], self.slabs[s2]
                    
                    if e1 == "right" and e2 == "left":
                        positions[s2] = (p1[0] + d1["lx"], p1[1])
                    elif e1 == "left" and e2 == "right":
                        positions[s2] = (p1[0] - d2["lx"], p1[1])
                    elif e1 == "bottom" and e2 == "top":
                        positions[s2] = (p1[0], p1[1] + d1["ly"])
                    elif e1 == "top" and e2 == "bottom":
                        positions[s2] = (p1[0], p1[1] - d2["ly"])
                    else:
                        # Approximate positioning for other edge combinations
                        positions[s2] = (p1[0] + d1["lx"], p1[1])
                    
                    placed.add(s2)
                    changed = True
                    
                elif s2 in placed and s1 not in placed:
                    # Place s1 relative to s2
                    p2 = positions[s2]
                    d1, d2 = self.slabs[s1], self.slabs[s2]
                    
                    if e2 == "right" and e1 == "left":
                        positions[s1] = (p2[0] + d2["lx"], p2[1])
                    elif e2 == "left" and e1 == "right":
                        positions[s1] = (p2[0] - d1["lx"], p2[1])
                    elif e2 == "bottom" and e1 == "top":
                        positions[s1] = (p2[0], p2[1] + d2["ly"])
                    elif e2 == "top" and e1 == "bottom":
                        positions[s1] = (p2[0], p2[1] - d1["ly"])
                    else:
                        positions[s1] = (p2[0] + d2["lx"], p2[1])
                    
                    placed.add(s1)
                    changed = True
        
        # Place any remaining unconnected slabs
        offset_x = 0
        for slab_id in self.slabs:
            if slab_id not in positions:
                # Find max x position
                if positions:
                    max_x = max(p[0] + self.slabs[s]["lx"] for s, p in positions.items())
                else:
                    max_x = 0
                positions[slab_id] = (max_x + 1, 0)
        
        return positions
    
    def create_action_bar(self, parent):
        t = self.theme
        bar = tk.Frame(parent, bg=t["bg"])
        bar.pack(fill=tk.X, pady=t["pad_sm"])
        
        solve_btn = self.create_button(bar, "🔧 Hesapla ve Çöz", self.solve, "primary", "lg")
        solve_btn.pack(side=tk.LEFT)
        
        self.status_frame = tk.Frame(bar, bg=t["bg"])
        self.status_frame.pack(side=tk.LEFT, padx=t["pad_lg"])
        self.status_icon = tk.Label(self.status_frame, text="○", font=t["font_md"], bg=t["bg"], fg=t["text_muted"])
        self.status_icon.pack(side=tk.LEFT)
        self.status_label = tk.Label(self.status_frame, text="Hesaplama bekleniyor", font=t["font_sm"], bg=t["bg"], fg=t["text_muted"])
        self.status_label.pack(side=tk.LEFT, padx=(t["pad_xs"], 0))
    
    def create_results_panel(self, parent):
        t = self.theme
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Slab Results
        slab_tab = tk.Frame(self.notebook, bg=t["surface"])
        self.notebook.add(slab_tab, text="  📊 Döşeme Sonuçları  ")
        
        info = tk.Frame(slab_tab, bg="#eff6ff")
        info.pack(fill=tk.X, padx=t["pad_sm"], pady=t["pad_sm"])
        tk.Label(info, text="ℹ️  Her döşeme için X ve Y yönünde moment, gerekli donatı ve seçilen donatı gösterilir.",
                font=t["font_xs"], bg="#eff6ff", fg="#1e40af").pack(anchor=tk.W, padx=t["pad_sm"], pady=t["pad_xs"])
        
        cols = ("doseme", "yon", "md", "d", "as_req", "donati", "as_prov", "durum")
        self.result_tree = ttk.Treeview(slab_tab, columns=cols, show="headings", height=7)
        headings = [("doseme", "Döşeme", 90), ("yon", "Yön", 50), ("md", "Md (kNm)", 85),
                   ("d", "d (cm)", 65), ("as_req", "As,req (mm²)", 100),
                   ("donati", "Seçilen Donatı", 180), ("as_prov", "As,prov (mm²)", 105), ("durum", "Durum", 70)]
        for col, text, width in headings:
            self.result_tree.heading(col, text=text, anchor=tk.CENTER if col != "donati" else tk.W)
            self.result_tree.column(col, width=width, anchor=tk.CENTER if col != "donati" else tk.W)
        
        vsb1 = ttk.Scrollbar(slab_tab, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=vsb1.set)
        self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(t["pad_sm"], 0), pady=(0, t["pad_sm"]))
        vsb1.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, t["pad_sm"]), pady=(0, t["pad_sm"]))
        
        # Tab 2: Support Results
        support_tab = tk.Frame(self.notebook, bg=t["surface"])
        self.notebook.add(support_tab, text="  📐 Mesnet Sonuçları  ")
        
        info2 = tk.Frame(support_tab, bg="#fef3c7")
        info2.pack(fill=tk.X, padx=t["pad_sm"], pady=t["pad_sm"])
        tk.Label(info2, text="⚠️  Mesnet momentleri dengelenmiş değerlerdir.",
                font=t["font_xs"], bg="#fef3c7", fg="#92400e").pack(anchor=tk.W, padx=t["pad_sm"], pady=t["pad_xs"])
        
        cols2 = ("mesnet", "md", "as_req", "mevcut", "ek_gerek", "ek_donati", "toplam", "durum")
        self.support_tree = ttk.Treeview(support_tab, columns=cols2, show="headings", height=5)
        headings2 = [("mesnet", "Mesnet", 140), ("md", "Md (kNm)", 85), ("as_req", "As,req", 80),
                    ("mevcut", "Mevcut", 80), ("ek_gerek", "Ek Gerek", 80),
                    ("ek_donati", "Ek Donatı", 110), ("toplam", "Toplam", 80), ("durum", "Durum", 70)]
        for col, text, width in headings2:
            self.support_tree.heading(col, text=text, anchor=tk.CENTER if col != "mesnet" else tk.W)
            self.support_tree.column(col, width=width, anchor=tk.CENTER if col != "mesnet" else tk.W)
        
        vsb2 = ttk.Scrollbar(support_tab, orient="vertical", command=self.support_tree.yview)
        self.support_tree.configure(yscrollcommand=vsb2.set)
        self.support_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(t["pad_sm"], 0), pady=(0, t["pad_sm"]))
        vsb2.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, t["pad_sm"]), pady=(0, t["pad_sm"]))
        
        # Tab 3: Calculation Details
        from tkinter import scrolledtext
        calc_tab = tk.Frame(self.notebook, bg=t["surface"])
        self.notebook.add(calc_tab, text="  📋 Hesap Detayları  ")
        
        info3 = tk.Frame(calc_tab, bg="#f0fdf4")
        info3.pack(fill=tk.X, padx=t["pad_sm"], pady=t["pad_sm"])
        tk.Label(info3, text="📋  Detaylı hesap adımları, formüller ve yönetmelik kontrolleri",
                font=t["font_xs"], bg="#f0fdf4", fg="#166534").pack(anchor=tk.W, padx=t["pad_sm"], pady=t["pad_xs"])
        
        self.calc_log = scrolledtext.ScrolledText(calc_tab, wrap=tk.WORD, font=("Consolas", 9),
                                                   bg="#1e293b", fg="#e2e8f0", insertbackground="white",
                                                   relief=tk.FLAT, padx=10, pady=10)
        self.calc_log.pack(fill=tk.BOTH, expand=True, padx=t["pad_sm"], pady=(0, t["pad_sm"]))
    
    # ==================== DIALOGS ====================
    
    def show_add_slab_dialog(self, edit_data=None):
        t = self.theme
        dialog = tk.Toplevel(self.root)
        dialog.title("Döşeme Ekle" if not edit_data else "Döşeme Düzenle")
        dialog.geometry("480x480")
        dialog.configure(bg=t["surface"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 480) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 480) // 2
        dialog.geometry(f"+{x}+{y}")
        
        content = tk.Frame(dialog, bg=t["surface"])
        content.pack(fill=tk.BOTH, expand=True, padx=t["pad_xl"], pady=t["pad_lg"])
        
        tk.Label(content, text="📋 Döşeme Bilgileri", font=t["font_lg"], bg=t["surface"], fg=t["text"]).pack(anchor=tk.W, pady=(0, t["pad_md"]))
        
        entries = {}
        
        # Basic Info
        section1 = tk.LabelFrame(content, text="Temel Bilgiler", font=t["font_sm"], bg=t["surface"], fg=t["text_secondary"])
        section1.pack(fill=tk.X, pady=(0, t["pad_md"]))
        
        row1 = tk.Frame(section1, bg=t["surface"])
        row1.pack(fill=tk.X, padx=t["pad_md"], pady=t["pad_sm"])
        
        for label, key, default, width in [
            ("ID:", "id", edit_data.get("id", f"D{self.slab_counter}") if edit_data else f"D{self.slab_counter}", 10),
            ("Lx (m):", "lx", edit_data.get("lx", 6.0) if edit_data else 6.0, 8),
            ("Ly (m):", "ly", edit_data.get("ly", 6.0) if edit_data else 6.0, 8),
        ]:
            frame = tk.Frame(row1, bg=t["surface"])
            frame.pack(side=tk.LEFT, padx=(0, t["pad_md"]))
            tk.Label(frame, text=label, font=t["font_xs"], bg=t["surface"], fg=t["text_secondary"]).pack(anchor=tk.W)
            entry = ttk.Entry(frame, width=width, font=t["font_sm"])
            entry.insert(0, str(default))
            entry.pack()
            entries[key] = entry
        
        case_frame = tk.Frame(row1, bg=t["surface"])
        case_frame.pack(side=tk.LEFT)
        tk.Label(case_frame, text="Mesnet:", font=t["font_xs"], bg=t["surface"], fg=t["text_secondary"]).pack(anchor=tk.W)
        case_var = tk.StringVar(value=str(edit_data.get("case", 3)) if edit_data else "3")
        case_combo = ttk.Combobox(case_frame, textvariable=case_var, width=6, state="readonly", font=t["font_sm"])
        case_combo['values'] = tuple(range(1, 10))
        case_combo.pack()
        
        # Beam widths
        section2 = tk.LabelFrame(content, text="Kiriş Genişlikleri (mm) - Konsol için 0", font=t["font_sm"], bg=t["surface"], fg=t["text_secondary"])
        section2.pack(fill=tk.X, pady=(0, t["pad_md"]))
        
        beam_grid = tk.Frame(section2, bg=t["surface"])
        beam_grid.pack(padx=t["pad_md"], pady=t["pad_sm"])
        
        beam_fields = [
            (0, 1, "Üst Y:", "bw_ry", edit_data.get("bw_ry", 250) if edit_data else 250),
            (1, 0, "Sol X:", "bw_lx", edit_data.get("bw_lx", 250) if edit_data else 250),
            (1, 2, "Sağ X:", "bw_rx", edit_data.get("bw_rx", 250) if edit_data else 250),
            (2, 1, "Alt Y:", "bw_ly", edit_data.get("bw_ly", 250) if edit_data else 250),
        ]
        
        for row, col, label, key, default in beam_fields:
            frame = tk.Frame(beam_grid, bg=t["surface"])
            frame.grid(row=row, column=col, padx=t["pad_sm"], pady=t["pad_xs"])
            tk.Label(frame, text=label, font=t["font_xs"], bg=t["surface"], fg=t["text_secondary"]).pack()
            entry = ttk.Entry(frame, width=8, font=t["font_sm"], justify=tk.CENTER)
            entry.insert(0, str(int(default)))
            entry.pack()
            entries[key] = entry
        
        center = tk.Label(beam_grid, text="⬜\nDöşeme", font=t["font_xs"], bg=t["surface_alt"], fg=t["text_muted"], width=10, height=3)
        center.grid(row=1, column=1, padx=t["pad_sm"], pady=t["pad_sm"])
        
        btn_row = tk.Frame(content, bg=t["surface"])
        btn_row.pack(fill=tk.X, pady=(t["pad_md"], 0))
        
        def save():
            try:
                slab_id = entries["id"].get().strip()
                if not slab_id:
                    raise ValueError("ID boş olamaz")
                data = {
                    "id": slab_id,
                    "lx": float(entries["lx"].get()),
                    "ly": float(entries["ly"].get()),
                    "bw_lx": float(entries["bw_lx"].get()),
                    "bw_rx": float(entries["bw_rx"].get()),
                    "bw_ly": float(entries["bw_ly"].get()),
                    "bw_ry": float(entries["bw_ry"].get()),
                    "case": int(case_var.get())
                }
                if edit_data and edit_data.get("id") != slab_id:
                    del self.slabs[edit_data["id"]]
                self.slabs[slab_id] = data
                self.refresh_slab_list()
                self.draw_plan()
                self.slab_counter += 1
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Hata", f"Geçersiz değer: {e}", parent=dialog)
        
        self.create_button(btn_row, "İptal", dialog.destroy, "ghost", "md").pack(side=tk.RIGHT)
        self.create_button(btn_row, "💾 Kaydet", save, "primary", "md").pack(side=tk.RIGHT, padx=(0, t["pad_sm"]))
    
    def show_add_connection_dialog(self):
        if len(self.slabs) < 2:
            messagebox.showwarning("Uyarı", "Bağlantı için en az 2 döşeme gerekli!")
            return
        
        t = self.theme
        dialog = tk.Toplevel(self.root)
        dialog.title("Bağlantı Ekle")
        dialog.geometry("380x300")
        dialog.configure(bg=t["surface"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 380) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 300) // 2
        dialog.geometry(f"+{x}+{y}")
        
        content = tk.Frame(dialog, bg=t["surface"])
        content.pack(fill=tk.BOTH, expand=True, padx=t["pad_xl"], pady=t["pad_lg"])
        
        tk.Label(content, text="🔗 Bağlantı Tanımla", font=t["font_lg"], bg=t["surface"], fg=t["text"]).pack(anchor=tk.W, pady=(0, t["pad_md"]))
        
        slab_ids = list(self.slabs.keys())
        edges = {"Sol": "left", "Sağ": "right", "Üst": "top", "Alt": "bottom"}
        edge_names = list(edges.keys())
        
        frame1 = tk.LabelFrame(content, text="Birinci Döşeme", font=t["font_sm"], bg=t["surface"], fg=t["text_secondary"])
        frame1.pack(fill=tk.X, pady=(0, t["pad_sm"]))
        row1 = tk.Frame(frame1, bg=t["surface"])
        row1.pack(fill=tk.X, padx=t["pad_md"], pady=t["pad_sm"])
        
        tk.Label(row1, text="Döşeme:", font=t["font_xs"], bg=t["surface"]).pack(side=tk.LEFT)
        slab1_var = tk.StringVar(value=slab_ids[0])
        ttk.Combobox(row1, textvariable=slab1_var, values=slab_ids, width=12, state="readonly").pack(side=tk.LEFT, padx=t["pad_sm"])
        tk.Label(row1, text="Kenar:", font=t["font_xs"], bg=t["surface"]).pack(side=tk.LEFT, padx=(t["pad_md"], 0))
        edge1_var = tk.StringVar(value="Sağ")
        ttk.Combobox(row1, textvariable=edge1_var, values=edge_names, width=8, state="readonly").pack(side=tk.LEFT, padx=t["pad_sm"])
        
        tk.Label(content, text="↕️", font=("Segoe UI", 16), bg=t["surface"]).pack(pady=t["pad_xs"])
        
        frame2 = tk.LabelFrame(content, text="İkinci Döşeme", font=t["font_sm"], bg=t["surface"], fg=t["text_secondary"])
        frame2.pack(fill=tk.X, pady=(0, t["pad_md"]))
        row2 = tk.Frame(frame2, bg=t["surface"])
        row2.pack(fill=tk.X, padx=t["pad_md"], pady=t["pad_sm"])
        
        tk.Label(row2, text="Döşeme:", font=t["font_xs"], bg=t["surface"]).pack(side=tk.LEFT)
        slab2_var = tk.StringVar(value=slab_ids[1] if len(slab_ids) > 1 else slab_ids[0])
        ttk.Combobox(row2, textvariable=slab2_var, values=slab_ids, width=12, state="readonly").pack(side=tk.LEFT, padx=t["pad_sm"])
        tk.Label(row2, text="Kenar:", font=t["font_xs"], bg=t["surface"]).pack(side=tk.LEFT, padx=(t["pad_md"], 0))
        edge2_var = tk.StringVar(value="Sol")
        ttk.Combobox(row2, textvariable=edge2_var, values=edge_names, width=8, state="readonly").pack(side=tk.LEFT, padx=t["pad_sm"])
        
        btn_row = tk.Frame(content, bg=t["surface"])
        btn_row.pack(fill=tk.X, pady=(t["pad_md"], 0))
        
        def save():
            s1, e1 = slab1_var.get(), edges[edge1_var.get()]
            s2, e2 = slab2_var.get(), edges[edge2_var.get()]
            if s1 == s2:
                messagebox.showerror("Hata", "Aynı döşeme seçilemez!", parent=dialog)
                return
            self.connections.append((s1, e1, s2, e2))
            self.refresh_connection_list()
            self.draw_plan()
            dialog.destroy()
        
        self.create_button(btn_row, "İptal", dialog.destroy, "ghost", "md").pack(side=tk.RIGHT)
        self.create_button(btn_row, "💾 Kaydet", save, "primary", "md").pack(side=tk.RIGHT, padx=(0, t["pad_sm"]))
    
    # ==================== ACTIONS ====================
    
    def edit_slab(self):
        sel = self.slab_tree.selection()
        if not sel:
            messagebox.showinfo("Bilgi", "Düzenlemek için bir döşeme seçin.")
            return
        slab_id = self.slab_tree.item(sel[0])['values'][0]
        self.show_add_slab_dialog(edit_data=self.slabs[slab_id])
    
    def delete_slab(self):
        sel = self.slab_tree.selection()
        if not sel:
            return
        slab_id = self.slab_tree.item(sel[0])['values'][0]
        self.connections = [c for c in self.connections if slab_id not in (c[0], c[2])]
        del self.slabs[slab_id]
        self.refresh_slab_list()
        self.refresh_connection_list()
        self.draw_plan()
    
    def delete_connection(self):
        sel = self.conn_tree.selection()
        if not sel:
            return
        idx = self.conn_tree.index(sel[0])
        del self.connections[idx]
        self.refresh_connection_list()
        self.draw_plan()
    
    def refresh_slab_list(self):
        for item in self.slab_tree.get_children():
            self.slab_tree.delete(item)
        for sid, d in self.slabs.items():
            dims = f"{d['lx']}×{d['ly']}"
            beams = f"X:{int(d['bw_lx'])}/{int(d['bw_rx'])} Y:{int(d['bw_ly'])}/{int(d['bw_ry'])}"
            self.slab_tree.insert("", tk.END, values=(sid, dims, d['case'], beams))
    
    def refresh_connection_list(self):
        for item in self.conn_tree.get_children():
            self.conn_tree.delete(item)
        edge_tr = {"left": "Sol", "right": "Sağ", "top": "Üst", "bottom": "Alt"}
        for s1, e1, s2, e2 in self.connections:
            text = f"{s1} ({edge_tr[e1]}) ↔ {s2} ({edge_tr[e2]})"
            self.conn_tree.insert("", tk.END, values=(text,))
    
    def load_defaults(self):
        self.slabs = {
            "D1_Sol": {"id": "D1_Sol", "lx": 6.0, "ly": 6.0, "bw_lx": 250, "bw_rx": 250, "bw_ly": 250, "bw_ry": 250, "case": 3},
            "D1_Sag": {"id": "D1_Sag", "lx": 6.0, "ly": 6.0, "bw_lx": 250, "bw_rx": 250, "bw_ly": 250, "bw_ry": 250, "case": 3},
            "BD_Alt": {"id": "BD_Alt", "lx": 6.0, "ly": 1.5, "bw_lx": 250, "bw_rx": 250, "bw_ly": 250, "bw_ry": 0, "case": 8},
            "BD_Ust": {"id": "BD_Ust", "lx": 6.0, "ly": 1.5, "bw_lx": 250, "bw_rx": 250, "bw_ly": 0, "bw_ry": 250, "case": 8},
        }
        self.connections = [
            ("D1_Sol", "right", "D1_Sag", "left"),
            ("D1_Sol", "bottom", "BD_Alt", "top"),
            ("D1_Sag", "top", "BD_Ust", "bottom"),
        ]
        self.slab_counter = 5
        self.refresh_slab_list()
        self.refresh_connection_list()
    
    def get_global_values(self):
        try:
            return {
                "conc": self.global_entries["conc"].get().strip().upper(),
                "steel": self.global_entries["steel"].get().strip().upper(),
                "g_add": float(self.global_entries["g_add"].get()),
                "q": float(self.global_entries["q"].get()),
                "h": float(self.global_entries["h"].get()),
                "cover": float(self.global_entries["cover"].get()),
            }
        except ValueError:
            messagebox.showerror("Hata", "Geçersiz parametre değeri!")
            return None
    
    def set_status(self, text, state="idle"):
        t = self.theme
        states = {"idle": (t["text_muted"], "○"), "running": (t["primary"], "◉"),
                 "success": (t["success"], "✓"), "error": (t["danger"], "✗")}
        color, icon = states.get(state, states["idle"])
        self.status_icon.config(text=icon, fg=color)
        self.status_label.config(text=text, fg=color)
    
    def solve(self):
        if not self.slabs:
            messagebox.showwarning("Uyarı", "En az bir döşeme ekleyin!")
            return
        
        gv = self.get_global_values()
        if not gv:
            return
        
        self.set_status("Hesaplanıyor...", "running")
        self.root.update()
        
        try:
            system = SlabSystem()
            for slab_id, data in self.slabs.items():
                inp = InputData(
                    lx=data['lx'], ly=data['ly'],
                    beam_w_left_x=data['bw_lx'], beam_w_right_x=data['bw_rx'],
                    beam_w_left_y=data['bw_ly'], beam_w_right_y=data['bw_ry'],
                    h_mm=gv['h'], cover_mm=gv['cover'],
                    concrete=gv['conc'], steel=gv['steel'],
                    g_additional=gv['g_add'], q_live=gv['q'],
                    slab_case=data['case'], slab_id=slab_id
                )
                system.add_slab(slab_id, inp)
            
            for s1, e1, s2, e2 in self.connections:
                system.connect(s1, e1, s2, e2)
            
            import sys
            from io import StringIO
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            system.solve()
            generate_system_dxf(system, "System_Reinforcement.dxf")
            sys.stdout = old_stdout
            
            self.populate_results(system, gv)
            self.set_status("Hesaplama tamamlandı • DXF oluşturuldu", "success")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Hata", f"Hesaplama hatası:\n{str(e)}")
            self.set_status("Hesaplama başarısız", "error")
    
    def populate_results(self, system, gv):
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        for item in self.support_tree.get_children():
            self.support_tree.delete(item)
        
        # Clear and populate calculation log
        self.calc_log.delete(1.0, tk.END)
        self.write_calculation_log(system, gv)
        
        for slab_id, slab in system.slabs.items():
            for direction, design in [("X", slab.design_x), ("Y", slab.design_y)]:
                if design.slab_type == "one_way" and design.M_pos_kNm_per_m < 0.001:
                    self.result_tree.insert("", tk.END, values=(slab_id, direction, "—", "—", "—", "Dağıtma donatısı", "—", "✓"))
                else:
                    layout = design.main_bottom_layout
                    if layout:
                        rebar = f"Ø{layout.straight.phi}/{layout.straight.s_cm:.0f} + Ø{layout.pilye.phi}/{layout.pilye.s_cm:.0f}"
                        as_prov = f"{layout.As_total_prov_mm2_per_m:.1f}"
                        ok = layout.As_total_prov_mm2_per_m >= design.As_pos_req_mm2_per_m
                    else:
                        rebar, as_prov, ok = "—", "—", False
                    
                    self.result_tree.insert("", tk.END, values=(
                        slab_id, direction, f"{design.M_pos_kNm_per_m:.2f}", f"{design.d_m*100:.1f}",
                        f"{design.As_pos_req_mm2_per_m:.1f}", rebar, as_prov, "✓ Yeterli" if ok else "✗ Yetersiz"
                    ), tags=("ok" if ok else "fail",))
        
        fck = int(gv['conc'].replace("C", ""))
        d_m = (gv['h'] - gv['cover'] - 4) / 1000
        
        for slab_id, slab in system.slabs.items():
            for edge, moment in slab.balanced_moments.items():
                if moment > 0.01:
                    _, _, As_req = calc_K_and_As_from_M(moment, d_m, fck, gv['steel'])
                    direction = "X" if edge in ["left", "right"] else "Y"
                    design = slab.design_x if direction == "X" else slab.design_y
                    
                    As_mevcut = 0
                    if design.main_bottom_layout and design.main_bottom_layout.pilye.phi > 0:
                        As_mevcut = design.main_bottom_layout.pilye.As_prov_mm2_per_m
                    
                    As_ek_req = max(0, As_req - As_mevcut)
                    if As_ek_req > 0:
                        ek_bar = choose_single_layer_rebar(As_ek_req, s_max_mm=300)
                        ek_rebar = f"Ø{ek_bar.phi}/{ek_bar.s_cm:.0f}"
                        total = As_mevcut + ek_bar.As_prov_mm2_per_m
                    else:
                        ek_rebar = "—"
                        total = As_mevcut
                    
                    ok = total >= As_req
                    edge_tr = {"left": "Sol", "right": "Sağ", "top": "Üst", "bottom": "Alt"}
                    
                    self.support_tree.insert("", tk.END, values=(
                        f"{slab_id} ({edge_tr[edge]})", f"{moment:.2f}", f"{As_req:.1f}",
                        f"{As_mevcut:.1f}", f"{As_ek_req:.1f}" if As_ek_req > 0 else "—",
                        ek_rebar, f"{total:.1f}", "✓ Yeterli" if ok else "✗ Yetersiz"
                    ), tags=("ok" if ok else "fail",))
        
        self.result_tree.tag_configure("ok", foreground=self.theme["success"])
        self.result_tree.tag_configure("fail", foreground=self.theme["danger"])
        self.support_tree.tag_configure("ok", foreground=self.theme["success"])
        self.support_tree.tag_configure("fail", foreground=self.theme["danger"])
    
    def write_calculation_log(self, system, gv):
        """Write detailed calculation steps to the log."""
        log = self.calc_log
        
        def write(text):
            log.insert(tk.END, text + "\n")
        
        def header(text):
            write("\n" + "=" * 60)
            write(f"  {text}")
            write("=" * 60)
        
        # Header
        header("DÖŞEME SİSTEMİ HESAP RAPORU")
        write(f"\nTarih: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        # Input Parameters
        header("1. GİRİŞ PARAMETRELERİ")
        write(f"\n  Beton Sınıfı    : {gv['conc']}")
        write(f"  Çelik Sınıfı    : {gv['steel']}")
        write(f"  Döşeme Kalınlığı: h = {gv['h']} mm")
        write(f"  Pas Payı        : c = {gv['cover']} mm")
        write(f"  Ek Sabit Yük    : g = {gv['g_add']} kN/m²")
        write(f"  Hareketli Yük   : q = {gv['q']} kN/m²")
        
        # Material properties
        fck = int(gv['conc'].replace("C", ""))
        fcd = fck / 1.5
        fyk = int(gv['steel'].replace("S", ""))
        fyd = fyk / 1.15
        
        write(f"\n  Malzeme Özellikleri:")
        write(f"    fck = {fck} MPa  →  fcd = fck/1.5 = {fcd:.2f} MPa")
        write(f"    fyk = {fyk} MPa  →  fyd = fyk/1.15 = {fyd:.2f} MPa")
        
        # Load calculation
        header("2. YÜK HESABI")
        gamma_beton = 25  # kN/m³
        g_self = gv['h'] / 1000 * gamma_beton
        g_total = g_self + gv['g_add']
        pd = 1.4 * g_total + 1.6 * gv['q']
        
        write(f"\n  Öz Ağırlık:")
        write(f"    g_öz = h × γ_beton = {gv['h']/1000:.3f} × 25 = {g_self:.2f} kN/m²")
        write(f"\n  Toplam Sabit Yük:")
        write(f"    g = g_öz + g_ek = {g_self:.2f} + {gv['g_add']:.2f} = {g_total:.2f} kN/m²")
        write(f"\n  Tasarım Yükü (TS500):")
        write(f"    pd = 1.4×g + 1.6×q = 1.4×{g_total:.2f} + 1.6×{gv['q']:.2f}")
        write(f"    pd = {pd:.2f} kN/m²")
        
        # Slab calculations
        header("3. DÖŞEME HESAPLARI")
        
        for slab_id, slab in system.slabs.items():
            data = self.slabs[slab_id]
            write(f"\n  ┌─ [{slab_id}] ─────────────────────────")
            write(f"  │ Boyutlar: Lx = {data['lx']} m, Ly = {data['ly']} m")
            write(f"  │ Mesnet Durumu: Tip {data['case']}")
            
            ratio = max(data['lx'], data['ly']) / min(data['lx'], data['ly'])
            slab_type = "Tek Doğrultulu" if ratio > 2 else "Çift Doğrultulu"
            write(f"  │ Oran: Lmax/Lmin = {ratio:.2f} → {slab_type}")
            
            for direction, design in [("X", slab.design_x), ("Y", slab.design_y)]:
                if design.slab_type == "one_way" and design.M_pos_kNm_per_m < 0.001:
                    write(f"  │\n  │ {direction} Yönü: Dağıtma donatısı (ikincil yön)")
                    continue
                
                write(f"  │\n  │ {direction} Yönü Hesabı:")
                write(f"  │   Md = {design.M_pos_kNm_per_m:.2f} kNm/m")
                write(f"  │   d = h - c - φ/2 = {design.d_m*1000:.0f} mm = {design.d_m*100:.1f} cm")
                write(f"  │")
                write(f"  │   K Hesabı:")
                write(f"  │   K = Md / (b × d² × fcd)")
                write(f"  │   K = {design.M_pos_kNm_per_m:.2f} / (1.0 × {design.d_m:.4f}² × {fcd*1000:.0f})")
                write(f"  │   K = {design.Kcalc_pos_x1e5:.1f} × 10⁻⁵")
                write(f"  │")
                write(f"  │   ks = {design.ks_pos:.2f} (tablodan)")
                write(f"  │   As = ks × Md / d = {design.ks_pos:.2f} × {design.M_pos_kNm_per_m:.2f} / {design.d_m:.4f}")
                write(f"  │   As,req = {design.As_pos_req_mm2_per_m:.1f} mm²/m")
                
                # Minimum reinforcement check
                rho_min = 0.0015  # TS500 minimum
                As_min = rho_min * 1000 * design.d_m * 1000
                write(f"  │")
                write(f"  │   Minimum Donatı Kontrolü (TS500):")
                write(f"  │   ρ_min = 0.0015")
                write(f"  │   As,min = ρ_min × b × d = 0.0015 × 1000 × {design.d_m*1000:.0f}")
                write(f"  │   As,min = {As_min:.1f} mm²/m")
                write(f"  │   As,req = {design.As_pos_req_mm2_per_m:.1f} {'≥' if design.As_pos_req_mm2_per_m >= As_min else '<'} As,min → {'OK' if design.As_pos_req_mm2_per_m >= As_min else 'As,min kullan'}")
                
                layout = design.main_bottom_layout
                if layout:
                    write(f"  │")
                    write(f"  │   Seçilen Donatı:")
                    write(f"  │   Düz: Ø{layout.straight.phi}/{layout.straight.s_cm:.0f} → As = {layout.straight.As_prov_mm2_per_m:.1f} mm²/m")
                    write(f"  │   Pilye: Ø{layout.pilye.phi}/{layout.pilye.s_cm:.0f} → As = {layout.pilye.As_prov_mm2_per_m:.1f} mm²/m")
                    write(f"  │   TOPLAM: As,prov = {layout.As_total_prov_mm2_per_m:.1f} mm²/m")
                    
                    # Spacing check
                    s_max = min(1.5 * gv['h'], 200)
                    s_actual = layout.straight.s_cm * 10  # mm
                    write(f"  │")
                    write(f"  │   Aralık Kontrolü:")
                    write(f"  │   s_max = min(1.5h, 200) = min({1.5*gv['h']:.0f}, 200) = {s_max:.0f} mm")
                    write(f"  │   s = {s_actual:.0f} mm {'≤' if s_actual <= s_max else '>'} s_max → {'OK' if s_actual <= s_max else 'UYGUN DEĞİL'}")
            
            write(f"  └─────────────────────────────────────")
        
        # Support moments
        header("4. MESNET MOMENTLERİ")
        
        for slab_id, slab in system.slabs.items():
            for edge, moment in slab.balanced_moments.items():
                if moment > 0.01:
                    edge_tr = {"left": "Sol", "right": "Sağ", "top": "Üst", "bottom": "Alt"}
                    write(f"\n  Mesnet: {slab_id} ({edge_tr[edge]})")
                    write(f"    Dengelenmiş Moment: Md = {moment:.2f} kNm/m")
        
        header("5. YÖNETMELİK KONTROLLER")
        write("\n  ✓ TS500 - Betonarme Yapıların Tasarım ve Yapım Kuralları")
        write("  ✓ Minimum donatı oranı: ρ_min = 0.0015")
        write("  ✓ Maksimum aralık: s_max = min(1.5h, 200mm)")
        write("  ✓ Yük katsayıları: 1.4G + 1.6Q")
        write("  ✓ Malzeme güvenlik katsayıları: γc=1.5, γs=1.15")
        
        write("\n" + "=" * 60)
        write("  HESAPLAMA TAMAMLANDI")
        write("=" * 60)


def main():
    root = tk.Tk()
    app = SlabDesignUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
