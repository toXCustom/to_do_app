import os
import sys
import threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import webbrowser
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox

from core.tasks import TaskManager
from core.storage import save_tasks, load_tasks, save_config, load_config
from datetime import datetime


import calendar as _calendar_lib

# ── Pure-canvas MiniCalendar — replaces tkcalendar entirely ──────────────────
# Zero external dependencies. Fully compatible with ttkbootstrap.
# API is a superset of tkcalendar's Calendar API used in this app.

class MiniCalendar(tk.Frame):
    DAY_W = 28; DAY_H = 24; DOW_H = 18; PAD = 4

    def __init__(self, master, **kw):
        # Strip tkcalendar-only kwargs we accept but don't use at init
        for k in ("selectmode","date_pattern","showweeknumbers","font",
                  "tooltipdelay"):
            kw.pop(k, None)
        super().__init__(master)
        from datetime import date
        self._today    = date.today()
        self._date     = self._today.replace(day=1)
        self._selected = self._today
        self._events   = {}   # date → [(ev_id, text, tag), …]
        self._tag_cfg  = {}   # tag  → {background, foreground}
        self._day_rects = {}  # date → (x1,y1,x2,y2)
        self._hover_date = None
        # Colour defaults (dark)
        self._bg=self._norm_bg="#22262F"; self._fg=self._norm_fg="#EDE9E3"
        self._hdr_bg="#1C1F26"; self._hdr_fg="#8A8E99"
        self._sel_bg="#E07A47"; self._sel_fg="#FFFFFF"
        self._wknd_bg="#1C1F26"; self._wknd_fg="#EDE9E3"
        self._other_bg="#13151A"; self._other_fg="#8A8E99"
        self._border_c="#2E3340"
        # Header row
        hdr = tk.Frame(self, bg=self._hdr_bg)
        hdr.pack(fill=tk.X)
        self._hdr_frame = hdr
        self._l_year  = tk.Button(hdr,text="«",relief="flat",cursor="hand2",font=("TkDefaultFont",9),command=self._prev_year)
        self._l_month = tk.Button(hdr,text="‹",relief="flat",cursor="hand2",font=("TkDefaultFont",9),command=self._prev_month)
        self._month_lbl = tk.Label(hdr,text="",font=("TkDefaultFont",9,"bold"))
        self._r_month = tk.Button(hdr,text="›",relief="flat",cursor="hand2",font=("TkDefaultFont",9),command=self._next_month)
        self._r_year  = tk.Button(hdr,text="»",relief="flat",cursor="hand2",font=("TkDefaultFont",9),command=self._next_year)
        for w in (self._l_year,self._l_month): w.pack(side=tk.LEFT,padx=2,pady=3)
        self._month_lbl.pack(side=tk.LEFT,expand=True)
        for w in (self._r_month,self._r_year): w.pack(side=tk.RIGHT,padx=2,pady=3)
        W = self.DAY_W*7; H = self.DOW_H + self.DAY_H*6 + self.PAD
        self._canvas = tk.Canvas(self,width=W,height=H,highlightthickness=0,bd=0)
        self._canvas.pack(fill=tk.X,padx=self.PAD,pady=(0,self.PAD))
        self._canvas.bind("<Button-1>",self._on_click)
        self._canvas.bind("<Motion>",  self._on_motion)
        self._canvas.bind("<Leave>",   self._on_leave)
        self._redraw()

    # ── tkcalendar-compatible API ─────────────────────────────────────────────
    def get_date(self): return self._selected.strftime("%Y-%m-%d")
    def set_date(self,d):
        from datetime import datetime as _dt
        if isinstance(d,str): d=_dt.strptime(d,"%Y-%m-%d").date()
        self._selected=d; self._date=d.replace(day=1); self._redraw()
    def get_calevents(self):
        return [ev_id for evs in self._events.values() for ev_id,_,_ in evs]
    def calevent_create(self,date_obj,text,tag):
        self._events.setdefault(date_obj,[])
        ev_id=hash((date_obj,text,tag,len(self._events[date_obj])))
        self._events[date_obj].append((ev_id,text,tag))
        self._redraw(); return ev_id
    def calevent_remove(self,ev_id=None):
        if ev_id is None: self._events.clear()
        else:
            for d in list(self._events):
                self._events[d]=[(i,t,g) for i,t,g in self._events[d] if i!=ev_id]
                if not self._events[d]: del self._events[d]
        self._redraw()
    def tag_config(self,tag,**kw): self._tag_cfg[tag]=kw; self._redraw()
    def configure(self,cnf=None,**kw):
        if isinstance(cnf,dict): kw.update(cnf)
        m={"background":"_bg","foreground":"_fg","headersbackground":"_hdr_bg",
           "headersforeground":"_hdr_fg","selectbackground":"_sel_bg",
           "selectforeground":"_sel_fg","normalbackground":"_norm_bg",
           "normalforeground":"_norm_fg","weekendbackground":"_wknd_bg",
           "weekendforeground":"_wknd_fg","othermonthbackground":"_other_bg",
           "othermonthforeground":"_other_fg","bordercolor":"_border_c"}
        for k,attr in m.items():
            if k in kw: setattr(self,attr,kw[k])
        self._redraw()
    def after(self,ms,fn=None,*args):
        return super().after(ms,fn,*args) if fn else super().after(ms)

    # ── Drawing ───────────────────────────────────────────────────────────────
    def _begin_update(self):
        """Suppress redraws during bulk operations."""
        self._batch = True

    def _end_update(self):
        """End batch mode and trigger a single redraw."""
        self._batch = False
        self._redraw()

    def _redraw(self):
        if getattr(self, '_batch', False):
            return
        from datetime import date as _d
        c=self._canvas; c.delete("all")
        bg=self._bg; fg=self._fg
        hb=self._hdr_bg; hf=self._hdr_fg
        sb=self._sel_bg; sf=self._sel_fg
        nb=self._norm_bg; nf=self._norm_fg
        wb=self._wknd_bg; wf=self._wknd_fg
        ob=self._other_bg; of_=self._other_fg
        bc=self._border_c
        self._month_lbl.configure(text=self._date.strftime("%B %Y"),bg=hb,fg=fg)
        for btn in (self._l_year,self._l_month,self._r_month,self._r_year):
            btn.configure(bg=hb,fg=hf,activebackground=hb,activeforeground=fg)
        self._hdr_frame.configure(bg=hb); self.configure_bg(bg)
        c.configure(bg=bg)
        DOW=["Mo","Tu","We","Th","Fr","Sa","Su"]
        for i,lbl in enumerate(DOW):
            c.create_text(i*self.DAY_W+self.DAY_W//2,self.DOW_H//2,text=lbl,
                          fill=wf if i>=5 else hf,font=("TkDefaultFont",8))
        y0=self.DOW_H; yr=self._date.year; mo=self._date.month
        weeks=_calendar_lib.monthcalendar(yr,mo)
        while len(weeks)<6: weeks.append([0]*7)
        self._day_rects={}
        for row,week in enumerate(weeks):
            for col,day in enumerate(week):
                x1=col*self.DAY_W; y1=y0+row*self.DAY_H
                x2=x1+self.DAY_W; y2=y1+self.DAY_H
                if day==0:
                    c.create_rectangle(x1,y1,x2,y2,fill=ob,outline=""); continue
                cd=_d(yr,mo,day)
                evs=self._events.get(cd,[])
                ev_cfg=self._tag_cfg.get(evs[0][2],{}) if evs else {}
                ev_bg=ev_cfg.get("background"); ev_fg=ev_cfg.get("foreground")
                is_sel=(cd==self._selected); is_today=(cd==self._today)
                is_hover=(cd==self._hover_date); is_wknd=(col>=5)
                if is_sel: cbg=sb; cfg=sf
                elif ev_bg: cbg=ev_bg; cfg=ev_fg or fg
                elif is_hover: cbg=sb; cfg=sf
                elif is_wknd: cbg=wb; cfg=wf
                else: cbg=nb; cfg=nf
                c.create_rectangle(x1,y1,x2,y2,fill=cbg,outline=bc,width=1)
                if is_today and not is_sel:
                    c.create_rectangle(x1+1,y1+1,x2-1,y2-1,outline=sb,width=2,fill="")
                font=("TkDefaultFont",8,"bold") if is_today else ("TkDefaultFont",8)
                c.create_text(x1+self.DAY_W//2,y1+self.DAY_H//2,text=str(day),
                              fill=cfg,font=font)
                if evs and not ev_bg:
                    c.create_oval(x2-8,y1+2,x2-2,y1+8,fill=sb,outline="")
                self._day_rects[cd]=(x1,y1,x2,y2)

    def configure_bg(self,bg):
        try: tk.Frame.configure(self,bg=bg)
        except Exception: pass

    # ── Navigation ────────────────────────────────────────────────────────────
    def _prev_month(self):
        y,m=self._date.year,self._date.month; m-=1
        if m==0: m=12; y-=1
        from datetime import date as _d; self._date=_d(y,m,1); self._redraw()
        self.event_generate("<<CalendarMonthChanged>>")
    def _next_month(self):
        y,m=self._date.year,self._date.month; m+=1
        if m==13: m=1; y+=1
        from datetime import date as _d; self._date=_d(y,m,1); self._redraw()
        self.event_generate("<<CalendarMonthChanged>>")
    def _prev_year(self):
        self._date=self._date.replace(year=self._date.year-1); self._redraw()
    def _next_year(self):
        self._date=self._date.replace(year=self._date.year+1); self._redraw()

    # ── Hit testing ───────────────────────────────────────────────────────────
    def _hit(self,x,y):
        y-=self.DOW_H
        for d,(x1,y1,x2,y2) in self._day_rects.items():
            if x1<=x<=x2 and (y1-self.DOW_H)<=y<=(y2-self.DOW_H): return d
        return None
    def _on_click(self,event):
        d=self._hit(event.x,event.y)
        if d: self._selected=d; self._redraw(); self.event_generate("<<CalendarSelected>>")
    def _on_motion(self,event):
        d=self._hit(event.x,event.y)
        if d!=self._hover_date: self._hover_date=d; self._redraw()
    def _on_leave(self,event):
        if self._hover_date: self._hover_date=None; self._redraw()

    # ── Stubs for _bind_cal_day_tooltips (canvas-based now) ──────────────────
    @property
    def _calendar(self): return []

Calendar = MiniCalendar
from core import logic
from services import export as export_module
from services import importer as import_module
from services import share as share_module
from services.reminders import ReminderService, PLYER_AVAILABLE as REMINDERS_AVAILABLE, DEFAULT_CONFIG as REMINDER_DEFAULTS
from core import categories as cat_module
from core.categories import auto_fg
from core.commands import (
    CommandHistory, AddTaskCommand, DeleteTaskCommand,
    EditTaskCommand, MarkDoneCommand, ToggleDoneCommand, snapshot
)

# pystray — optional system tray support
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

PRIORITY_ICONS = {"High": "🔥 High", "Medium": "⚡ Medium", "Low": "🌿 Low"}

# ---------- Theme Constants ----------
LIGHT_THEME = {
    "bg":               "#FAF7F2",   # warm parchment
    "fg":               "#1C1917",   # near-black text
    "muted_fg":         "#78716C",   # secondary text
    "accent":           "#C2622D",   # terracotta
    "accent_hover":     "#A85226",
    "accent_fg":        "#FFFFFF",
    "surface":          "#F2EDE6",   # toolbar / footer surface
    "surface2":         "#FFFFFF",   # list row background
    "border":           "#E0D9CF",
    "list_fg":          "#1C1917",
    "heading_fg":       "#78716C",
    "secondary_btn_bg": "#EDE8E1",
    "secondary_btn_fg": "#1C1917",
    "entry_bg":         "#FFFFFF",
}

DARK_THEME = {
    "bg":               "#13151A",   # deep midnight
    "fg":               "#EDE9E3",   # warm off-white
    "muted_fg":         "#8A8E99",
    "accent":           "#E07A47",   # warm orange
    "accent_hover":     "#C86832",
    "accent_fg":        "#FFFFFF",
    "surface":          "#1C1F26",   # lifted surface
    "surface2":         "#22262F",   # toolbar / footer
    "border":           "#2E3340",
    "list_fg":          "#EDE9E3",
    "heading_fg":       "#8A8E99",
    "secondary_btn_bg": "#22262F",
    "secondary_btn_fg": "#EDE9E3",
    "entry_bg":         "#22262F",
}


class TodoApp:
    def __init__(self, root, username: str = "", enc_key: bytes = None,
                 _session_info: dict = None):
        self.root         = root
        self.username     = username
        self.enc_key      = enc_key
        self._session_info = _session_info
        self.root.minsize(720, 480)
        config = load_config(username)
        self.root.geometry(config.get("geometry", "900x620"))
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._tray_icon = None

        # ── Workspace ──────────────────────────────────
        from core.workspaces import active_workspace, list_workspaces
        self.workspace = active_workspace(username) if username else "Default"

        # Task manager — load workspace-scoped file
        self.manager = TaskManager()
        load_tasks(self.manager, username, enc_key, workspace=self.workspace)

        # State
        config = load_config(username)
        self._update_title()
        self.dark_mode = config.get("dark_mode", False)
        self.minimize_to_tray = config.get("minimize_to_tray", True)
        self.sort_type = tk.StringVar(value=config.get("sort", "due_date"))
        self.sort_reverse = False
        self.filter_type = tk.StringVar(value=config.get("filter", "All"))
        self._calendar_date_filter = None
        self.categories      = cat_module.load_categories(config)
        self.category_colors = cat_module.load_category_colors(config)
        self._category_filter = None
        self.history = CommandHistory()
        self.search_var = tk.StringVar()
        self._search_after_id = None   # debounce handle

        def _debounced_search(*_):
            if self._search_after_id:
                self.root.after_cancel(self._search_after_id)
            self._search_after_id = self.root.after(200, self.refresh_tasks)

        self.search_var.trace_add("write", _debounced_search)

        # Reminder config
        self.reminder_cfg = {**REMINDER_DEFAULTS, **config.get("reminders", {})}
        self.api_cfg      = config.get("api", {"api_enabled": False, "api_port": 5000})

        self._build_ui()
        # ── Keyboard shortcuts ──────────────────────────
        kb = self.root.bind_all
        # Task actions
        kb("<Control-n>",        lambda e: self.add_task_gui())
        kb("<Control-e>",        lambda e: self.edit_task_gui())
        kb("<Delete>",           lambda e: self._shortcut_delete())
        kb("<Control-d>",        lambda e: self.mark_done_gui())
        # Undo / Redo
        kb("<Control-z>",        lambda e: self.undo_action())
        kb("<Control-y>",        lambda e: self.redo_action())
        kb("<Control-Z>",        lambda e: self.redo_action())   # Ctrl+Shift+Z
        # Navigation
        kb("<Control-f>",        lambda e: self._focus_search())
        kb("<Escape>",           lambda e: self._shortcut_escape())
        kb("<Control-Home>",     lambda e: self._select_first_task())
        kb("<Control-End>",      lambda e: self._select_last_task())
        # View
        kb("<Control-t>",        lambda e: self.toggle_theme())
        kb("<Control-comma>",    lambda e: self.open_settings_gui())
        # Help
        kb("<question>",         lambda e: self._show_shortcuts_help())
        self.apply_theme()
        self.refresh_tasks()
        self.auto_save()
        self.root.after(100, self._bind_cal_day_tooltips)
        self.root.after(300, self._start_tray)
        self.root.after(500,  self._start_reminders)
        self.root.after(800,  self._start_api_server)

    # ═══════════════════════════════════════════════
    #  UI BUILD
    # ═══════════════════════════════════════════════

    def _build_ui(self):
        # ── Header ──────────────────────────────────
        self.header_frame = tk.Frame(self.root)
        self.header_frame.pack(fill=tk.X, padx=18, pady=(14, 10))

        title_block = tk.Frame(self.header_frame)
        title_block.pack(side=tk.LEFT)
        self.title_label = tk.Label(
            title_block, text="My Tasks",
            font=("Georgia", 22, "bold")
        )
        self.title_label.pack(anchor="w")
        self.count_label = tk.Label(
            title_block, text="",
            font=("TkDefaultFont", 10)
        )
        self.count_label.pack(anchor="w")

        self.add_btn = tk.Button(
            self.header_frame, text="＋  Add Task",
            command=self.add_task_gui,
            font=("TkDefaultFont", 11, "bold"),
            relief="flat", cursor="hand2",
            padx=16, pady=8
        )
        self.add_btn.pack(side=tk.RIGHT, padx=(0, 2))

        # ── Workspace selector ──────────────────────────
        if self.username:
            self._build_workspace_chip()

        # ── User chip (only when logged in) ─────────
        if self.username:
            self._build_user_chip()

        # ── Header separator ────────────────────────
        self.sep1 = tk.Frame(self.root, height=1)
        self.sep1.pack(fill=tk.X)

        # ── Toolbar ─────────────────────────────────
        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(fill=tk.X)

        self.toolbar_inner = tk.Frame(self.toolbar)
        self.toolbar_inner.pack(fill=tk.X, padx=14, pady=8)

        # ── Single row: FILTER on left, SORT on right ────
        self.filter_row = self.toolbar_inner
        self.sort_row   = self.toolbar_inner

        # Left side — FILTER label + search + filter tabs
        self.filter_heading = tk.Label(
            self.toolbar_inner, text="FILTER",
            font=("TkDefaultFont", 8, "bold")
        )
        self.filter_heading.pack(side=tk.LEFT, padx=(0, 8))

        self.search_entry = tk.Entry(
            self.toolbar_inner,
            textvariable=self.search_var,
            width=18, relief="flat",
            font=("TkDefaultFont", 11)
        )
        self.search_entry.pack(side=tk.LEFT, ipady=5, padx=(0, 8))

        self.filter_buttons = {}
        for label in ["All", "Active", "Completed", "Overdue"]:
            btn = tk.Button(
                self.toolbar_inner, text=label,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10, "bold"),
                padx=10, pady=5,
                command=lambda v=label: self._set_filter(v)
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.filter_buttons[label] = btn

        # Right side — SORT tabs then SORT label (packed right-to-left)
        sort_options = [
            ("due_date",      "Due Date"),
            ("priority",      "Priority"),
            ("alphabetical",  "A – Z"),
            ("creation_date", "Created"),
        ]
        self.sort_buttons = {}
        for value, label in reversed(sort_options):
            btn = tk.Button(
                self.toolbar_inner, text=label,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10, "bold"),
                padx=10, pady=5,
                command=lambda v=value: self._set_sort(v)
            )
            btn.pack(side=tk.RIGHT, padx=2)
            self.sort_buttons[value] = btn

        self.sort_heading = tk.Label(
            self.toolbar_inner, text="SORT",
            font=("TkDefaultFont", 8, "bold")
        )
        self.sort_heading.pack(side=tk.RIGHT, padx=(0, 8))

        # vertical separator between filter and sort groups
        self.toolbar_divider = tk.Frame(self.toolbar_inner, width=1)
        self.toolbar_divider.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=4)

        # ── Toolbar separator ────────────────────────
        self.sep2 = tk.Frame(self.root, height=1)
        self.sep2.pack(fill=tk.X)

        # ── Footer separator + footer are packed BEFORE the treeview ──
        # This ensures pack(expand=True) on the tree only fills the space
        # that remains after the footer is already reserved at the bottom.

        # ── Footer separator ─────────────────────────
        self.sep3 = tk.Frame(self.root, height=1)
        self.sep3.pack(side=tk.BOTTOM, fill=tk.X)

        # ── Footer ───────────────────────────────────
        self.footer_frame = tk.Frame(self.root)
        self.footer_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=8)

        # Secondary action buttons (left)
        self.action_frame = tk.Frame(self.footer_frame)
        self.action_frame.pack(side=tk.LEFT)

        # Undo / Redo buttons
        self.undo_btn = tk.Button(
            self.action_frame, text="↩  Undo",
            command=self.undo_action,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.undo_btn.pack(side=tk.LEFT, padx=(0, 3))

        self.redo_btn = tk.Button(
            self.action_frame, text="↪  Redo",
            command=self.redo_action,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.redo_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Divider between undo/redo and task actions
        self.undo_divider = tk.Frame(self.action_frame, width=1)
        self.undo_divider.pack(side=tk.LEFT, fill=tk.Y, pady=4, padx=(0, 10))

        self.action_buttons = []
        for label, cmd in [
            ("✎  Edit",          self.edit_task_gui),
            ("✕  Delete",        self.delete_task_gui),
            ("✔  Mark Done",     self.mark_done_gui),
            ("📎  Attachments",  self.open_attachments_gui),
            ("◈  Subtasks",      self.open_subtasks_gui),
        ]:
            btn = tk.Button(
                self.action_frame, text=label, command=cmd,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10),
                padx=11, pady=5
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.action_buttons.append(btn)

        # Right side: save indicator + theme toggle
        self.right_frame = tk.Frame(self.footer_frame)
        self.right_frame.pack(side=tk.RIGHT)

        self.save_dot = tk.Label(
            self.right_frame, text="●",
            font=("TkDefaultFont", 10),
            fg="#4ADE80"   # always green — dot colour doesn't change with theme
        )
        self.save_dot.pack(side=tk.LEFT, padx=(0, 4))

        self.save_label = tk.Label(
            self.right_frame, text="Auto-save on",
            font=("TkDefaultFont", 10)
        )
        self.save_label.pack(side=tk.LEFT, padx=(0, 14))

        self.help_btn = tk.Button(
            self.right_frame, text="?",
            command=self._show_shortcuts_help,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10, "bold"),
            width=2, padx=6, pady=5
        )
        self.help_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.import_btn = tk.Button(
            self.right_frame, text="⬇  Import",
            command=self.open_import_gui,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.import_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.export_btn = tk.Button(
            self.right_frame, text="⬆  Export",
            command=self.open_export_gui,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.export_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.gantt_btn = tk.Button(
            self.right_frame, text="📊  Gantt",
            command=self.open_gantt_view,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.gantt_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.sync_btn = tk.Button(
            self.right_frame, text="☁️  Sync",
            command=self.open_cloud_sync_gui,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.sync_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.analytics_btn = tk.Button(
            self.right_frame, text="📈  Analytics",
            command=self.open_analytics_view,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.analytics_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.settings_btn = tk.Button(
            self.right_frame, text="⚙  Settings",
            command=self.open_settings_gui,
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 10),
            padx=11, pady=5
        )
        self.settings_btn.pack(side=tk.LEFT)

        # ── Main content: sidebar + task list side by side ──
        self.content_frame = tk.Frame(self.root)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar ──────────────────────────────────
        self.sidebar = tk.Frame(self.content_frame, width=220)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0), pady=10)
        self.sidebar.pack_propagate(False)

        # Scrollable canvas inside sidebar
        _sb_canvas = self._sb_canvas = tk.Canvas(self.sidebar, width=218, highlightthickness=0, bd=0)
        _sb_scroll  = ttk.Scrollbar(self.sidebar, orient="vertical", command=_sb_canvas.yview, style="Flat.Vertical.TScrollbar")
        _sb_canvas.configure(yscrollcommand=_sb_scroll.set)
        _sb_scroll.pack(side=tk.LEFT, fill=tk.Y)
        _sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame — all sidebar widgets go here
        _sb_inner = self._sb_inner = tk.Frame(_sb_canvas)
        _sb_win   = _sb_canvas.create_window((0, 0), window=_sb_inner, anchor="nw")

        def _sb_on_inner_resize(e):
            _sb_canvas.configure(scrollregion=_sb_canvas.bbox("all"))
        def _sb_on_canvas_resize(e):
            _sb_canvas.itemconfig(_sb_win, width=e.width)
        _sb_inner.bind("<Configure>", _sb_on_inner_resize)
        _sb_canvas.bind("<Configure>", _sb_on_canvas_resize)

        def _sb_mousewheel(e):
            _sb_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        _sb_canvas.bind("<Enter>", lambda e: _sb_canvas.bind_all("<MouseWheel>", _sb_mousewheel))
        _sb_canvas.bind("<Leave>", lambda e: _sb_canvas.unbind_all("<MouseWheel>"))

        # Use _sb_inner as the parent for all sidebar content
        sb = _sb_inner

        self.cal_label = tk.Label(
            sb, text="📅  Calendar",
            font=("TkDefaultFont", 10, "bold")
        )
        self.cal_label.pack(anchor="w", padx=6, pady=(0, 6))

        self.mini_cal = Calendar(
            sb,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            showweeknumbers=False,
            font=("TkDefaultFont", 9),
        )
        self.mini_cal.pack(fill=tk.X, padx=4)
        self.mini_cal.bind("<<CalendarSelected>>", self._on_calendar_day_click)
        # Tooltip state
        self._cal_tooltip_win  = None
        self._cal_tooltip_date = None
        # Rebind tooltips when user navigates month or year (bind after build)
        self.mini_cal.after(200, self._bind_nav_buttons)

        # "Show all" link below the calendar
        self.cal_reset_btn = tk.Button(
            sb, text="Show all tasks",
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 9),
            command=self._calendar_reset
        )
        self.cal_reset_btn.pack(pady=(6, 0))

        # ── Dashboard Stats Panel ─────────────────────
        self.stats_sep = tk.Frame(sb, height=1)
        self.stats_sep.pack(fill=tk.X, padx=8, pady=(14, 0))

        self.stats_label = tk.Label(
            sb, text="📊  Stats",
            font=("TkDefaultFont", 10, "bold")
        )
        self.stats_label.pack(anchor="w", padx=10, pady=(8, 6))

        self.stats_frame = tk.Frame(sb)
        self.stats_frame.pack(fill=tk.X, padx=8)

        # Each stat row: icon + label on left, value on right
        self._stat_widgets = {}
        stat_rows = [
            ("total",   "📋", "Total"),
            ("active",  "⏳", "Active"),
            ("done",    "✅", "Done"),
            ("overdue", "🔴", "Overdue"),
            ("today",   "📅", "Due today"),
            ("week",    "📆", "This week"),
        ]
        for key, icon, label in stat_rows:
            row = tk.Frame(self.stats_frame)
            row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=f"{icon}  {label}",
                           font=("TkDefaultFont", 9), anchor="w")
            lbl.pack(side=tk.LEFT)
            val = tk.Label(row, text="—",
                           font=("TkDefaultFont", 9, "bold"), anchor="e")
            val.pack(side=tk.RIGHT)
            self._stat_widgets[key] = (row, lbl, val)

        # Completion progress bar (canvas-drawn)
        self.progress_frame = tk.Frame(sb)
        self.progress_frame.pack(fill=tk.X, padx=10, pady=(10, 4))

        self.progress_header = tk.Frame(self.progress_frame)
        self.progress_header.pack(fill=tk.X)
        self.progress_title = tk.Label(
            self.progress_header, text="Completion",
            font=("TkDefaultFont", 8), anchor="w"
        )
        self.progress_title.pack(side=tk.LEFT)
        self.progress_pct_label = tk.Label(
            self.progress_header, text="0%",
            font=("TkDefaultFont", 8, "bold"), anchor="e"
        )
        self.progress_pct_label.pack(side=tk.RIGHT)

        self.progress_canvas = tk.Canvas(
            self.progress_frame, height=6, highlightthickness=0
        )
        self.progress_canvas.pack(fill=tk.X, pady=(3, 0))

        # ── Weekly Heatmap ────────────────────────────
        self.heatmap_sep = tk.Frame(sb, height=1)
        self.heatmap_sep.pack(fill=tk.X, padx=8, pady=(14, 0))

        heatmap_header = tk.Frame(sb)
        heatmap_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        self.heatmap_label = tk.Label(
            heatmap_header, text="📊  Activity",
            font=("TkDefaultFont", 10, "bold")
        )
        self.heatmap_label.pack(side=tk.LEFT)
        self.heatmap_range_lbl = tk.Label(
            heatmap_header, text="",
            font=("TkDefaultFont", 8)
        )
        self.heatmap_range_lbl.pack(side=tk.RIGHT)

        # Canvas: 13 weeks (~3 months). LEFT_PAD=14 for day labels, CELL=11, GAP=1 → 14+13×12=170px
        _HM_CELL =  9
        _HM_GAP  =  1
        _HM_COLS = 17
        _HM_ROWS =  7
        _HM_LPAD = 14
        hm_w = _HM_LPAD + _HM_COLS * (_HM_CELL + _HM_GAP)   # 170px
        hm_h = _HM_ROWS * (_HM_CELL + _HM_GAP) + 14
        self.heatmap_canvas = tk.Canvas(
            sb, width=hm_w, height=hm_h,
            highlightthickness=0, bd=0
        )
        self.heatmap_canvas.pack(padx=2, pady=(0, 4), anchor="w")
        self._heatmap_tip = {"win": None}

        # ── Category Filter Panel ────────────────────
        self.cat_sep = tk.Frame(sb, height=1)
        self.cat_sep.pack(fill=tk.X, padx=8, pady=(12, 0))

        cat_header_row = tk.Frame(sb)
        cat_header_row.pack(fill=tk.X, padx=10, pady=(8, 4))

        self.cat_heading = tk.Label(
            cat_header_row, text="🏷  Categories",
            font=("TkDefaultFont", 10, "bold")
        )
        self.cat_heading.pack(side=tk.LEFT)

        self.cat_filter_frame = tk.Frame(sb)
        self.cat_filter_frame.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._cat_filter_buttons = {}
        self._build_category_filter_buttons()


        # Vertical divider between sidebar and list
        self.sidebar_sep = tk.Frame(self.content_frame, width=1)
        self.sidebar_sep.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 0))

        # ── Task Treeview ────────────────────────────
        tree_frame = tk.Frame(self.content_frame)
        tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # "Done" is the first column so the checkbox sits on the left edge
        columns = ("Done", "Name", "Category", "Priority", "Due", "DaysLeft", "Description")
        self.task_tree = ttk.Treeview(
            tree_frame, columns=columns,
            show="tree headings", height=15
        )
        # Tree column (expand arrow) — slim
        self.task_tree.column("#0", width=22, minwidth=22, stretch=False)

        col_config = {
            "Done":        (40,  "center"),
            "Name":        (180, "w"),
            "Category":    (100, "center"),
            "Priority":    (80,  "center"),
            "Due":         (100, "center"),
            "DaysLeft":    (120, "center"),
            "Description": (260, "w"),
        }
        for col, (width, anchor) in col_config.items():
            self.task_tree.heading(col, text="" if col == "Done" else col)
            self.task_tree.column(col, width=width, anchor=anchor,
                                  minwidth=width if col == "Done" else 40)

        # Map column names to sort keys and bind click handlers
        self._col_sort_map = {
            "Name":        "alphabetical",
            "Category":    "category",
            "Priority":    "priority",
            "Due":         "due_date",
            "DaysLeft":    "due_date",
            "Description": "alphabetical",
        }
        for col in self._col_sort_map:
            self.task_tree.heading(
                col, text=col,
                command=lambda c=col: self._sort_by_column(c)
            )

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL,
            command=self.task_tree.yview,
            style="Flat.Vertical.TScrollbar",
        )
        self.task_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_tree.pack(fill=tk.BOTH, expand=True)

        # Single click on the Done column toggles completion immediately
        self.task_tree.bind("<Button-1>", self._on_tree_click)
        # Double-click anywhere else opens edit
        self.task_tree.bind("<Double-1>", lambda e: self.edit_task_gui())
        # Hover highlight
        self._hovered_row = None
        self.task_tree.bind("<Motion>",  self._on_tree_hover)
        self.task_tree.bind("<Leave>",   self._on_tree_leave)

    # ═══════════════════════════════════════════════
    #  FILTER HELPER
    # ═══════════════════════════════════════════════

    def _set_filter(self, value):
        self.filter_type.set(value)
        self._update_filter_buttons()
        self.refresh_tasks()

    def _set_sort(self, value):
        self.sort_type.set(value)
        self._update_sort_buttons()
        self.refresh_tasks()

    def _bind_hover(self, btn, is_active_fn, rest_bg=None, hover_bg=None):
        """Attach Enter/Leave hover highlight to any pill/toolbar button."""
        def on_enter(e):
            t = DARK_THEME if self.dark_mode else LIGHT_THEME
            if is_active_fn():
                btn.configure(bg=t["accent_hover"])
            else:
                btn.configure(bg=hover_bg or t["border"])
        def on_leave(e):
            t = DARK_THEME if self.dark_mode else LIGHT_THEME
            if is_active_fn():
                btn.configure(bg=t["accent"])
            else:
                btn.configure(bg=rest_bg or t["surface2"])
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def _bind_tooltip(self, widget, text_fn):
        """
        Show a small tooltip above the widget on hover.
        text_fn is a callable so the label is evaluated at hover time (always fresh).
        """
        tip = {"win": None}

        def show(e):
            msg = text_fn()
            if not msg:
                return
            t   = DARK_THEME if self.dark_mode else LIGHT_THEME
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=t["border"])
            tk.Label(
                win, text=msg,
                bg=t["surface2"], fg=t["fg"],
                font=("TkDefaultFont", 9),
                padx=10, pady=5,
            ).pack(padx=1, pady=1)
            win.update_idletasks()
            wx = widget.winfo_rootx()
            wy = widget.winfo_rooty()
            ww = win.winfo_reqwidth()
            wh = win.winfo_reqheight()
            win.geometry(f"+{wx}+{wy - wh - 4}")
            tip["win"] = win

        def hide(e):
            if tip["win"]:
                try:
                    tip["win"].destroy()
                except Exception:
                    pass
                tip["win"] = None

        widget.bind("<Enter>", lambda e: (hide(e), show(e)), add="+")
        widget.bind("<Leave>", hide, add="+")

    def _update_filter_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        active = self.filter_type.get()
        for label, btn in self.filter_buttons.items():
            if label == active:
                btn.configure(
                    bg=t["accent"], fg=t["accent_fg"],
                    activebackground=t["accent_hover"],
                    activeforeground=t["accent_fg"]
                )
            else:
                btn.configure(
                    bg=t["surface2"], fg=t["muted_fg"],
                    activebackground=t["border"],
                    activeforeground=t["fg"]
                )
            self._bind_hover(btn, lambda lbl=label: self.filter_type.get() == lbl)

    def _update_sort_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        active = self.sort_type.get()
        for value, btn in self.sort_buttons.items():
            if value == active:
                btn.configure(
                    bg=t["accent"], fg=t["accent_fg"],
                    activebackground=t["accent_hover"],
                    activeforeground=t["accent_fg"]
                )
            else:
                btn.configure(
                    bg=t["surface2"], fg=t["muted_fg"],
                    activebackground=t["border"],
                    activeforeground=t["fg"]
                )
            self._bind_hover(btn, lambda val=value: self.sort_type.get() == val)

    # ═══════════════════════════════════════════════
    #  THEME
    # ═══════════════════════════════════════════════

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.save_ui_config()
        self.apply_theme()

    def apply_theme(self):
        # Skip if theme hasn't changed (prevents redundant widget reconfiguration)
        _cache_key = ("dark" if self.dark_mode else "light")
        if getattr(self, "_last_applied_theme", None) == _cache_key:
            return
        self._last_applied_theme = _cache_key
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        self.root.configure(bg=t["bg"])

        # Header
        for w in [self.header_frame, self.title_label.master]:
            w.configure(bg=t["bg"])
        self.title_label.configure(bg=t["bg"], fg=t["fg"])
        self.count_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.add_btn.configure(
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"],
            activeforeground=t["accent_fg"]
        )
        self._bind_hover(self.add_btn, lambda: True)

        # Rebuild user chip for new theme colours
        if self.username and hasattr(self, "_user_chip"):
            self._user_chip.destroy()
            self._build_user_chip()
        # Rebuild workspace chip for new theme colours
        if self.username and hasattr(self, "_ws_chip"):
            self._build_workspace_chip()

        # Separators
        for sep in [self.sep1, self.sep2, self.sep3]:
            sep.configure(bg=t["border"])

        # Toolbar
        self.toolbar.configure(bg=t["surface2"])
        self.toolbar_inner.configure(bg=t["surface2"])
        self.toolbar_divider.configure(bg=t["border"])
        self.filter_heading.configure(bg=t["surface2"], fg=t["muted_fg"])
        self.sort_heading.configure(bg=t["surface2"], fg=t["muted_fg"])
        self.search_entry.configure(
            bg=t["entry_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            highlightthickness=1,
            highlightbackground=t["border"],
            highlightcolor=t["accent"]
        )
        self.sort_label = None  # removed — no longer used
        self._update_filter_buttons()
        self._update_sort_buttons()

        # Sidebar
        self.sidebar.configure(bg=t["bg"])
        self.sidebar_sep.configure(bg=t["border"])
        self.content_frame.configure(bg=t["bg"])
        # Theme the scrollable canvas and inner frame
        self._sb_canvas.configure(bg=t["bg"])
        self._sb_inner.configure(bg=t["bg"])
        self.cal_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.cal_reset_btn.configure(
            bg=t["bg"], fg=t["accent"],
            activebackground=t["bg"], activeforeground=t["accent_hover"]
        )
        self.mini_cal.configure(
            background=t["surface2"],
            foreground=t["fg"],
            headersbackground=t["surface"],
            headersforeground=t["muted_fg"],
            selectbackground=t["accent"],
            selectforeground=t["accent_fg"],
            normalbackground=t["surface2"],
            normalforeground=t["fg"],
            weekendbackground=t["surface"],
            weekendforeground=t["fg"],
            othermonthbackground=t["bg"],
            othermonthforeground=t["muted_fg"],
            bordercolor=t["border"],
            tooltipbackground=t["surface2"],
            tooltipforeground=t["fg"],
        )
        self.refresh_calendar()

        # Stats panel
        self.stats_sep.configure(bg=t["border"])
        self.stats_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.stats_frame.configure(bg=t["bg"])
        self.progress_frame.configure(bg=t["bg"])
        self.progress_header.configure(bg=t["bg"])
        self.progress_title.configure(bg=t["bg"], fg=t["muted_fg"])
        self.progress_pct_label.configure(bg=t["bg"], fg=t["fg"])
        self.progress_canvas.configure(bg=t["bg"])
        for key, (row, lbl, val) in self._stat_widgets.items():
            row.configure(bg=t["bg"])
            lbl.configure(bg=t["bg"], fg=t["muted_fg"])
            val.configure(bg=t["bg"], fg=t["fg"])
        self.refresh_stats()

        # Heatmap
        self.heatmap_sep.configure(bg=t["border"])
        self.heatmap_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.heatmap_range_lbl.configure(bg=t["bg"], fg=t["muted_fg"])
        self.heatmap_canvas.configure(bg=t["bg"])
        self.heatmap_canvas.master.configure(bg=t["bg"])

        # Category filter panel
        self.cat_sep.configure(bg=t["border"])
        self.cat_heading.configure(bg=t["bg"], fg=t["muted_fg"])
        cat_header_row = self.cat_heading.master
        cat_header_row.configure(bg=t["bg"])

        self.cat_filter_frame.configure(bg=t["bg"])
        self._build_category_filter_buttons()

        # Footer
        for w in [self.footer_frame, self.action_frame, self.right_frame]:
            w.configure(bg=t["bg"])
        self.undo_divider.configure(bg=t["border"])
        for btn in [self.undo_btn, self.redo_btn] + self.action_buttons:
            btn.configure(
                bg=t["secondary_btn_bg"], fg=t["secondary_btn_fg"],
                activebackground=t["border"],
                activeforeground=t["fg"]
            )
            self._bind_hover(btn, lambda: False,
                             rest_bg=t["secondary_btn_bg"], hover_bg=t["border"])
        self._update_undo_redo_buttons()
        self.save_dot.configure(bg=t["bg"])
        self.save_label.configure(bg=t["bg"], fg=t["muted_fg"])
        self.help_btn.configure(
            bg=t["surface2"], fg=t["accent"],
            activebackground=t["border"], activeforeground=t["accent"]
        )
        self._bind_hover(self.help_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.import_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"]
        )
        self._bind_hover(self.import_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.export_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"]
        )
        self._bind_hover(self.export_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.gantt_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"],
        )
        self._bind_hover(self.gantt_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.sync_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"],
        )
        self._bind_hover(self.sync_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.analytics_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"], activeforeground=t["fg"],
        )
        self._bind_hover(self.analytics_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])
        self.settings_btn.configure(
            bg=t["surface2"], fg=t["muted_fg"],
            activebackground=t["border"],
            activeforeground=t["fg"],
        )
        self._bind_hover(self.settings_btn, lambda: False,
                         rest_bg=t["surface2"], hover_bg=t["border"])

        # Treeview
        style = ttk.Style()
        # Use ttkbootstrap if loaded, otherwise fall back to "default"
        try:
            import ttkbootstrap as _bs
            _bs_theme = "darkly" if self.dark_mode else "flatly"
            style.theme_use(_bs_theme)
        except (ImportError, Exception):
            style.theme_use("default")

        style.configure(
            "Treeview",
            background=t["surface"],
            foreground=t["list_fg"],
            fieldbackground=t["surface"],
            rowheight=30,
            font=("TkDefaultFont", 11),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=t["surface2"],
            foreground=t["heading_fg"],
            font=("TkDefaultFont", 10, "bold"),
            relief="flat",
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", t["accent"])],
            foreground=[("selected", t["accent_fg"])]
        )
        style.configure(
            "Vertical.TScrollbar",
            background=t["surface2"],
            troughcolor=t["bg"],
            arrowcolor=t["muted_fg"],
            relief="flat",
            borderwidth=0,
        )
        # Flat custom scrollbar — immune to maximize resets
        style.layout("Flat.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {
                "sticky": "ns",
                "children": [
                    ("Vertical.Scrollbar.thumb", {"unit": "1", "sticky": "nswe"}),
                ],
            }),
        ])
        style.configure(
            "Flat.Vertical.TScrollbar",
            background=t["surface2"],
            troughcolor=t["bg"],
            bordercolor=t["bg"],
            darkcolor=t["surface2"],
            lightcolor=t["surface2"],
            arrowcolor=t["bg"],
            relief="flat",
            borderwidth=0,
            width=8,
        )
        style.map(
            "Flat.Vertical.TScrollbar",
            background=[
                ("pressed",  t["accent"]),
                ("active",   t["muted_fg"]),
                ("!active",  t["border"]),
            ],
        )

        # ── ttkbootstrap-specific enhancements ────────────────────────────────
        try:
            import ttkbootstrap as _bs
            # Rounded accent buttons via bootstyle
            style.configure(
                "Accent.TButton",
                font=("TkDefaultFont", 10, "bold"),
                padding=(12, 6),
            )
            # Modern entry fields
            style.configure(
                "TEntry",
                fieldbackground=t["entry_bg"],
                foreground=t["fg"],
                insertcolor=t["fg"],
                bordercolor=t["border"],
                lightcolor=t["border"],
                darkcolor=t["border"],
            )
            # Combobox matches entry
            style.configure(
                "TCombobox",
                fieldbackground=t["entry_bg"],
                foreground=t["fg"],
                selectbackground=t["accent"],
                selectforeground=t["accent_fg"],
            )
            # Notebook tabs (if used later)
            style.configure(
                "TNotebook",
                background=t["bg"],
                tabmargins=[2, 4, 0, 0],
            )
            style.configure(
                "TNotebook.Tab",
                background=t["surface"],
                foreground=t["muted_fg"],
                padding=[12, 6],
                font=("TkDefaultFont", 9),
            )
            style.map(
                "TNotebook.Tab",
                background=[("selected", t["surface2"])],
                foreground=[("selected", t["fg"])],
            )
        except ImportError:
            pass   # ttkbootstrap not installed — base theme only
        self._tags_configured = False
        self._configure_tags()
        self._tags_configured = True

    def _configure_tags(self):
        if self.dark_mode:
            self.task_tree.tag_configure("hover",   background="#2C3240")
            self.task_tree.tag_configure("done",    foreground="#4A4E5A")
            self.task_tree.tag_configure("overdue", foreground="#F87171")
            self.task_tree.tag_configure("high",    foreground="#F87171")
            self.task_tree.tag_configure("medium",  foreground="#FCD34D")
            self.task_tree.tag_configure("low",     foreground="#6EE7A0")
        else:
            self.task_tree.tag_configure("hover",   background="#EDE8E1")
            self.task_tree.tag_configure("done",    foreground="#B0AAA4")
            self.task_tree.tag_configure("overdue", foreground="#DC2626")
            self.task_tree.tag_configure("high",    foreground="#B91C1C")
            self.task_tree.tag_configure("medium",  foreground="#B45309")
            self.task_tree.tag_configure("low",     foreground="#4D7C5F")

    def _save_async(self):
        """Save tasks in a background thread — non-blocking for the UI."""
        t = threading.Thread(
            target=save_tasks,
            args=(self.manager, self.username, self.enc_key),
            kwargs={"workspace": self.workspace},
            daemon=True,
        )
        t.start()

    def save_ui_config(self):
        save_config({
            "dark_mode":         self.dark_mode,
            "sort":              self.sort_type.get(),
            "filter":            self.filter_type.get(),
            "geometry":          self.root.geometry(),
            "categories":        self.categories,
            "category_colors":   self.category_colors,
            "minimize_to_tray":  self.minimize_to_tray,
            "reminders":         self.reminder_cfg,
            "api":               self.api_cfg,
        }, self.username)

    # ═══════════════════════════════════════════════
    #  CATEGORIES
    # ═══════════════════════════════════════════════

    def _build_workspace_chip(self):
        """Workspace selector pill in the header."""
        from core.workspaces import list_workspaces
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        wss = list_workspaces(self.username)
        ws_colors = {w["name"]: w.get("color", t["accent"]) for w in wss}

        if hasattr(self, "_ws_chip") and self._ws_chip:
            try: self._ws_chip.destroy()
            except: pass

        chip = tk.Frame(self.header_frame, bg=t["surface"], cursor="hand2")
        chip.pack(side=tk.RIGHT, padx=(0, 8))
        self._ws_chip = chip

        color = ws_colors.get(self.workspace, t["accent"])
        dot = tk.Label(chip, text="●", font=("TkDefaultFont", 10),
                       bg=t["surface"], fg=color)
        dot.pack(side=tk.LEFT, padx=(8, 4), pady=6)
        lbl = tk.Label(chip, text=self.workspace,
                       font=("TkDefaultFont", 10, "bold"),
                       bg=t["surface"], fg=t["fg"])
        lbl.pack(side=tk.LEFT)
        arrow = tk.Label(chip, text="▾", font=("TkDefaultFont", 9),
                         bg=t["surface"], fg=t["muted_fg"])
        arrow.pack(side=tk.LEFT, padx=(2, 8), pady=6)

        def _show_menu(event=None):
            menu = tk.Menu(self.root, tearoff=0,
                           bg=t["surface2"], fg=t["fg"],
                           activebackground=t["accent"],
                           activeforeground=t["accent_fg"],
                           relief="flat", bd=0)
            for ws in wss:
                n = ws["name"]
                menu.add_command(
                    label=("✓  " if n == self.workspace else "     ") + n,
                    command=lambda name=n: self._switch_workspace(name),
                )
            menu.add_separator()
            menu.add_command(label="⚙  Manage Workspaces…",
                             command=self.open_workspaces_gui)
            try:
                menu.tk_popup(chip.winfo_rootx(),
                              chip.winfo_rooty() + chip.winfo_height())
            finally:
                menu.grab_release()

        for w in (chip, dot, lbl, arrow):
            w.bind("<Button-1>", _show_menu)

    def _switch_workspace(self, name: str):
        """Save current workspace, load the new one, refresh."""
        from core.workspaces import set_active_workspace
        # Save current tasks first
        save_tasks(self.manager, self.username, self.enc_key,
                   workspace=self.workspace)
        # Switch
        self.workspace = name
        if self.username:
            set_active_workspace(self.username, name)
        # Reload tasks for new workspace
        self.manager.tasks.clear()
        self.history = CommandHistory()
        load_tasks(self.manager, self.username, self.enc_key,
                   workspace=self.workspace)
        self._update_title()
        self._build_workspace_chip()
        self.refresh_tasks()
        self.refresh_stats()

    def open_workspaces_gui(self):
        """Workspace management dialog — list, create, edit, delete."""
        from core.workspaces import (list_workspaces, create_workspace,
                                     delete_workspace, update_workspace)
        t   = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = self._make_dialog("📁  Workspaces")
        top.geometry("520x580")
        top.resizable(False, True)

        err_col = "#F87171" if self.dark_mode else "#DC2626"
        ok_col  = "#4ADE80" if self.dark_mode else "#16A34A"

        _COLORS = ["#E07A47","#4A9EE0","#6EE7A0","#FCD34D","#C084FC","#F87171","#38BDF8","#A78BFA"]

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="📁  Workspaces",
                 font=("TkDefaultFont", 12, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=16, pady=(12, 2))
        tk.Label(hdr, text="Each workspace keeps its own independent task list",
                 font=("TkDefaultFont", 9), bg=t["surface"],
                 fg=t["muted_fg"]).pack(anchor="w", padx=16, pady=(0, 10))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Scrollable workspace list ─────────────────────────────────────────
        list_canvas_frame = tk.Frame(top, bg=t["bg"])
        list_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(10, 0))

        list_canvas = tk.Canvas(list_canvas_frame, bg=t["bg"],
                                highlightthickness=0, bd=0)
        list_scroll  = ttk.Scrollbar(list_canvas_frame, orient=tk.VERTICAL,
                                     command=list_canvas.yview,
                                     style="Flat.Vertical.TScrollbar")
        list_canvas.configure(yscrollcommand=list_scroll.set)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_inner = tk.Frame(list_canvas, bg=t["bg"])
        list_win   = list_canvas.create_window((0,0), window=list_inner, anchor="nw")
        list_canvas.bind("<Configure>", lambda e: list_canvas.itemconfig(list_win, width=e.width))
        list_inner.bind("<Configure>", lambda e: list_canvas.configure(
            scrollregion=list_canvas.bbox("all")))

        # Global message label
        msg_var = tk.StringVar()
        msg_lbl = tk.Label(top, textvariable=msg_var,
                           font=("TkDefaultFont", 9),
                           bg=t["bg"], fg=ok_col, wraplength=480)
        msg_lbl.pack(anchor="w", padx=14, pady=(2, 0))

        def _set_msg(text, ok=True):
            msg_var.set(text)
            msg_lbl.configure(fg=ok_col if ok else err_col)
            top.after(2500, lambda: msg_var.set(""))

        # ── Edit sub-form (shown inline when editing) ─────────────────────────
        _editing = {"name": None}   # tracks which workspace is being edited

        def _rebuild():
            for w in list_inner.winfo_children():
                w.destroy()

            for ws in list_workspaces(self.username):
                is_active  = ws["name"] == self.workspace
                is_default = ws["name"] == "Default"
                color      = ws.get("color", t["accent"])

                card = tk.Frame(list_inner, bg=t["surface2"],
                                highlightthickness=1, highlightbackground=t["border"])
                card.pack(fill=tk.X, pady=3, padx=2)

                # ── Main row ──────────────────────────────────────────────────
                main_row = tk.Frame(card, bg=t["surface2"])
                main_row.pack(fill=tk.X, padx=8, pady=6)

                tk.Label(main_row, text="●", fg=color, bg=t["surface2"],
                         font=("TkDefaultFont", 13)).pack(side=tk.LEFT, padx=(4, 8))

                info_block = tk.Frame(main_row, bg=t["surface2"])
                info_block.pack(side=tk.LEFT, fill=tk.X, expand=True)

                name_row_w = tk.Frame(info_block, bg=t["surface2"])
                name_row_w.pack(anchor="w")
                tk.Label(name_row_w,
                         text=ws["name"] + ("  ✦ active" if is_active else ""),
                         font=("TkDefaultFont", 10, "bold"),
                         bg=t["surface2"],
                         fg=t["accent"] if is_active else t["fg"]).pack(side=tk.LEFT)

                desc = ws.get("description") or ""
                tk.Label(info_block,
                         text=desc if desc else "No description",
                         font=("TkDefaultFont", 8),
                         bg=t["surface2"],
                         fg=t["muted_fg"]).pack(anchor="w")

                # ── Action buttons ─────────────────────────────────────────
                btn_block = tk.Frame(main_row, bg=t["surface2"])
                btn_block.pack(side=tk.RIGHT, padx=(6, 0))

                if not is_active:
                    def _switch_ws(n=ws["name"]):
                        top.destroy()
                        self._switch_workspace(n)
                    tk.Button(btn_block, text="Switch",
                              command=_switch_ws,
                              bg=t["accent"], fg=t["accent_fg"],
                              relief=tk.FLAT, cursor="hand2",
                              font=("TkDefaultFont", 8, "bold"),
                              padx=8, pady=3).pack(side=tk.LEFT, padx=2)

                def _toggle_edit(n=ws["name"], c=card):
                    # Show/hide inline edit panel for this card
                    edit_frame = getattr(c, "_edit_frame", None)
                    if edit_frame and edit_frame.winfo_exists():
                        edit_frame.destroy()
                        c._edit_frame = None
                    else:
                        _show_edit_panel(c, n)

                tk.Button(btn_block, text="✎ Edit",
                          command=_toggle_edit,
                          bg=t["surface"], fg=t["fg"],
                          relief=tk.FLAT, cursor="hand2",
                          font=("TkDefaultFont", 8),
                          padx=6, pady=3).pack(side=tk.LEFT, padx=2)

                if not is_default:
                    def _del(n=ws["name"]):
                        if messagebox.askyesno("Delete workspace",
                                f"Delete workspace '{n}'?\n"
                                "Its task file will also be deleted.",
                                parent=top):
                            try:
                                delete_workspace(self.username, n)
                                _rebuild()
                                _set_msg(f"✓ '{n}' deleted.")
                                self._build_workspace_chip()
                            except Exception as e:
                                _set_msg(str(e), ok=False)
                    tk.Button(btn_block, text="🗑",
                              command=_del,
                              bg=t["surface2"], fg=err_col,
                              relief=tk.FLAT, cursor="hand2",
                              font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=2)

        def _show_edit_panel(card, ws_name):
            """Inline edit panel attached to a workspace card."""
            ws_list = list_workspaces(self.username)
            ws_data = next((w for w in ws_list if w["name"] == ws_name), {})

            ef = tk.Frame(card, bg=t["surface"],
                          highlightthickness=1, highlightbackground=t["border"])
            ef.pack(fill=tk.X, padx=8, pady=(0, 8))
            card._edit_frame = ef

            tk.Label(ef, text="Edit workspace",
                     font=("TkDefaultFont", 9, "bold"),
                     bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=8, pady=(6, 4))

            # Name field (disabled for Default)
            fields_row = tk.Frame(ef, bg=t["surface"])
            fields_row.pack(fill=tk.X, padx=8, pady=(0, 6))

            tk.Label(fields_row, text="Name:", font=("TkDefaultFont", 9),
                     bg=t["surface"], fg=t["muted_fg"], width=6, anchor="w").grid(
                row=0, column=0, sticky="w", pady=3)
            name_var = tk.StringVar(value=ws_data.get("name", ""))
            name_e = tk.Entry(fields_row, textvariable=name_var, width=22,
                              bg=t["entry_bg"], fg=t["fg"],
                              insertbackground=t["fg"], relief=tk.FLAT,
                              font=("TkDefaultFont", 9),
                              highlightthickness=1, highlightbackground=t["border"],
                              state="disabled" if ws_name == "Default" else "normal")
            name_e.grid(row=0, column=1, sticky="w", padx=(4, 0), pady=3)

            tk.Label(fields_row, text="Desc:", font=("TkDefaultFont", 9),
                     bg=t["surface"], fg=t["muted_fg"], width=6, anchor="w").grid(
                row=1, column=0, sticky="w", pady=3)
            desc_var = tk.StringVar(value=ws_data.get("description", ""))
            tk.Entry(fields_row, textvariable=desc_var, width=22,
                     bg=t["entry_bg"], fg=t["fg"],
                     insertbackground=t["fg"], relief=tk.FLAT,
                     font=("TkDefaultFont", 9),
                     highlightthickness=1, highlightbackground=t["border"]
                     ).grid(row=1, column=1, sticky="w", padx=(4, 0), pady=3)

            # Color picker
            tk.Label(fields_row, text="Color:", font=("TkDefaultFont", 9),
                     bg=t["surface"], fg=t["muted_fg"], width=6, anchor="w").grid(
                row=2, column=0, sticky="w", pady=3)
            col_frame = tk.Frame(fields_row, bg=t["surface"])
            col_frame.grid(row=2, column=1, sticky="w", padx=(4, 0), pady=3)
            cur_color = ws_data.get("color", _COLORS[0])
            col_var = tk.StringVar(value=cur_color)

            def _pick_color(cc, col_frame=col_frame, col_var=col_var):
                col_var.set(cc)
                for w in col_frame.winfo_children():
                    w.configure(relief="sunken" if w["bg"] == cc else "flat")

            for c in _COLORS:
                relief = "sunken" if c == cur_color else "flat"
                b = tk.Label(col_frame, bg=c, width=2, cursor="hand2", relief=relief,
                             highlightthickness=1,
                             highlightbackground="white" if c == cur_color else t["border"])
                b.pack(side=tk.LEFT, padx=1)
                b.bind("<Button-1>", lambda e, cc=c: _pick_color(cc))

            edit_msg = tk.StringVar()
            tk.Label(ef, textvariable=edit_msg, font=("TkDefaultFont", 8),
                     bg=t["surface"], fg=err_col).pack(anchor="w", padx=8)

            btn_row_ef = tk.Frame(ef, bg=t["surface"])
            btn_row_ef.pack(anchor="e", padx=8, pady=(0, 8))

            def _save_edit():
                new_name = name_var.get().strip() if ws_name != "Default" else ws_name
                new_desc = desc_var.get().strip()
                new_col  = col_var.get()
                try:
                    update_workspace(self.username, ws_name,
                                     new_name=new_name if new_name != ws_name else None,
                                     description=new_desc,
                                     color=new_col)
                    # If active workspace was renamed, update app state
                    if self.workspace == ws_name and new_name != ws_name:
                        self.workspace = new_name
                        self._update_title()
                    self._build_workspace_chip()
                    _rebuild()
                    _set_msg(f"✓ '{new_name}' updated.")
                except Exception as e:
                    edit_msg.set(str(e))

            tk.Button(btn_row_ef, text="Save", command=_save_edit,
                      bg=t["accent"], fg=t["accent_fg"],
                      relief=tk.FLAT, cursor="hand2",
                      font=("TkDefaultFont", 8, "bold"),
                      padx=8).pack(side=tk.LEFT, padx=(0, 4))
            tk.Button(btn_row_ef, text="Cancel",
                      command=lambda: ef.destroy(),
                      bg=t["surface2"], fg=t["fg"],
                      relief=tk.FLAT, cursor="hand2",
                      font=("TkDefaultFont", 8),
                      padx=8).pack(side=tk.LEFT)

        _rebuild()

        # ── Create new workspace ──────────────────────────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X, padx=0, pady=(6, 0))
        new_frame = tk.Frame(top, bg=t["surface"])
        new_frame.pack(fill=tk.X, padx=0, pady=0)

        tk.Label(new_frame, text="Create new workspace",
                 font=("TkDefaultFont", 10, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=16, pady=(10, 6))

        fields = tk.Frame(new_frame, bg=t["surface"])
        fields.pack(fill=tk.X, padx=16, pady=(0, 6))

        # Row 1: Name + Description
        r1 = tk.Frame(fields, bg=t["surface"])
        r1.pack(fill=tk.X, pady=2)
        tk.Label(r1, text="Name:", font=("TkDefaultFont", 9),
                 bg=t["surface"], fg=t["muted_fg"], width=6, anchor="w").pack(side=tk.LEFT)
        new_name_var = tk.StringVar()
        new_name_e = tk.Entry(r1, textvariable=new_name_var, width=18,
                              bg=t["entry_bg"], fg=t["fg"],
                              insertbackground=t["fg"], relief=tk.FLAT,
                              font=("TkDefaultFont", 9),
                              highlightthickness=1, highlightbackground=t["border"])
        new_name_e.pack(side=tk.LEFT, padx=(4, 12))
        tk.Label(r1, text="Desc:", font=("TkDefaultFont", 9),
                 bg=t["surface"], fg=t["muted_fg"], width=5, anchor="w").pack(side=tk.LEFT)
        new_desc_var = tk.StringVar()
        tk.Entry(r1, textvariable=new_desc_var, width=18,
                 bg=t["entry_bg"], fg=t["fg"],
                 insertbackground=t["fg"], relief=tk.FLAT,
                 font=("TkDefaultFont", 9),
                 highlightthickness=1, highlightbackground=t["border"]
                 ).pack(side=tk.LEFT, padx=(4, 0))

        # Row 2: Colour + Create button
        r2 = tk.Frame(fields, bg=t["surface"])
        r2.pack(fill=tk.X, pady=4)
        tk.Label(r2, text="Color:", font=("TkDefaultFont", 9),
                 bg=t["surface"], fg=t["muted_fg"], width=6, anchor="w").pack(side=tk.LEFT)
        col_picker = tk.Frame(r2, bg=t["surface"])
        col_picker.pack(side=tk.LEFT, padx=(4, 12))
        new_col_var = tk.StringVar(value=_COLORS[1])

        def _pick_new(cc):
            new_col_var.set(cc)
            for w in col_picker.winfo_children():
                w.configure(relief="sunken" if w["bg"] == cc else "flat",
                             highlightbackground="white" if w["bg"] == cc else t["border"])

        for c in _COLORS:
            b = tk.Label(col_picker, bg=c, width=2, cursor="hand2",
                         relief="sunken" if c == _COLORS[1] else "flat",
                         highlightthickness=1,
                         highlightbackground="white" if c == _COLORS[1] else t["border"])
            b.pack(side=tk.LEFT, padx=1)
            b.bind("<Button-1>", lambda e, cc=c: _pick_new(cc))

        def _create():
            name = new_name_var.get().strip()
            if not name:
                _set_msg("Enter a workspace name.", ok=False)
                return
            try:
                create_workspace(self.username, name,
                                 description=new_desc_var.get().strip(),
                                 color=new_col_var.get())
                new_name_var.set("")
                new_desc_var.set("")
                _rebuild()
                _set_msg(f"✓ '{name}' created.")
                self._build_workspace_chip()
            except Exception as e:
                _set_msg(str(e), ok=False)

        tk.Button(r2, text="Create workspace", command=_create,
                  bg=t["accent"], fg=t["accent_fg"],
                  activebackground=t["accent_hover"],
                  relief=tk.FLAT, cursor="hand2",
                  font=("TkDefaultFont", 9, "bold"), padx=10, pady=4).pack(side=tk.LEFT)
        new_name_e.bind("<Return>", lambda e: _create())

        # ── Footer ────────────────────────────────────────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=50)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Button(foot, text="Close", command=top.destroy,
                  relief="flat", cursor="hand2",
                  bg=t["accent"], fg=t["accent_fg"],
                  font=("TkDefaultFont", 10, "bold")
                  ).place(x=14, y=8, relwidth=1.0, width=-28, height=34)

    def _update_title(self):
        ws_suffix = f"  ·  {self.workspace}" if self.workspace != "Default" else ""
        base = f"My Tasks — {self.username}" if self.username else "My Tasks"
        self.root.title(f"{base}{ws_suffix}")

    def _build_user_chip(self):
        """Build the username/email chip in the header (right of Add Task)."""
        from core.auth import get_user_info
        t    = DARK_THEME if self.dark_mode else LIGHT_THEME
        info = get_user_info(self.username)

        chip = tk.Frame(self.header_frame, bg=t["surface"],
                        cursor="hand2")
        chip.pack(side=tk.RIGHT, padx=(0, 10))
        chip.bind("<Button-1>", lambda e: self.open_user_settings())

        # Avatar circle (initials)
        initial = info["display_name"][0].upper() if info["display_name"] else "?"
        av = tk.Label(chip, text=initial,
                      font=("TkDefaultFont", 11, "bold"),
                      bg=t["accent"], fg=t["accent_fg"],
                      width=2, relief="flat")
        av.pack(side=tk.LEFT, padx=(6, 4), pady=4)
        av.bind("<Button-1>", lambda e: self.open_user_settings())

        # Text block
        text_block = tk.Frame(chip, bg=t["surface"])
        text_block.pack(side=tk.LEFT, padx=(0, 8), pady=4)
        text_block.bind("<Button-1>", lambda e: self.open_user_settings())

        name_lbl = tk.Label(text_block, text=info["display_name"],
                            font=("TkDefaultFont", 10, "bold"),
                            bg=t["surface"], fg=t["fg"], cursor="hand2")
        name_lbl.pack(anchor="w")
        name_lbl.bind("<Button-1>", lambda e: self.open_user_settings())

        email_lbl = tk.Label(text_block,
                             text=info["email"] or "",
                             font=("TkDefaultFont", 8),
                             bg=t["surface"], fg=t["muted_fg"], cursor="hand2")
        email_lbl.pack(anchor="w")
        email_lbl.bind("<Button-1>", lambda e: self.open_user_settings())

        self._user_chip = chip

    def open_user_settings(self):
        """User profile / account settings dialog."""
        from core.auth import (get_user_info, update_username,
                               update_email, update_password)
        from gui.login import _load_remembered, _save_remembered, _clear_remembered

        t   = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = self._make_dialog("Account Settings")
        top.resizable(False, False)
        top.geometry("400x560")

        # ── Header ────────────────────────────────────
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        info    = get_user_info(self.username)
        initial = info["display_name"][0].upper() if info["display_name"] else "?"

        av = tk.Label(hdr, text=initial,
                      font=("TkDefaultFont", 22, "bold"),
                      bg=t["accent"], fg=t["accent_fg"],
                      width=2)
        av.pack(side=tk.LEFT, padx=(18, 12), pady=14)

        title_block = tk.Frame(hdr, bg=t["surface"])
        title_block.pack(side=tk.LEFT, pady=14)
        tk.Label(title_block, text=info["display_name"],
                 font=("TkDefaultFont", 13, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w")
        tk.Label(title_block, text=info["email"] or "",
                 font=("TkDefaultFont", 9),
                 bg=t["surface"], fg=t["muted_fg"]).pack(anchor="w")

        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Scrollable body ───────────────────────────
        canvas_frame = tk.Frame(top, bg=t["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg=t["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical",
                                  command=canvas.yview, style="Flat.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        pad = tk.Frame(canvas, bg=t["bg"])
        pad_win = canvas.create_window((0, 0), window=pad, anchor="nw")

        def _on_canvas_resize(e):
            canvas.itemconfig(pad_win, width=e.width)
        def _on_pad_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _on_canvas_resize)
        pad.bind("<Configure>", _on_pad_resize)

        def _mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        inner = tk.Frame(pad, bg=t["bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=10)

        def section(label):
            tk.Label(inner, text=label,
                     font=("TkDefaultFont", 9, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(14, 4))
            tk.Frame(inner, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        def field(parent, label):
            tk.Label(parent, text=label,
                     font=("TkDefaultFont", 9),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
            var = tk.StringVar()
            e = tk.Entry(parent, textvariable=var,
                         bg=t["entry_bg"], fg=t["fg"],
                         insertbackground=t["fg"],
                         relief=tk.FLAT, font=("TkDefaultFont", 10),
                         highlightthickness=1,
                         highlightbackground=t["border"],
                         highlightcolor=t["accent"])
            e.pack(fill=tk.X, pady=(3, 8))
            return var, e

        def pw_field(parent, label):
            tk.Label(parent, text=label,
                     font=("TkDefaultFont", 9),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")
            var = tk.StringVar()
            e = tk.Entry(parent, textvariable=var, show="●",
                         bg=t["entry_bg"], fg=t["fg"],
                         insertbackground=t["fg"],
                         relief=tk.FLAT, font=("TkDefaultFont", 10),
                         highlightthickness=1,
                         highlightbackground=t["border"],
                         highlightcolor=t["accent"])
            e.pack(fill=tk.X, pady=(3, 8))
            return var

        def msg_label(parent):
            v = tk.StringVar()
            err_color = "#F87171" if self.dark_mode else "#DC2626"
            tk.Label(parent, textvariable=v,
                     font=("TkDefaultFont", 9),
                     bg=t["bg"], fg=err_color,
                     wraplength=330).pack(anchor="w", pady=(0, 4))
            return v

        def save_btn(parent, text, cmd):
            b = tk.Button(parent, text=text, command=cmd,
                          bg=t["accent"], fg=t["accent_fg"],
                          activebackground=t["accent_hover"],
                          activeforeground=t["accent_fg"],
                          relief=tk.FLAT, cursor="hand2",
                          font=("TkDefaultFont", 9, "bold"))
            b.pack(anchor="e", pady=(0, 4))
            return b

        # ── Change username ───────────────────────────
        section("USERNAME")
        uname_var, uname_entry = field(inner, "New username")
        uname_entry.insert(0, info["display_name"])
        uname_msg = msg_label(inner)

        def _do_update_username():
            ok, val = update_username(self.username, uname_var.get())
            if ok:
                self.username = val
                self.root.title(f"My Tasks — {val}")
                if hasattr(self, "_user_chip"):
                    self._user_chip.destroy()
                self._build_user_chip()
                uname_msg.set("✓ Username updated.")
                top.after(1500, lambda: uname_msg.set(""))
            else:
                uname_msg.set(val)

        save_btn(inner, "Update username", _do_update_username)

        # ── Change email ──────────────────────────────
        section("EMAIL")
        email_var, _ = field(inner, "New email address")
        email_var.set(info["email"] or "")
        email_msg = msg_label(inner)

        def _do_update_email():
            ok, msg = update_email(self.username, email_var.get())
            if ok:
                if hasattr(self, "_user_chip"):
                    self._user_chip.destroy()
                self._build_user_chip()
                email_msg.set("✓ Email updated.")
                top.after(1500, lambda: email_msg.set(""))
            else:
                email_msg.set(msg)

        save_btn(inner, "Update email", _do_update_email)

        # ── Change password ───────────────────────────
        section("PASSWORD")
        cur_pw  = pw_field(inner, "Current password")
        new_pw  = pw_field(inner, "New password")
        conf_pw = pw_field(inner, "Confirm new password")
        pw_msg  = msg_label(inner)

        def _do_update_pw():
            if new_pw.get() != conf_pw.get():
                pw_msg.set("New passwords do not match.")
                return
            ok, msg = update_password(self.username, cur_pw.get(), new_pw.get())
            if ok:
                # Re-derive session key with new password and re-encrypt tasks
                from core.auth import get_encryption_key as _gek
                self.enc_key = _gek(self.username.strip().lower(), new_pw.get())
                self._save_async()
                cur_pw.set(""); new_pw.set(""); conf_pw.set("")
                pw_msg.set("✓ Password updated. Tasks re-encrypted.")
                top.after(2000, lambda: pw_msg.set(""))
            else:
                pw_msg.set(msg)

        save_btn(inner, "Update password", _do_update_pw)

        # ── Auto-login / Session ──────────────────────
        section("AUTO-LOGIN")

        from core.auth import (verify_session as _vs, create_session as _cs,
                               revoke_session as _rs, session_days_remaining as _sdr)

        sess = _vs()
        days_left = _sdr()

        # Status label
        if sess:
            import datetime as _dt
            exp = _dt.datetime.fromtimestamp(sess["expiry"]).strftime("%d %b %Y")
            status_text = f"✓  Active — expires {exp}  ({days_left:.1f} days left)"
            status_col  = "#4ADE80"
        else:
            status_text = "✗  No active session"
            status_col  = t["muted_fg"]

        status_lbl = tk.Label(inner, text=status_text,
                              font=("TkDefaultFont", 9),
                              bg=t["bg"], fg=status_col)
        status_lbl.pack(anchor="w", pady=(0, 10))

        # Duration selector
        dur_row = tk.Frame(inner, bg=t["bg"])
        dur_row.pack(anchor="w", pady=(0, 8))
        tk.Label(dur_row, text="Keep me logged in for:",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(side=tk.LEFT)
        _dur_opts = {"1 day": 1, "3 days": 3, "7 days": 7, "14 days": 14, "30 days": 30}
        # Default to current session length or 7 days
        _cur_days = sess["days"] if sess else 7
        _dur_label = next((k for k, v in _dur_opts.items() if v == _cur_days), "7 days")
        dur_var = tk.StringVar(value=_dur_label)
        dur_menu = tk.OptionMenu(dur_row, dur_var, *_dur_opts.keys())
        dur_menu.configure(bg=t["surface2"], fg=t["fg"],
                          activebackground=t["border"], relief="flat")
        dur_menu.pack(side=tk.LEFT, padx=(8, 0))

        sess_msg = msg_label(inner)

        def _enable_autologin():
            ukey = self.username.strip().lower()
            days = _dur_opts.get(dur_var.get(), 7)
            _cs(ukey, days=days, enc_key=self.enc_key)
            _save_remembered(self.username)
            sess_msg.set(f"✓  Auto-login enabled for {days} day{'s' if days > 1 else ''}.")
            status_lbl.config(
                text=f"✓  Active session created  ({days} days)",
                fg="#4ADE80"
            )
            top.after(2000, lambda: sess_msg.set(""))

        def _disable_autologin():
            _rs()
            _clear_remembered()
            sess_msg.set("Session revoked. You'll need to log in next time.")
            status_lbl.config(text="✗  No active session", fg=t["muted_fg"])
            top.after(2500, lambda: sess_msg.set(""))

        btn_row = tk.Frame(inner, bg=t["bg"])
        btn_row.pack(anchor="w", pady=(0, 16))

        tk.Button(btn_row, text="Enable Auto-login",
                  command=_enable_autologin,
                  bg=t["accent"], fg=t["accent_fg"],
                  activebackground=t["accent_hover"],
                  activeforeground=t["accent_fg"],
                  relief=tk.FLAT, cursor="hand2",
                  font=("TkDefaultFont", 9, "bold"),
                  padx=10, pady=4).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_row, text="Sign Out",
                  command=_disable_autologin,
                  bg=t["surface2"], fg=t["fg"],
                  activebackground=t["border"],
                  relief=tk.FLAT, cursor="hand2",
                  font=("TkDefaultFont", 9),
                  padx=10, pady=4).pack(side=tk.LEFT)

        # ── Close button ──────────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=60)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Button(foot, text="Close", command=top.destroy,
                  relief="flat", cursor="hand2",
                  bg=t["accent"], fg=t["accent_fg"],
                  activebackground=t["accent_hover"],
                  activeforeground=t["accent_fg"],
                  font=("TkDefaultFont", 11, "bold")
                  ).place(x=18, y=10, relwidth=1.0, width=-36, height=40)

    def _build_category_filter_buttons(self):
        """(Re)build the category pill buttons in the sidebar."""
        for w in self.cat_filter_frame.winfo_children():
            w.destroy()
        self._cat_filter_buttons.clear()
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # "All" button
        all_btn = tk.Button(
            self.cat_filter_frame, text="All",
            relief="flat", cursor="hand2",
            font=("TkDefaultFont", 9, "bold"),
            padx=8, pady=3,
            command=lambda: self._set_category_filter(None)
        )
        all_btn.pack(fill=tk.X, pady=1)
        self._cat_filter_buttons[None] = all_btn

        for cat in self.categories:
            bg, fg = cat_module.get_color(cat, self.categories, self.dark_mode, self.category_colors)
            btn = tk.Button(
                self.cat_filter_frame, text=cat,
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 9),
                padx=8, pady=3,
                bg=bg, fg=fg,
                activebackground=bg, activeforeground=fg,
                command=lambda c=cat: self._set_category_filter(c)
            )
            btn.pack(fill=tk.X, pady=1)
            self._cat_filter_buttons[cat] = btn

        self._update_category_buttons()

    def _set_category_filter(self, cat):
        self._category_filter = cat
        self._update_category_buttons()
        self.refresh_tasks()

    def _update_category_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        active = self._category_filter
        for key, btn in self._cat_filter_buttons.items():
            if key == active:
                btn.configure(relief="solid", bd=2)
            else:
                btn.configure(relief="flat", bd=0)
        # "All" button colour
        all_btn = self._cat_filter_buttons.get(None)
        if all_btn:
            if active is None:
                all_btn.configure(bg=t["accent"], fg=t["accent_fg"])
            else:
                all_btn.configure(bg=t["surface2"], fg=t["muted_fg"])

    def open_import_gui(self):
        """Import tasks from CSV, TXT, or PDF."""
        from tkinter.filedialog import askopenfilename
        from core.tasks import Task

        top = self._make_dialog("Import Tasks")
        top.resizable(False, False)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer first
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=64)
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        foot.pack_propagate(False)

        # Header
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⬇  Import Tasks",
                 font=("Georgia", 13, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        body = tk.Frame(top, bg=t["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        def section(text):
            tk.Label(body, text=text, font=("TkDefaultFont", 9, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(10, 3))
            tk.Frame(body, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        # ── File picker ───────────────────────────────────
        section("FILE")
        file_row = tk.Frame(body, bg=t["bg"])
        file_row.pack(fill=tk.X)

        file_var = tk.StringVar(value="No file selected")
        file_lbl = tk.Label(file_row, textvariable=file_var,
                            bg=t["surface2"], fg=t["muted_fg"],
                            font=("TkDefaultFont", 9),
                            anchor="w", padx=8,
                            highlightthickness=1,
                            highlightbackground=t["border"])
        file_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)

        chosen_path = {"v": None}

        def pick_file():
            path = askopenfilename(
                title="Choose file to import",
                filetypes=[
                    ("Supported files", "*.csv *.txt *.pdf"),
                    ("CSV files", "*.csv"),
                    ("Text files", "*.txt"),
                    ("PDF files", "*.pdf"),
                ],
                parent=top,
            )
            if path:
                chosen_path["v"] = path
                import os
                file_var.set(os.path.basename(path))
                file_lbl.configure(fg=t["fg"])
                status_lbl.configure(text="")
                _preview()

        self._btn(file_row, t, "Browse…", pick_file).pack(side=tk.LEFT, padx=(8, 0))

        # ── Duplicate handling ────────────────────────────
        section("DUPLICATES")
        dup_var = tk.StringVar(value="skip")
        for val, label, desc in [
            ("skip",    "Skip",    "Don't import tasks with the same name"),
            ("replace", "Replace", "Overwrite existing tasks with the same name"),
            ("keep",    "Keep all","Import all tasks even if names match"),
        ]:
            row = tk.Frame(body, bg=t["bg"])
            row.pack(fill=tk.X, pady=1)
            tk.Radiobutton(row, text=label, variable=dup_var, value=val,
                           bg=t["bg"], fg=t["fg"],
                           activebackground=t["bg"], selectcolor=t["surface2"],
                           relief="flat", cursor="hand2",
                           font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT)
            tk.Label(row, text=f"  — {desc}", bg=t["bg"], fg=t["muted_fg"],
                     font=("TkDefaultFont", 9)).pack(side=tk.LEFT)

        # ── Preview count ─────────────────────────────────
        preview_lbl = tk.Label(body, text="", bg=t["bg"], fg=t["muted_fg"],
                               font=("TkDefaultFont", 9, "italic"))
        preview_lbl.pack(anchor="w", pady=(10, 0))

        status_lbl = tk.Label(body, text="", bg=t["bg"],
                              font=("TkDefaultFont", 9))
        status_lbl.pack(anchor="w", pady=(4, 0))

        parsed_tasks = {"v": []}

        def _preview():
            path = chosen_path["v"]
            if not path:
                return
            try:
                ext = path.lower().rsplit(".", 1)[-1]
                if ext == "csv":
                    rows = import_module.import_csv(path)
                elif ext == "txt":
                    rows = import_module.import_txt(path)
                elif ext == "pdf":
                    rows = import_module.import_pdf(path)
                else:
                    rows = []
                parsed_tasks["v"] = rows
                preview_lbl.configure(
                    text=f"Found {len(rows)} task(s) in file.",
                    fg="#4ADE80" if rows else t["muted_fg"]
                )
            except ImportError as e:
                preview_lbl.configure(text=str(e), fg="#EF4444")
            except Exception as e:
                preview_lbl.configure(text=f"Parse error: {e}", fg="#EF4444")

        def do_import():
            rows = parsed_tasks["v"]
            if not rows:
                status_lbl.configure(text="No tasks to import. Pick a file first.",
                                     fg="#EF4444")
                return

            dup = dup_var.get()
            existing_names = {task.name.lower() for task in self.manager.tasks}
            added = skipped = replaced = 0

            for row in rows:
                name = row["name"].strip()
                if not name:
                    continue
                is_dup = name.lower() in existing_names

                if is_dup and dup == "skip":
                    skipped += 1
                    continue

                if is_dup and dup == "replace":
                    self.manager.tasks = [
                        tk_task for tk_task in self.manager.tasks
                        if tk_task.name.lower() != name.lower()
                    ]
                    replaced += 1

                new_task = Task(
                    name,
                    row.get("description", ""),
                    row.get("due_date"),
                    row.get("priority", "Medium"),
                )
                new_task.category = row.get("category", "General")
                new_task.done     = row.get("done", False)
                new_task.update_status()
                self.manager.tasks.append(new_task)
                existing_names.add(name.lower())
                added += 1

            self._save_async()
            self.refresh_tasks()

            parts = [f"{added} imported"]
            if replaced: parts.append(f"{replaced} replaced")
            if skipped:  parts.append(f"{skipped} skipped")
            status_lbl.configure(text="Done — " + ", ".join(parts) + ".", fg="#4ADE80")

        tk.Button(
            foot, text="⬇  Import", command=do_import,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)

        top.geometry("420x520")

    def open_export_gui(self):
        """Export dialog: choose format, scope, and destination file."""
        top = self._make_dialog("Export Tasks")
        top.resizable(False, False)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer first (pack before grid content)
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=64)
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        foot.pack_propagate(False)

        # Header
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⬆  Export Tasks",
                 font=("Georgia", 13, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        body = tk.Frame(top, bg=t["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        def section(text):
            tk.Label(body, text=text, font=("TkDefaultFont", 9, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(10, 3))
            tk.Frame(body, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        # ── Format ────────────────────────────────────────
        section("FORMAT")
        fmt_var = tk.StringVar(value="CSV")
        fmt_row = tk.Frame(body, bg=t["bg"])
        fmt_row.pack(fill=tk.X)
        for fmt, desc in [("CSV", "Spreadsheet (.csv)"),
                          ("TXT", "Plain text (.txt)"),
                          ("PDF", "PDF report (.pdf)")]:
            col = tk.Frame(fmt_row, bg=t["bg"])
            col.pack(side=tk.LEFT, padx=(0, 16))
            tk.Radiobutton(
                col, text=fmt, variable=fmt_var, value=fmt,
                bg=t["bg"], fg=t["fg"],
                activebackground=t["bg"], selectcolor=t["surface2"],
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 11, "bold")
            ).pack(anchor="w")
            tk.Label(col, text=desc, bg=t["bg"], fg=t["muted_fg"],
                     font=("TkDefaultFont", 8)).pack(anchor="w")

        # ── Scope ─────────────────────────────────────────
        section("SCOPE")
        scope_var = tk.StringVar(value="all")
        for val, label in [
            ("all",    "All tasks"),
            ("active", "Active tasks only"),
            ("done",   "Done tasks only"),
        ]:
            tk.Radiobutton(
                body, text=label, variable=scope_var, value=val,
                bg=t["bg"], fg=t["fg"],
                activebackground=t["bg"], selectcolor=t["surface2"],
                relief="flat", cursor="hand2",
                font=("TkDefaultFont", 10)
            ).pack(anchor="w", pady=1)

        # ── Status label ──────────────────────────────────
        status_lbl = tk.Label(body, text="", bg=t["bg"],
                              font=("TkDefaultFont", 9))
        status_lbl.pack(anchor="w", pady=(12, 0))

        # Share panel (built after generating the temp file)
        share_frame = tk.Frame(body, bg=t["bg"])
        temp_files  = {"path": None}   # track temp file for cleanup on close

        def _build_share_panel(tmp_path, fmt, task_list):
            """Show all share destinations — no mandatory save-to-PC."""
            for w in share_frame.winfo_children():
                w.destroy()
            share_frame.pack(fill=tk.X, pady=(10, 0))

            tk.Frame(share_frame, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))
            tk.Label(share_frame, text="WHAT WOULD YOU LIKE TO DO?",
                     font=("TkDefaultFont", 8, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(0, 6))

            def _share_btn(parent, label, cmd):
                b = tk.Button(parent, text=label, command=cmd,
                              relief="flat", cursor="hand2",
                              bg=t["surface2"], fg=t["fg"],
                              activebackground=t["border"],
                              font=("TkDefaultFont", 9), padx=8, pady=5)
                b.pack(side=tk.LEFT, padx=(0, 6), pady=2)
                return b

            def _row():
                r = tk.Frame(share_frame, bg=t["bg"])
                r.pack(fill=tk.X)
                return r

            # ── Save to PC ───────────────────────────────────
            row_save = _row()
            def save_to_pc():
                from tkinter.filedialog import asksaveasfilename
                ext_map  = {"CSV": ".csv", "TXT": ".txt", "PDF": ".pdf"}
                type_map = {"CSV": [("CSV files", "*.csv")],
                            "TXT": [("Text files", "*.txt")],
                            "PDF": [("PDF files", "*.pdf")]}
                dest = asksaveasfilename(
                    initialfile=os.path.basename(tmp_path),
                    defaultextension=ext_map[fmt],
                    filetypes=type_map[fmt],
                    title="Save export file",
                    parent=top,
                )
                if dest:
                    import shutil
                    shutil.copy2(tmp_path, dest)
                    status_lbl.configure(
                        text=f"✓  Saved to {os.path.basename(dest)}",
                        fg="#4ADE80"
                    )

            _share_btn(row_save, "💾  Save to PC", save_to_pc)
            _share_btn(row_save, "📂  Open file",
                       lambda: share_module.open_file(tmp_path))
            _share_btn(row_save, "🗂  Show folder",
                       lambda: share_module.reveal_in_folder(tmp_path))

            # ── Clipboard ────────────────────────────────────
            row_clip = _row()
            clip_lbl = tk.Label(row_clip, text="", bg=t["bg"],
                                fg="#4ADE80", font=("TkDefaultFont", 8))
            def copy_path():
                share_module.copy_path_to_clipboard(tmp_path, self.root)
                clip_lbl.configure(text="Path copied!")
                top.after(2000, lambda: clip_lbl.configure(text=""))
            def copy_content():
                ok = share_module.copy_content_to_clipboard(tmp_path, self.root)
                clip_lbl.configure(text="Copied!" if ok else "Cannot copy PDF.")
                top.after(2000, lambda: clip_lbl.configure(text=""))

            _share_btn(row_clip, "📋  Copy path", copy_path)
            if fmt in ("CSV", "TXT"):
                _share_btn(row_clip, "📄  Copy content", copy_content)
            clip_lbl.pack(side=tk.LEFT, padx=(6, 0))

            # ── Email ────────────────────────────────────────
            row_mail = _row()
            def send_mail():
                fname = os.path.basename(tmp_path)
                if not share_module.send_email_outlook(tmp_path, f"Tasks export — {fname}"):
                    share_module.send_email(tmp_path, f"Tasks export — {fname}")

            _share_btn(row_mail, "✉️  Send by email", send_mail)
            if fmt == "PDF":
                tk.Label(row_mail,
                         text="(Outlook: attached automatically)",
                         bg=t["bg"], fg=t["muted_fg"],
                         font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(6, 0))

            # ── Messaging ────────────────────────────────────
            if fmt in ("TXT", "CSV"):
                share_text = share_module.tasks_to_share_text(task_list)
                # Split 6 apps across two rows of 3
                row_msg1 = _row()
                row_msg2 = _row()
                rows_for = [row_msg1, row_msg1, row_msg2, row_msg1, row_msg2, row_msg2]
                for (name, icon, fn, needs_root, note), row in zip(
                        share_module.COMMUNICATORS, rows_for):
                    if needs_root:
                        _share_btn(row, f"{icon}  {name}",
                                   lambda f=fn: f(share_text, self.root))
                    else:
                        _share_btn(row, f"{icon}  {name}",
                                   lambda f=fn: f(share_text))
            else:
                row_msg1 = _row()
                row_msg2 = _row()
                def _open_wa(): webbrowser.open("https://web.whatsapp.com")
                def _open_tg(): webbrowser.open("https://web.telegram.org")
                def _open_dc(): webbrowser.open("https://discord.com/app")
                def _open_ms(): webbrowser.open("https://www.messenger.com")
                def _open_sg(): webbrowser.open("https://signal.org")
                def _open_ig(): webbrowser.open("https://www.instagram.com/direct/inbox/")
                _share_btn(row_msg1, "💬  WhatsApp",  _open_wa)
                _share_btn(row_msg1, "✈️  Telegram",   _open_tg)
                _share_btn(row_msg1, "🎮  Discord",   _open_dc)
                _share_btn(row_msg2, "🔒  Signal",    _open_sg)
                _share_btn(row_msg2, "💙  Messenger", _open_ms)
                _share_btn(row_msg2, "📸  Instagram", _open_ig)
                tk.Label(row_msg2, text="— attach PDF manually",
                         bg=t["bg"], fg=t["muted_fg"],
                         font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(4, 0))

            # Resize to fit
            top.update_idletasks()
            new_h = min(top.winfo_reqheight() + 20, 700)
            top.geometry(f"420x{new_h}")

        def do_export():
            import tempfile
            fmt   = fmt_var.get()
            scope = scope_var.get()

            tasks = list(self.manager.tasks)
            if scope == "active":
                tasks = [tk_t for tk_t in tasks if not tk_t.done]
            elif scope == "done":
                tasks = [tk_t for tk_t in tasks if tk_t.done]

            if not tasks:
                status_lbl.configure(text="No tasks match the selected scope.",
                                     fg="#EF4444")
                return

            ext_map = {"CSV": ".csv", "TXT": ".txt", "PDF": ".pdf"}
            try:
                # Write to a named temp file that persists until dialog closes
                if temp_files["path"] and os.path.exists(temp_files["path"]):
                    try: os.unlink(temp_files["path"])
                    except: pass

                from datetime import datetime as dt
                stamp   = dt.now().strftime("%d%m%Y_%H%M")
                suffix  = ext_map[fmt]
                fname   = f"mytasks_{stamp}{suffix}"

                tmp_dir  = tempfile.gettempdir()
                tmp_path = os.path.join(tmp_dir, fname)
                temp_files["path"] = tmp_path

                if fmt == "CSV":
                    export_module.export_csv(tasks, tmp_path)
                elif fmt == "TXT":
                    export_module.export_txt(tasks, tmp_path)
                elif fmt == "PDF":
                    export_module.export_pdf(tasks, tmp_path)

                status_lbl.configure(
                    text=f"✓  {len(tasks)} tasks ready — choose what to do:",
                    fg="#4ADE80"
                )
                _build_share_panel(tmp_path, fmt, tasks)

            except ImportError as e:
                status_lbl.configure(text=str(e), fg="#EF4444")
            except Exception as e:
                status_lbl.configure(text=f"Error: {e}", fg="#EF4444")

        def _cleanup_temp():
            if temp_files["path"] and os.path.exists(temp_files["path"]):
                try: os.unlink(temp_files["path"])
                except: pass
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", _cleanup_temp)

        tk.Button(
            foot, text="⚡  Generate", command=do_export,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)

        top.geometry("380x460")

    def open_analytics_view(self):
        """Advanced Analytics window — pure-canvas charts, no external deps."""
        from datetime import date, datetime as _dt, timedelta
        from collections import defaultdict, Counter
        import math

        t    = DARK_THEME if self.dark_mode else LIGHT_THEME
        top  = tk.Toplevel(self.root)
        top.title("📈  Advanced Analytics")
        top.configure(bg=t["bg"])
        top.geometry("920x680")
        top.resizable(True, True)

        tasks = self.manager.tasks
        today = date.today()

        # ── Palette ────────────────────────────────────────────────────────────
        ACCENT   = t["accent"]
        MUTED    = t["muted_fg"]
        FG       = t["fg"]
        BG       = t["bg"]
        SURF     = t["surface"]
        SURF2    = t["surface2"]
        BORDER   = t["border"]
        CHART_COLORS = [
            "#E07A47","#4A9EE0","#6EE7A0","#FCD34D",
            "#C084FC","#F87171","#34D399","#60A5FA",
        ]
        GREEN  = "#4ADE80"
        RED    = "#F87171"
        YELLOW = "#FCD34D"

        # ── Header ─────────────────────────────────────────────────────────────
        hdr = tk.Frame(top, bg=SURF)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="📈  Advanced Analytics",
                 font=("TkDefaultFont", 13, "bold"),
                 bg=SURF, fg=FG).pack(side=tk.LEFT, padx=16, pady=12)
        tk.Label(hdr, text=f"Based on {len(tasks)} tasks  •  {today.strftime('%d %b %Y')}",
                 font=("TkDefaultFont", 9), bg=SURF, fg=MUTED).pack(side=tk.LEFT, padx=8)
        tk.Frame(top, height=1, bg=BORDER).pack(fill=tk.X)

        # ── Scrollable body ─────────────────────────────────────────────────────
        outer  = tk.Frame(top, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)
        vscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL,
                                style="Flat.Vertical.TScrollbar")
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        main_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0,
                                yscrollcommand=vscroll.set)
        main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll.configure(command=main_canvas.yview)
        body = tk.Frame(main_canvas, bg=BG)
        bwin = main_canvas.create_window((0, 0), window=body, anchor="nw")
        main_canvas.bind("<Configure>", lambda e: main_canvas.itemconfig(bwin, width=e.width))
        body.bind("<Configure>", lambda e: main_canvas.configure(
            scrollregion=main_canvas.bbox("all")))
        def _mw(e): main_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        main_canvas.bind("<Enter>", lambda e: main_canvas.bind_all("<MouseWheel>", _mw))
        main_canvas.bind("<Leave>", lambda e: main_canvas.unbind_all("<MouseWheel>"))

        # ── Chart helpers ───────────────────────────────────────────────────────
        def _frame(title, h=220):
            """Titled chart card."""
            card = tk.Frame(body, bg=SURF, highlightthickness=1,
                            highlightbackground=BORDER)
            card.pack(fill=tk.X, padx=14, pady=8)
            hrow = tk.Frame(card, bg=SURF)
            hrow.pack(fill=tk.X, padx=10, pady=(8, 2))
            tk.Label(hrow, text=title, font=("TkDefaultFont", 10, "bold"),
                     bg=SURF, fg=FG).pack(side=tk.LEFT)
            cv = tk.Canvas(card, height=h, bg=SURF,
                           highlightthickness=0, bd=0)
            cv.pack(fill=tk.X, padx=10, pady=(4, 10))
            return cv

        def _bar_chart(cv, labels, values, colors=None, max_val=None, horizontal=False):
            """Draw a bar chart on canvas cv. Binds resize."""
            if not values or max(values) == 0:
                cv.create_text(10, cv.winfo_reqheight()//2,
                               text="No data", anchor="w", fill=MUTED,
                               font=("TkDefaultFont", 9))
                return
            def _draw(w, h):
                cv.delete("all")
                mv  = max_val or max(values)
                PAD = 36
                n   = len(labels)
                if horizontal:
                    row_h  = (h - PAD) // max(n, 1)
                    bar_h  = int(row_h * 0.55)
                    for i, (lbl, val) in enumerate(zip(labels, values)):
                        y   = PAD + i * row_h + (row_h - bar_h) // 2
                        bw  = int((w - PAD - 80) * (val / mv))
                        col = (colors[i % len(colors)] if colors else ACCENT)
                        cv.create_rectangle(80, y, 80 + bw, y + bar_h,
                                            fill=col, outline="")
                        cv.create_text(76, y + bar_h // 2, text=str(lbl),
                                       anchor="e", fill=MUTED,
                                       font=("TkDefaultFont", 8))
                        cv.create_text(82 + bw, y + bar_h // 2, text=str(val),
                                       anchor="w", fill=FG,
                                       font=("TkDefaultFont", 8))
                else:
                    col_w  = (w - PAD) // max(n, 1)
                    bar_w  = max(4, int(col_w * 0.6))
                    for i, (lbl, val) in enumerate(zip(labels, values)):
                        x   = PAD + i * col_w + (col_w - bar_w) // 2
                        bh  = int((h - PAD - 16) * (val / mv))
                        col = (colors[i % len(colors)] if colors else ACCENT)
                        cv.create_rectangle(x, h - PAD - bh, x + bar_w, h - PAD,
                                            fill=col, outline="")
                        cv.create_text(x + bar_w // 2, h - PAD + 4,
                                       text=str(lbl)[:6], anchor="n",
                                       fill=MUTED, font=("TkDefaultFont", 7))
                        cv.create_text(x + bar_w // 2, h - PAD - bh - 4,
                                       text=str(val), anchor="s",
                                       fill=FG, font=("TkDefaultFont", 8))
                    # Baseline
                    cv.create_line(PAD, h - PAD, w, h - PAD, fill=BORDER)
            cv.update_idletasks()
            _draw(cv.winfo_width() or 860, cv.winfo_height())
            cv.bind("<Configure>", lambda e: _draw(e.width, e.height))

        def _donut(cv, slices, labels):
            """Slices: list of (value, color). Centered donut + legend."""
            def _draw(w, h):
                cv.delete("all")
                total = sum(s[0] for s in slices)
                if total == 0:
                    cv.create_text(w//2, h//2, text="No data",
                                   fill=MUTED, font=("TkDefaultFont", 9))
                    return
                cx, cy = w // 3, h // 2
                R, r   = min(cx, h//2) - 16, min(cx, h//2) - 42
                start  = -90.0
                for (val, col), lbl in zip(slices, labels):
                    extent = 360.0 * val / total
                    cv.create_arc(cx - R, cy - R, cx + R, cy + R,
                                  start=start, extent=extent,
                                  fill=col, outline=SURF, width=2)
                    start += extent
                # Hole
                cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                               fill=SURF, outline=SURF)
                # Centre text
                cv.create_text(cx, cy - 8, text=str(total),
                               font=("TkDefaultFont", 13, "bold"), fill=FG)
                cv.create_text(cx, cy + 10, text="total",
                               font=("TkDefaultFont", 8), fill=MUTED)
                # Legend
                lx, ly = cx + R + 20, cy - len(slices) * 13
                for (val, col), lbl in zip(slices, labels):
                    pct = int(val / total * 100)
                    cv.create_rectangle(lx, ly, lx+12, ly+12, fill=col, outline="")
                    cv.create_text(lx + 16, ly + 6,
                                   text=f"{lbl}  {val} ({pct}%)",
                                   anchor="w", fill=FG,
                                   font=("TkDefaultFont", 9))
                    ly += 22
            cv.update_idletasks()
            _draw(cv.winfo_width() or 860, cv.winfo_height())
            cv.bind("<Configure>", lambda e: _draw(e.width, e.height))

        def _line_chart(cv, series, x_labels=None, ylabel=""):
            """Multi-line chart. series = [(label, [y_vals], color)]"""
            def _draw(w, h):
                cv.delete("all")
                if not series:
                    return
                all_vals = [v for _, vals, _ in series for v in vals]
                if not all_vals:
                    return
                mv   = max(all_vals) or 1
                PAD  = 40
                n    = len(series[0][1])
                if n < 2:
                    return
                step = (w - PAD - 10) / (n - 1)
                # Grid lines
                for i in range(5):
                    y = PAD + i * (h - PAD - 10) // 4
                    cv.create_line(PAD, y, w - 10, y, fill=BORDER, dash=(2, 4))
                    cv.create_text(PAD - 4, y, text=str(int(mv * (4-i) / 4)),
                                   anchor="e", fill=MUTED, font=("TkDefaultFont", 7))
                # X labels
                if x_labels:
                    step_lbl = max(1, n // 10)
                    for i, lbl in enumerate(x_labels):
                        if i % step_lbl == 0:
                            x = PAD + i * step
                            cv.create_text(x, h - 6, text=str(lbl)[:5],
                                           anchor="s", fill=MUTED,
                                           font=("TkDefaultFont", 7))
                # Lines + dots
                for _, vals, col in series:
                    points = []
                    for i, v in enumerate(vals):
                        x = PAD + i * step
                        y = PAD + (h - PAD - 10) * (1 - v / mv)
                        points.extend([x, y])
                    if len(points) >= 4:
                        cv.create_line(*points, fill=col, width=2, smooth=True)
                    for i, v in enumerate(vals):
                        x = PAD + i * step
                        y = PAD + (h - PAD - 10) * (1 - v / mv)
                        cv.create_oval(x-3, y-3, x+3, y+3, fill=col, outline=SURF)
                cv.create_line(PAD, PAD, PAD, h - 10, fill=BORDER)
                cv.create_line(PAD, h - 10, w - 10, h - 10, fill=BORDER)
            cv.update_idletasks()
            _draw(cv.winfo_width() or 860, cv.winfo_height())
            cv.bind("<Configure>", lambda e: _draw(e.width, e.height))

        # ══════════════════════════════════════════════════════════════════════
        # ── KPI tiles row ────────────────────────────────────────────────────
        # ══════════════════════════════════════════════════════════════════════
        total     = len(tasks)
        done      = sum(1 for t2 in tasks if t2.done)
        active    = total - done
        overdue   = sum(1 for t2 in tasks
                        if not t2.done and t2.due_date and t2.due_date < today)
        due_today = sum(1 for t2 in tasks
                        if not t2.done and t2.due_date and t2.due_date == today)
        pct       = round(done / total * 100, 1) if total else 0
        with_sub  = sum(1 for t2 in tasks if getattr(t2, "subtasks", []))
        total_sub = sum(len(getattr(t2, "subtasks", [])) for t2 in tasks)
        avg_sub   = round(total_sub / with_sub, 1) if with_sub else 0

        # Avg completion days
        durations = []
        for t2 in tasks:
            if t2.done and t2.completed_at and t2.created_at:
                try:
                    c = _dt.strptime(t2.created_at[:10], "%Y-%m-%d").date()
                    d = _dt.strptime(t2.completed_at[:10], "%Y-%m-%d").date()
                    durations.append((d - c).days)
                except Exception:
                    pass
        avg_days = round(sum(durations) / len(durations), 1) if durations else "—"

        kpi_frame = tk.Frame(body, bg=BG)
        kpi_frame.pack(fill=tk.X, padx=14, pady=(10, 2))
        for title, value, color in [
            ("Total Tasks",      total,     FG),
            ("Completed",        f"{done} ({pct}%)",  GREEN),
            ("Active",           active,    ACCENT),
            ("Overdue",          overdue,   RED),
            ("Due Today",        due_today, YELLOW),
            ("Avg Complete",     f"{avg_days}d", MUTED),
        ]:
            tile = tk.Frame(kpi_frame, bg=SURF2,
                            highlightthickness=1, highlightbackground=BORDER)
            tile.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
            tk.Label(tile, text=str(value),
                     font=("TkDefaultFont", 18, "bold"),
                     bg=SURF2, fg=color).pack(pady=(10, 0))
            tk.Label(tile, text=title,
                     font=("TkDefaultFont", 8),
                     bg=SURF2, fg=MUTED).pack(pady=(0, 10))

        # ══════════════════════════════════════════════════════════════════════
        # ── Row 1: Completion trend (last 30 days) + Category donut
        # ══════════════════════════════════════════════════════════════════════
        row1 = tk.Frame(body, bg=BG)
        row1.pack(fill=tk.X, padx=14, pady=4)

        # Completion trend
        trend_card = tk.Frame(row1, bg=SURF, highlightthickness=1,
                              highlightbackground=BORDER)
        trend_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(trend_card, text="📅  Tasks Completed — Last 30 Days",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        trend_cv = tk.Canvas(trend_card, height=200, bg=SURF,
                             highlightthickness=0, bd=0)
        trend_cv.pack(fill=tk.X, padx=10, pady=(4, 10))

        completed_by_day = defaultdict(int)
        created_by_day   = defaultdict(int)
        for t2 in tasks:
            if t2.completed_at:
                try:
                    d = _dt.strptime(t2.completed_at[:10], "%Y-%m-%d").date()
                    if (today - d).days <= 30:
                        completed_by_day[d] += 1
                except Exception: pass
            try:
                d = _dt.strptime(t2.created_at[:10], "%Y-%m-%d").date()
                if (today - d).days <= 30:
                    created_by_day[d] += 1
            except Exception: pass

        days30 = [(today - timedelta(days=29-i)) for i in range(30)]
        completed_vals = [completed_by_day.get(d, 0) for d in days30]
        created_vals   = [created_by_day.get(d,   0) for d in days30]
        xlbls = [d.strftime("%d") for d in days30]
        _line_chart(trend_cv, [
            ("Completed", completed_vals, GREEN),
            ("Created",   created_vals,   ACCENT),
        ], x_labels=xlbls)

        # Category donut
        cat_card = tk.Frame(row1, bg=SURF, highlightthickness=1,
                            highlightbackground=BORDER)
        cat_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(cat_card, text="🏷  Tasks by Category",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        cat_cv = tk.Canvas(cat_card, height=200, bg=SURF,
                           highlightthickness=0, bd=0)
        cat_cv.pack(fill=tk.X, padx=10, pady=(4, 10))

        cat_counts = Counter(getattr(t2, "category", "General") for t2 in tasks)
        cat_items  = cat_counts.most_common()
        _donut(cat_cv,
               [(v, CHART_COLORS[i % len(CHART_COLORS)]) for i, (k, v) in enumerate(cat_items)],
               [k for k, v in cat_items])

        # ══════════════════════════════════════════════════════════════════════
        # ── Row 2: Priority breakdown + Completion by weekday
        # ══════════════════════════════════════════════════════════════════════
        row2 = tk.Frame(body, bg=BG)
        row2.pack(fill=tk.X, padx=14, pady=4)

        # Priority donut
        prio_card = tk.Frame(row2, bg=SURF, highlightthickness=1,
                             highlightbackground=BORDER)
        prio_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(prio_card, text="🔥  Priority Distribution",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        prio_cv = tk.Canvas(prio_card, height=200, bg=SURF,
                            highlightthickness=0, bd=0)
        prio_cv.pack(fill=tk.X, padx=10, pady=(4, 10))
        pc = Counter(t2.priority for t2 in tasks)
        _donut(prio_cv, [
            (pc.get("High",   0), RED),
            (pc.get("Medium", 0), YELLOW),
            (pc.get("Low",    0), GREEN),
        ], ["High", "Medium", "Low"])

        # Completion by day of week
        dow_card = tk.Frame(row2, bg=SURF, highlightthickness=1,
                            highlightbackground=BORDER)
        dow_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(dow_card, text="📆  Completions by Day of Week",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        dow_cv = tk.Canvas(dow_card, height=200, bg=SURF,
                           highlightthickness=0, bd=0)
        dow_cv.pack(fill=tk.X, padx=10, pady=(4, 10))
        dow_counts = defaultdict(int)
        for t2 in tasks:
            if t2.done and t2.completed_at:
                try:
                    d = _dt.strptime(t2.completed_at[:10], "%Y-%m-%d")
                    dow_counts[d.weekday()] += 1
                except Exception: pass
        dow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        _bar_chart(dow_cv, dow_labels,
                   [dow_counts.get(i, 0) for i in range(7)],
                   colors=CHART_COLORS)

        # ══════════════════════════════════════════════════════════════════════
        # ── Row 3: Monthly completed bar + Overdue aging
        # ══════════════════════════════════════════════════════════════════════
        row3 = tk.Frame(body, bg=BG)
        row3.pack(fill=tk.X, padx=14, pady=4)

        # Monthly completed
        monthly_card = tk.Frame(row3, bg=SURF, highlightthickness=1,
                                highlightbackground=BORDER)
        monthly_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(monthly_card, text="📊  Completions by Month",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        monthly_cv = tk.Canvas(monthly_card, height=200, bg=SURF,
                               highlightthickness=0, bd=0)
        monthly_cv.pack(fill=tk.X, padx=10, pady=(4, 10))
        monthly_counts = defaultdict(int)
        for t2 in tasks:
            if t2.done and t2.completed_at:
                try:
                    d = _dt.strptime(t2.completed_at[:7], "%Y-%m")
                    monthly_counts[d.strftime("%b %y")] += 1
                except Exception: pass
        if monthly_counts:
            m_keys = sorted(monthly_counts.keys(),
                            key=lambda s: _dt.strptime(s, "%b %y"))[-12:]
            _bar_chart(monthly_cv, m_keys,
                       [monthly_counts[k] for k in m_keys],
                       colors=[ACCENT])

        # Overdue aging
        aging_card = tk.Frame(row3, bg=SURF, highlightthickness=1,
                              highlightbackground=BORDER)
        aging_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(aging_card, text="⚠️  Overdue Aging",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        aging_cv = tk.Canvas(aging_card, height=200, bg=SURF,
                             highlightthickness=0, bd=0)
        aging_cv.pack(fill=tk.X, padx=10, pady=(4, 10))
        overdue_tasks = [t2 for t2 in tasks
                         if not t2.done and t2.due_date and t2.due_date < today]
        buckets = {"1-3d": 0, "4-7d": 0, "8-14d": 0, "15-30d": 0, ">30d": 0}
        for t2 in overdue_tasks:
            days_over = (today - t2.due_date).days
            if days_over <= 3:   buckets["1-3d"]   += 1
            elif days_over <= 7: buckets["4-7d"]   += 1
            elif days_over <= 14: buckets["8-14d"] += 1
            elif days_over <= 30: buckets["15-30d"] += 1
            else:                buckets[">30d"]   += 1
        _bar_chart(aging_cv, list(buckets.keys()), list(buckets.values()),
                   colors=[YELLOW, ACCENT, RED, RED, "#7F1D1D"],
                   horizontal=True)

        # ══════════════════════════════════════════════════════════════════════
        # ── Row 4: Top categories horizontal bar + Completion speed histogram
        # ══════════════════════════════════════════════════════════════════════
        row4 = tk.Frame(body, bg=BG)
        row4.pack(fill=tk.X, padx=14, pady=4)

        # Completion rate by category
        cr_card = tk.Frame(row4, bg=SURF, highlightthickness=1,
                           highlightbackground=BORDER)
        cr_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(cr_card, text="✅  Completion Rate by Category",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        cr_cv = tk.Canvas(cr_card, height=220, bg=SURF,
                          highlightthickness=0, bd=0)
        cr_cv.pack(fill=tk.X, padx=10, pady=(4, 10))
        cat_done  = defaultdict(int)
        cat_total = defaultdict(int)
        for t2 in tasks:
            cat = getattr(t2, "category", "General")
            cat_total[cat] += 1
            if t2.done: cat_done[cat] += 1
        cr_cats = sorted(cat_total.keys(),
                         key=lambda c: cat_total[c], reverse=True)[:8]
        cr_vals = [int(cat_done[c] / cat_total[c] * 100) for c in cr_cats]
        _bar_chart(cr_cv, cr_cats, cr_vals,
                   colors=[GREEN if v >= 70 else (YELLOW if v >= 40 else RED)
                           for v in cr_vals],
                   max_val=100, horizontal=True)

        # Completion speed histogram
        spd_card = tk.Frame(row4, bg=SURF, highlightthickness=1,
                            highlightbackground=BORDER)
        spd_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(spd_card, text="⏱  Completion Speed (days to finish)",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        spd_cv = tk.Canvas(spd_card, height=220, bg=SURF,
                           highlightthickness=0, bd=0)
        spd_cv.pack(fill=tk.X, padx=10, pady=(4, 10))
        spd_buckets = defaultdict(int)
        for days in durations:
            if days == 0:   spd_buckets["0d"]    += 1
            elif days <= 3: spd_buckets["1-3d"]  += 1
            elif days <= 7: spd_buckets["4-7d"]  += 1
            elif days <= 14: spd_buckets["8-14d"] += 1
            elif days <= 30: spd_buckets["15-30d"] += 1
            else:            spd_buckets[">30d"]  += 1
        spd_order = ["0d", "1-3d", "4-7d", "8-14d", "15-30d", ">30d"]
        _bar_chart(spd_cv, spd_order,
                   [spd_buckets.get(k, 0) for k in spd_order],
                   colors=[GREEN, GREEN, YELLOW, YELLOW, ACCENT, RED])

        # ══════════════════════════════════════════════════════════════════════
        # ── Row 5: Cumulative burndown + Attachment/Recurrence stats
        # ══════════════════════════════════════════════════════════════════════
        row5 = tk.Frame(body, bg=BG)
        row5.pack(fill=tk.X, padx=14, pady=(4, 14))

        burn_card = tk.Frame(row5, bg=SURF, highlightthickness=1,
                             highlightbackground=BORDER)
        burn_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        tk.Label(burn_card, text="📉  Cumulative Burndown (last 60 days)",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))
        burn_cv = tk.Canvas(burn_card, height=200, bg=SURF,
                            highlightthickness=0, bd=0)
        burn_cv.pack(fill=tk.X, padx=10, pady=(4, 10))

        days60 = [(today - timedelta(days=59-i)) for i in range(60)]
        created_cum  = []
        completed_cum = []
        cc, dc = 0, 0
        for d in days60:
            for t2 in tasks:
                try:
                    if _dt.strptime(t2.created_at[:10], "%Y-%m-%d").date() == d:
                        cc += 1
                except Exception: pass
                if t2.done and t2.completed_at:
                    try:
                        if _dt.strptime(t2.completed_at[:10], "%Y-%m-%d").date() == d:
                            dc += 1
                    except Exception: pass
            created_cum.append(cc)
            completed_cum.append(dc)
        xlbls60 = [d.strftime("%d") for d in days60]
        _line_chart(burn_cv, [
            ("Total created",   created_cum,   ACCENT),
            ("Total completed", completed_cum, GREEN),
        ], x_labels=xlbls60)

        # Feature stats tile
        feat_card = tk.Frame(row5, bg=SURF, highlightthickness=1,
                             highlightbackground=BORDER)
        feat_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(feat_card, text="🔬  Feature Usage",
                 font=("TkDefaultFont", 10, "bold"), bg=SURF, fg=FG).pack(
            anchor="w", padx=10, pady=(8, 2))

        stats = {
            "With subtasks":   sum(1 for t2 in tasks if getattr(t2, "subtasks", [])),
            "Subtasks total":  sum(len(getattr(t2, "subtasks", [])) for t2 in tasks),
            "With attachment": sum(1 for t2 in tasks if getattr(t2, "attachments", [])),
            "Recurring":       sum(1 for t2 in tasks if getattr(t2, "recurrence", None)),
            "  ↳ Daily":       sum(1 for t2 in tasks if getattr(t2, "recurrence","")=="Daily"),
            "  ↳ Weekly":      sum(1 for t2 in tasks if getattr(t2, "recurrence","")=="Weekly"),
            "  ↳ Monthly":     sum(1 for t2 in tasks if getattr(t2, "recurrence","")=="Monthly"),
            "No due date":     sum(1 for t2 in tasks if not t2.due_date),
            "Completion rate": f"{pct}%",
        }
        for k, v in stats.items():
            r = tk.Frame(feat_card, bg=SURF)
            r.pack(fill=tk.X, padx=14, pady=2)
            tk.Label(r, text=k, font=("TkDefaultFont", 9),
                     bg=SURF, fg=MUTED).pack(side=tk.LEFT)
            tk.Label(r, text=str(v), font=("TkDefaultFont", 9, "bold"),
                     bg=SURF, fg=FG).pack(side=tk.RIGHT)
        # Footer padding
        tk.Frame(feat_card, bg=SURF, height=10).pack()

    def open_cloud_sync_gui(self):
        """Cloud sync management dialog."""
        from services.cloud_sync import PROVIDERS, get_last_sync_info, _load_creds, _save_creds
        from core.storage import tasks_file

        t   = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = self._make_dialog("☁️  Cloud Sync")
        top.geometry("500x560")
        top.resizable(False, True)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="☁️  Cloud Sync",
                 font=("TkDefaultFont", 12, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=16, pady=(12, 4))
        tk.Label(hdr, text="Backup and restore your encrypted task file",
                 font=("TkDefaultFont", 9), bg=t["surface"],
                 fg=t["muted_fg"]).pack(anchor="w", padx=16, pady=(0, 10))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Scrollable body ───────────────────────────────────────────────────
        canvas_frame = tk.Frame(top, bg=t["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas   = tk.Canvas(canvas_frame, bg=t["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical",
                                  command=canvas.yview,
                                  style="Flat.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        body = tk.Frame(canvas, bg=t["bg"])
        bwin = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(bwin, width=e.width))
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        def _mw(e): canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _mw))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        pad = tk.Frame(body, bg=t["bg"])
        pad.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # ── Determine local task file ─────────────────────────────────────────
        enc_path   = tasks_file(self.username, encrypted=True)
        plain_path = tasks_file(self.username, encrypted=False)
        local_path = enc_path if os.path.exists(enc_path) else plain_path
        is_enc     = os.path.exists(enc_path)

        tk.Label(pad,
                 text=f"Local file:  {os.path.basename(local_path)}  "
                      f"({'🔒 encrypted' if is_enc else '📄 plain JSON'})",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]
                 ).pack(anchor="w", pady=(0, 10))

        # Helper widgets
        err_color = "#F87171" if self.dark_mode else "#DC2626"
        ok_color  = "#4ADE80" if self.dark_mode else "#16A34A"

        def _section(title):
            tk.Label(pad, text=title,
                     font=("TkDefaultFont", 10, "bold"),
                     bg=t["bg"], fg=t["fg"]).pack(anchor="w", pady=(14, 2))
            tk.Frame(pad, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        def _status_lbl():
            v = tk.StringVar()
            lbl = tk.Label(pad, textvariable=v, font=("TkDefaultFont", 9),
                           bg=t["bg"], fg=ok_color, wraplength=440, justify="left")
            lbl.pack(anchor="w", pady=(2, 0))
            return v, lbl

        def _btn_row(*items):
            r = tk.Frame(pad, bg=t["bg"])
            r.pack(anchor="w", pady=(0, 4))
            return r

        def _mk_btn(parent, text, cmd, primary=False):
            bg = t["accent"] if primary else t["surface2"]
            fg = t["accent_fg"] if primary else t["fg"]
            b = tk.Button(parent, text=text, command=cmd,
                          bg=bg, fg=fg,
                          activebackground=t["accent_hover"] if primary else t["border"],
                          relief=tk.FLAT, cursor="hand2",
                          font=("TkDefaultFont", 9, "bold" if primary else "normal"),
                          padx=10, pady=4)
            b.pack(side=tk.LEFT, padx=(0, 6))
            return b

        sync_info = get_last_sync_info()

        # ── GITHUB GIST ───────────────────────────────────────────────────────
        _section("🐙  GitHub Gist")
        gist = PROVIDERS["GitHub Gist"]
        gist_cfg = _load_creds().get("github_gist", {})

        tk.Label(pad, text="Personal Access Token (gist scope):",
                 font=("TkDefaultFont", 9), bg=t["bg"],
                 fg=t["muted_fg"]).pack(anchor="w")
        gist_token_var = tk.StringVar(value=gist_cfg.get("token", ""))
        gist_entry = tk.Entry(pad, textvariable=gist_token_var, show="●", width=46,
                              bg=t["entry_bg"], fg=t["fg"],
                              insertbackground=t["fg"], relief=tk.FLAT,
                              font=("TkDefaultFont", 9),
                              highlightthickness=1, highlightbackground=t["border"])
        gist_entry.pack(anchor="w", pady=(3, 6), fill=tk.X)
        gist_msg, gist_lbl = _status_lbl()

        if "GitHub Gist" in sync_info:
            info = sync_info["GitHub Gist"]
            gist_msg.set(f"✓ Connected  •  Last push: {info['last_push']}  •  Last pull: {info['last_pull']}")

        def _gist_connect():
            tok = gist_token_var.get().strip()
            if not tok:
                gist_msg.set("Enter a token first."); gist_lbl.configure(fg=err_color); return
            gist.set_token(tok)
            gist_msg.set("✓ Token saved."); gist_lbl.configure(fg=ok_color)

        def _gist_push():
            try:
                self._save_async()
                url = gist.push(local_path, self.username)
                gist_msg.set(f"✓ Pushed  →  {url}"); gist_lbl.configure(fg=ok_color)
            except Exception as e:
                gist_msg.set(f"✗ {e}"); gist_lbl.configure(fg=err_color)

        def _gist_pull():
            try:
                gist.pull(local_path, self.username)
                self.manager.tasks.clear()
                from core.storage import load_tasks
                load_tasks(self.manager, self.username, self.enc_key)
                self.refresh_tasks()
                gist_msg.set("✓ Pulled and reloaded."); gist_lbl.configure(fg=ok_color)
            except Exception as e:
                gist_msg.set(f"✗ {e}"); gist_lbl.configure(fg=err_color)

        r1 = _btn_row()
        _mk_btn(r1, "Save token", _gist_connect)
        _mk_btn(r1, "⬆ Push",  _gist_push,  primary=True)
        _mk_btn(r1, "⬇ Pull",  _gist_pull)

        tk.Label(pad, text="Get a token → github.com/settings/tokens  (tick 'gist')",
                 font=("TkDefaultFont", 8), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")

        # ── GOOGLE DRIVE ──────────────────────────────────────────────────────
        _section("🟢  Google Drive")
        gdrive = PROVIDERS["Google Drive"]
        gdrive_msg, gdrive_lbl = _status_lbl()

        if "Google Drive" in sync_info:
            info = sync_info["Google Drive"]
            gdrive_msg.set(f"✓ Connected  •  Last push: {info['last_push']}")
            gdrive_lbl.configure(fg=ok_color)
        else:
            gdrive_msg.set("Not connected")
            gdrive_lbl.configure(fg=t["muted_fg"])

        def _gdrive_auth():
            try:
                gdrive.authorise()
                gdrive_msg.set("✓ Google Drive connected."); gdrive_lbl.configure(fg=ok_color)
            except Exception as e:
                gdrive_msg.set(f"✗ {e}"); gdrive_lbl.configure(fg=err_color)

        def _gdrive_push():
            try:
                self._save_async()
                url = gdrive.push(local_path, self.username)
                gdrive_msg.set(f"✓ Pushed to Drive."); gdrive_lbl.configure(fg=ok_color)
            except Exception as e:
                gdrive_msg.set(f"✗ {e}"); gdrive_lbl.configure(fg=err_color)

        def _gdrive_pull():
            try:
                gdrive.pull(local_path, self.username)
                self.manager.tasks.clear()
                from core.storage import load_tasks
                load_tasks(self.manager, self.username, self.enc_key)
                self.refresh_tasks()
                gdrive_msg.set("✓ Pulled from Drive."); gdrive_lbl.configure(fg=ok_color)
            except Exception as e:
                gdrive_msg.set(f"✗ {e}"); gdrive_lbl.configure(fg=err_color)

        r2 = _btn_row()
        _mk_btn(r2, "🔐 Authorise", _gdrive_auth)
        _mk_btn(r2, "⬆ Push", _gdrive_push, primary=True)
        _mk_btn(r2, "⬇ Pull", _gdrive_pull)
        tk.Label(pad,
                 text="Requires:  py -m pip install google-auth-oauthlib google-api-python-client",
                 font=("TkDefaultFont", 8), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")

        # ── DROPBOX ───────────────────────────────────────────────────────────
        _section("📦  Dropbox")
        dbox = PROVIDERS["Dropbox"]
        dbox_msg, dbox_lbl = _status_lbl()
        _dbox_flow = {"flow": None}

        if "Dropbox" in sync_info:
            info = sync_info["Dropbox"]
            dbox_msg.set(f"✓ Connected  •  Last push: {info['last_push']}")
            dbox_lbl.configure(fg=ok_color)
        else:
            dbox_msg.set("Not connected"); dbox_lbl.configure(fg=t["muted_fg"])

        dbox_code_frame = tk.Frame(pad, bg=t["bg"])
        dbox_code_frame.pack(anchor="w", pady=(4, 0))
        dbox_code_var = tk.StringVar()
        dbox_code_entry = tk.Entry(dbox_code_frame, textvariable=dbox_code_var, width=36,
                                   bg=t["entry_bg"], fg=t["fg"],
                                   insertbackground=t["fg"], relief=tk.FLAT,
                                   font=("TkDefaultFont", 9),
                                   highlightthickness=1, highlightbackground=t["border"],
                                   state="disabled")
        dbox_code_entry.pack(side=tk.LEFT, padx=(0, 6))

        def _dbox_auth():
            try:
                _dbox_flow["flow"] = dbox.authorise()
                dbox_code_entry.configure(state="normal")
                dbox_msg.set("Browser opened — paste the code above then click Confirm")
                dbox_lbl.configure(fg=t["muted_fg"])
            except Exception as e:
                dbox_msg.set(f"✗ {e}"); dbox_lbl.configure(fg=err_color)

        def _dbox_confirm():
            code = dbox_code_var.get().strip()
            if not code or not _dbox_flow["flow"]:
                return
            try:
                dbox.finish_auth(_dbox_flow["flow"], code)
                dbox_code_entry.configure(state="disabled")
                dbox_msg.set("✓ Dropbox connected."); dbox_lbl.configure(fg=ok_color)
            except Exception as e:
                dbox_msg.set(f"✗ {e}"); dbox_lbl.configure(fg=err_color)

        def _dbox_push():
            try:
                self._save_async()
                dbox.push(local_path, self.username)
                dbox_msg.set("✓ Pushed to Dropbox."); dbox_lbl.configure(fg=ok_color)
            except Exception as e:
                dbox_msg.set(f"✗ {e}"); dbox_lbl.configure(fg=err_color)

        def _dbox_pull():
            try:
                dbox.pull(local_path, self.username)
                self.manager.tasks.clear()
                from core.storage import load_tasks
                load_tasks(self.manager, self.username, self.enc_key)
                self.refresh_tasks()
                dbox_msg.set("✓ Pulled from Dropbox."); dbox_lbl.configure(fg=ok_color)
            except Exception as e:
                dbox_msg.set(f"✗ {e}"); dbox_lbl.configure(fg=err_color)

        r3 = _btn_row()
        _mk_btn(r3, "🔐 Authorise", _dbox_auth)
        _mk_btn(r3, "Confirm code", _dbox_confirm)
        _mk_btn(r3, "⬆ Push", _dbox_push, primary=True)
        _mk_btn(r3, "⬇ Pull", _dbox_pull)
        tk.Label(pad, text="Requires:  py -m pip install dropbox",
                 font=("TkDefaultFont", 8), bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w")

        # ── Footer ────────────────────────────────────────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=54)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Button(foot, text="Close", command=top.destroy,
                  relief="flat", cursor="hand2",
                  bg=t["accent"], fg=t["accent_fg"],
                  activebackground=t["accent_hover"],
                  font=("TkDefaultFont", 11, "bold")
                  ).place(x=14, y=8, relwidth=1.0, width=-28, height=38)

    def open_gantt_view(self):
        """Open a scrollable GitHub-style Gantt timeline window."""
        from datetime import date, timedelta

        tasks_with_dates = [t for t in self.manager.tasks if t.due_date]
        if not tasks_with_dates:
            messagebox.showinfo("Gantt View",
                "No tasks with due dates to display.")
            return

        t   = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = tk.Toplevel(self.root)
        top.title("📊  Gantt Timeline")
        top.configure(bg=t["bg"])
        top.geometry("1000x620")
        top.resizable(True, True)

        # ── Colour helpers ────────────────────────────────────────────────────
        PRIO_COLORS = {
            "High":   ("#F87171", "#7F1D1D"),
            "Medium": ("#FCD34D", "#78350F"),
            "Low":    ("#6EE7A0", "#14532D"),
        }
        DONE_COLOR  = (t["border"], t["muted_fg"])

        # ── Layout constants ──────────────────────────────────────────────────
        ROW_H       = 28
        LABEL_W     = 220
        HEADER_H    = 56
        DAY_W       = 22
        TODAY       = date.today()

        # Date range: earliest due - 3 days → latest due + 7 days
        all_dates = [t2.due_date for t2 in tasks_with_dates]
        range_start = min(all_dates) - timedelta(days=3)
        range_end   = max(all_dates) + timedelta(days=7)
        total_days  = (range_end - range_start).days + 1

        # ── Header bar ────────────────────────────────────────────────────────
        hdr_frame = tk.Frame(top, bg=t["surface"], height=44)
        hdr_frame.pack(fill=tk.X)
        hdr_frame.pack_propagate(False)

        title_lbl = tk.Label(hdr_frame, text="📊  Gantt Timeline",
                             font=("TkDefaultFont", 12, "bold"),
                             bg=t["surface"], fg=t["fg"])
        title_lbl.pack(side=tk.LEFT, padx=16, pady=10)

        range_lbl = tk.Label(hdr_frame,
                             text=f"{range_start.strftime('%d %b %Y')}  →  {range_end.strftime('%d %b %Y')}",
                             font=("TkDefaultFont", 9),
                             bg=t["surface"], fg=t["muted_fg"])
        range_lbl.pack(side=tk.LEFT, padx=8)

        # Filter var
        filter_var = tk.StringVar(value="All")
        for lbl in ("All", "Active", "Done", "Overdue"):
            rb = tk.Radiobutton(
                hdr_frame, text=lbl, variable=filter_var, value=lbl,
                bg=t["surface"], fg=t["fg"],
                selectcolor=t["surface"],
                activebackground=t["surface"],
                font=("TkDefaultFont", 9),
                cursor="hand2",
                command=lambda: _redraw(),
            )
            rb.pack(side=tk.RIGHT, padx=6)

        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Scrollable canvas area ────────────────────────────────────────────
        outer = tk.Frame(top, bg=t["bg"])
        outer.pack(fill=tk.BOTH, expand=True)

        h_scroll = ttk.Scrollbar(outer, orient=tk.HORIZONTAL,
                                  style="Flat.Vertical.TScrollbar")
        v_scroll = ttk.Scrollbar(outer, orient=tk.VERTICAL,
                                  style="Flat.Vertical.TScrollbar")
        canvas = tk.Canvas(outer, bg=t["bg"],
                           highlightthickness=0, bd=0)

        h_scroll.configure(command=canvas.xview)
        v_scroll.configure(command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set,
                         yscrollcommand=v_scroll.set)

        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Mouse wheel
        def _yscroll(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        def _xscroll(e):
            canvas.xview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<MouseWheel>",         _yscroll)
        canvas.bind("<Shift-MouseWheel>",   _xscroll)

        # ── Draw function ─────────────────────────────────────────────────────
        def _redraw():
            canvas.delete("all")
            filt = filter_var.get()
            rows = []
            for task in tasks_with_dates:
                if filt == "Active"  and task.done: continue
                if filt == "Done"    and not task.done: continue
                if filt == "Overdue" and (task.done or not task.is_overdue): continue
                rows.append(task)

            total_w = LABEL_W + total_days * DAY_W
            total_h = HEADER_H + len(rows) * ROW_H + 20

            # ── Month/week header ─────────────────────────────────────────────
            # Month row
            cur_month = None
            mx = LABEL_W
            for i in range(total_days):
                d = range_start + timedelta(days=i)
                if d.month != cur_month:
                    cur_month = d.month
                    canvas.create_rectangle(
                        mx, 0, mx + DAY_W * 20, HEADER_H // 2,
                        fill=t["surface"], outline=t["border"],
                    )
                    canvas.create_text(
                        mx + 4, HEADER_H // 4,
                        text=d.strftime("%b %Y"),
                        anchor="w",
                        font=("TkDefaultFont", 9, "bold"),
                        fill=t["fg"],
                    )
                mx += DAY_W

            # Day row + vertical grid lines
            for i in range(total_days):
                d   = range_start + timedelta(days=i)
                x   = LABEL_W + i * DAY_W
                is_today   = (d == TODAY)
                is_weekend = d.weekday() >= 5

                day_bg = t["accent"] if is_today else (t["surface"] if is_weekend else t["surface2"])
                day_fg = t["accent_fg"] if is_today else (t["muted_fg"] if is_weekend else t["fg"])

                canvas.create_rectangle(
                    x, HEADER_H // 2, x + DAY_W, HEADER_H,
                    fill=day_bg, outline=t["border"],
                )
                canvas.create_text(
                    x + DAY_W // 2, HEADER_H * 3 // 4,
                    text=str(d.day),
                    font=("TkDefaultFont", 7, "bold" if is_today else "normal"),
                    fill=day_fg,
                )

                # Vertical grid line through rows
                canvas.create_line(
                    x, HEADER_H, x, total_h,
                    fill=t["border"], width=1,
                )

            # Today vertical highlight
            if range_start <= TODAY <= range_end:
                tx = LABEL_W + (TODAY - range_start).days * DAY_W
                canvas.create_line(tx, HEADER_H, tx, total_h,
                                   fill=t["accent"], width=2, dash=(4, 3))

            # ── Task rows ─────────────────────────────────────────────────────
            tooltip_win = {"win": None, "item": None}

            for row_idx, task in enumerate(rows):
                y_top    = HEADER_H + row_idx * ROW_H
                y_bottom = y_top + ROW_H
                y_mid    = (y_top + y_bottom) // 2

                # Alternating row background
                row_bg = t["surface"] if row_idx % 2 == 0 else t["bg"]
                canvas.create_rectangle(0, y_top, total_w, y_bottom,
                                        fill=row_bg, outline="")

                # ── Label column ───────────────────────────────────────────
                # Truncate long names
                name_display = task.name if len(task.name) <= 26 else task.name[:25] + "…"
                prio_icon    = {"High": "🔥", "Medium": "⚡", "Low": "🌿"}.get(task.priority, "")
                done_prefix  = "☑ " if task.done else ""
                canvas.create_text(
                    8, y_mid,
                    text=f"{done_prefix}{prio_icon} {name_display}",
                    anchor="w",
                    font=("TkDefaultFont", 9),
                    fill=t["muted_fg"] if task.done else t["fg"],
                )

                # Separator
                canvas.create_line(LABEL_W, y_top, LABEL_W, y_bottom,
                                   fill=t["border"])

                # ── Bar: start = (due - 1 day), end = due date ─────────────
                # For tasks with only a due date, show a single-day milestone dot
                # For tasks that also have a created_at date on the range, show a bar
                try:
                    created = datetime.strptime(task.created_at[:10], "%Y-%m-%d").date()
                except Exception:
                    created = task.due_date

                bar_start = max(created, range_start)
                bar_end   = task.due_date

                if bar_start > bar_end:
                    bar_start = bar_end

                bx1 = LABEL_W + (bar_start - range_start).days * DAY_W
                bx2 = LABEL_W + (bar_end   - range_start).days * DAY_W + DAY_W

                BAR_PAD = 4
                bar_h   = ROW_H - BAR_PAD * 2

                bar_color, _ = DONE_COLOR if task.done else PRIO_COLORS.get(task.priority, PRIO_COLORS["Medium"])

                # Bar body
                bar_item = canvas.create_rectangle(
                    bx1, y_top + BAR_PAD,
                    bx2, y_top + BAR_PAD + bar_h,
                    fill=bar_color, outline="",
                    tags=(f"bar_{row_idx}",),
                )

                # Rounded end cap (diamond) at due date
                cx = bx2 - DAY_W // 2
                cy = y_mid
                r  = 5
                if bx2 - bx1 <= DAY_W:
                    # Single-day milestone: diamond
                    canvas.create_polygon(
                        cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy,
                        fill=bar_color, outline=t["bg"],
                    )

                # Subtask progress stripe
                subtasks = getattr(task, "subtasks", [])
                if subtasks:
                    done_sub = sum(1 for s in subtasks if s.done)
                    prog = done_sub / len(subtasks)
                    stripe_w = max(2, int((bx2 - bx1) * prog))
                    canvas.create_rectangle(
                        bx1, y_bottom - 4, bx1 + stripe_w, y_bottom,
                        fill=t["accent"], outline="",
                    )

                # Tooltip on hover
                def _enter(e, task=task, row_idx=row_idx):
                    if tooltip_win["item"] == row_idx:
                        return
                    if tooltip_win["win"]:
                        try: tooltip_win["win"].destroy()
                        except: pass
                    tooltip_win["item"] = row_idx
                    lines = [
                        task.name,
                        f"Priority: {task.priority}",
                        f"Due: {task.due_date}",
                        f"Status: {'Done ✓' if task.done else ('Overdue ⚠' if task.is_overdue else 'Active')}",
                    ]
                    if task.description:
                        lines.append(f"Note: {task.description[:50]}")
                    if subtasks:
                        done_sub = sum(1 for s in subtasks if s.done)
                        lines.append(f"Subtasks: {done_sub}/{len(subtasks)}")

                    win = tk.Toplevel(top)
                    win.overrideredirect(True)
                    win.attributes("-topmost", True)
                    win.configure(bg=t["border"])
                    tk.Label(win, text="\n".join(lines),
                             bg=t["surface2"], fg=t["fg"],
                             font=("TkDefaultFont", 9),
                             justify="left", padx=10, pady=6).pack(padx=1, pady=1)
                    win.update_idletasks()
                    wx = top.winfo_rootx() + e.x + 14
                    wy = top.winfo_rooty() + e.y - win.winfo_reqheight() - 6
                    win.geometry(f"+{wx}+{wy}")
                    tooltip_win["win"] = win

                def _leave(e):
                    if tooltip_win["win"]:
                        try: tooltip_win["win"].destroy()
                        except: pass
                    tooltip_win["win"]  = None
                    tooltip_win["item"] = None

                canvas.tag_bind(f"bar_{row_idx}", "<Enter>",  _enter)
                canvas.tag_bind(f"bar_{row_idx}", "<Leave>",  _leave)

                # Click bar → open edit dialog
                def _click(e, task=task):
                    # Select that task in main list and open edit
                    for item in self.task_tree.get_children():
                        vals = self.task_tree.item(item, "values")
                        name = vals[1].split("  🔁")[0].split("  📎")[0].split("  ◈")[0].strip()
                        if name == task.name:
                            self.task_tree.selection_set(item)
                            break
                canvas.tag_bind(f"bar_{row_idx}", "<Button-1>", _click)

            # Horizontal label separator
            canvas.create_line(LABEL_W, 0, LABEL_W, total_h,
                               fill=t["border"], width=1)

            canvas.configure(scrollregion=(0, 0, total_w, total_h))

        _redraw()

        # Scroll to today
        if range_start <= TODAY <= range_end:
            frac = ((TODAY - range_start).days * DAY_W) / max(1, total_days * DAY_W)
            canvas.after(100, lambda: canvas.xview_moveto(max(0, frac - 0.3)))

    def open_settings_gui(self):
        """Full Settings dialog with tabbed sections."""
        top = self._make_dialog("Settings")
        top.resizable(True, True)
        top.minsize(460, 420)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # ── Header ────────────────────────────────────────
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⚙  Settings", font=("Georgia", 14, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        # ── Footer (packed before canvas so it's always visible) ──
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X, side=tk.BOTTOM)
        foot = tk.Frame(top, bg=t["surface"], height=70)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Button(
            foot, text="Close", command=top.destroy,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 13, "bold"),
        ).place(x=18, y=10, relwidth=1.0, width=-36, height=50)

        # ── Scrollable canvas body ─────────────────────────
        canvas_frame = tk.Frame(top, bg=t["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg=t["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview, style="Flat.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = tk.Frame(canvas, bg=t["bg"])
        body_win = canvas.create_window((0, 0), window=body, anchor="nw")

        # Keep inner frame width in sync with canvas width
        def _on_canvas_resize(e):
            canvas.itemconfig(body_win, width=e.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        # Update scroll region whenever body content changes
        def _on_body_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Auto-fit height up to 85% of screen
            content_h  = body.winfo_reqheight()
            screen_h   = top.winfo_screenheight()
            max_h      = int(screen_h * 0.85)
            header_h   = hdr.winfo_reqheight() + 2   # +border
            footer_h   = foot.winfo_reqheight() + 2
            dialog_h   = min(content_h + header_h + footer_h + 10, max_h)
            top.geometry(f"460x{dialog_h}")
        body.bind("<Configure>", _on_body_resize)

        # Mouse-wheel scroll
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        top.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Inner padding wrapper
        pad = tk.Frame(body, bg=t["bg"])
        pad.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        def section(parent, title):
            """Render a section heading."""
            tk.Label(parent, text=title, font=("TkDefaultFont", 9, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(14, 4))
            tk.Frame(parent, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 8))

        def row(parent, label_text, widget_fn):
            """Label on left, widget on right."""
            r = tk.Frame(parent, bg=t["bg"])
            r.pack(fill=tk.X, pady=4)
            tk.Label(r, text=label_text, bg=t["bg"], fg=t["fg"],
                     font=("TkDefaultFont", 10), anchor="w").pack(side=tk.LEFT)
            widget_fn(r)
            return r

        # ══ APPEARANCE ════════════════════════════════════
        section(pad, "APPEARANCE")

        # Dark mode toggle
        dark_var = tk.BooleanVar(value=self.dark_mode)
        def toggle_dark():
            self.dark_mode = dark_var.get()
            self._last_applied_theme = None   # invalidate cache
            self.save_ui_config()
            self.apply_theme()

        def row_dark(parent):
            chk = tk.Checkbutton(parent, variable=dark_var, command=toggle_dark,
                                 bg=t["bg"], fg=t["fg"],
                                 activebackground=t["bg"],
                                 selectcolor=t["surface2"],
                                 relief="flat", cursor="hand2")
            chk.pack(side=tk.RIGHT)
        row(pad, "Dark mode", row_dark)

        # ══ BEHAVIOUR ═════════════════════════════════════
        section(pad, "BEHAVIOUR")

        tray_var = tk.BooleanVar(value=self.minimize_to_tray)
        tray_note = "(requires pystray)" if not TRAY_AVAILABLE else ""
        def toggle_tray():
            self.minimize_to_tray = tray_var.get()
            self.save_ui_config()

        def row_tray(parent):
            chk = tk.Checkbutton(parent, variable=tray_var, command=toggle_tray,
                                 bg=t["bg"], fg=t["fg"],
                                 activebackground=t["bg"],
                                 selectcolor=t["surface2"],
                                 relief="flat", cursor="hand2",
                                 state="normal" if TRAY_AVAILABLE else "disabled")
            chk.pack(side=tk.RIGHT)
        row(pad, f"Minimise to tray on close  {tray_note}", row_tray)

        # ══ REMINDERS ═════════════════════════════════════
        section(pad, "REMINDERS")

        rem_vars = {}
        remind_labels = [
            ("reminders_enabled", "Enable task reminders"),
            ("remind_overdue",    "Notify for overdue tasks"),
            ("remind_today",      "Notify for tasks due today"),
            ("remind_tomorrow",   "Notify for tasks due tomorrow"),
            ("remind_3days",      "Notify for tasks due within 3 days"),
        ]

        def make_toggle_rem(key, var):
            def _toggle():
                self.reminder_cfg[key] = var.get()
                self.save_ui_config()
                if hasattr(self, "_reminder_svc"):
                    self._reminder_svc.update_config(self.reminder_cfg)
                # Enable/disable sub-checkboxes when master toggle changes
                if key == "reminders_enabled":
                    state = "normal" if var.get() else "disabled"
                    for k, v in rem_vars.items():
                        if k != "reminders_enabled":
                            v["chk"].configure(state=state)
            return _toggle

        for key, label in remind_labels:
            var = tk.BooleanVar(value=self.reminder_cfg.get(key, True))
            enabled = self.reminder_cfg.get("reminders_enabled", True)
            state = "normal" if (key == "reminders_enabled" or enabled) else "disabled"

            def _row_rem(parent, v=var, k=key):
                chk = tk.Checkbutton(
                    parent, variable=v,
                    command=make_toggle_rem(k, v),
                    bg=t["bg"], fg=t["fg"],
                    activebackground=t["bg"],
                    selectcolor=t["surface2"],
                    relief="flat", cursor="hand2",
                    state=state,
                )
                chk.pack(side=tk.RIGHT)
                rem_vars[k] = {"chk": chk, "var": v}

            row(pad, label, _row_rem)

        if not REMINDERS_AVAILABLE:
            note = tk.Label(pad,
                            text="Install plyer for OS notifications:  pip install plyer\n"
                                 "Without it, in-app toasts are used.",
                            bg=t["bg"], fg=t["muted_fg"],
                            font=("TkDefaultFont", 8),
                            justify="left")
            note.pack(anchor="w", pady=(4, 0))
        section(pad, "CATEGORIES")

        cat_outer = tk.Frame(pad, bg=t["bg"])
        cat_outer.pack(fill=tk.X)

        # Scrollable list of categories
        list_frame = tk.Frame(cat_outer, bg=t["surface2"],
                              highlightthickness=1,
                              highlightbackground=t["border"])
        list_frame.pack(fill=tk.X, pady=(0, 8))

        def rebuild_cat_list():
            for w in list_frame.winfo_children():
                w.destroy()
            for cat in self.categories:
                r = tk.Frame(list_frame, bg=t["surface2"])
                r.pack(fill=tk.X, padx=6, pady=3)
                from core import categories as _cm
                bg_c, fg_c = _cm.get_color(cat, self.categories, self.dark_mode, self.category_colors)
                tk.Label(r, text=cat, bg=bg_c, fg=fg_c,
                         font=("TkDefaultFont", 9, "bold"),
                         padx=8, pady=2).pack(side=tk.LEFT)
                if cat != "General":
                    def _del(c=cat):
                        self.categories.remove(c)
                        self.category_colors.pop(c, None)   # remove custom colour
                        for task in self.manager.tasks:
                            if getattr(task, "category", "General") == c:
                                task.category = "General"
                        self.save_ui_config()
                        self._build_category_filter_buttons()
                        self.refresh_tasks()
                        rebuild_cat_list()
                    tk.Button(r, text="✕", relief="flat", cursor="hand2",
                              bg=t["surface2"], fg=t["muted_fg"],
                              activebackground=t["surface2"],
                              font=("TkDefaultFont", 8),
                              command=_del).pack(side=tk.RIGHT)

        rebuild_cat_list()

        # ── Add new category ──────────────────────────────
        # State: chosen custom colour for the new category (None = use palette)
        chosen_color = {"light": None, "dark": None}  # mutable dict for closure

        add_row = tk.Frame(cat_outer, bg=t["bg"])
        add_row.pack(fill=tk.X, pady=(4, 0))

        new_cat_entry = self._entry(add_row, t, width=16)
        new_cat_entry.pack(side=tk.LEFT, ipady=4, padx=(0, 6))

        # Colour swatch button — shows chosen colour, opens picker on click
        DEFAULT_SWATCH = t["surface2"]
        swatch_btn = tk.Button(
            add_row, text="  🎨  ", relief="flat", cursor="hand2",
            bg=DEFAULT_SWATCH, fg=t["fg"],
            activebackground=t["border"],
            font=("TkDefaultFont", 10),
            padx=4, pady=4
        )
        swatch_btn.pack(side=tk.LEFT, padx=(0, 6))

        def pick_color():
            from tkinter.colorchooser import askcolor
            # Start from current swatch colour or a default
            init = chosen_color["light"] or t["accent"]
            result = askcolor(color=init, title="Pick category colour", parent=top)
            if result and result[1]:
                bg_light = result[1]          # e.g. "#a855f7"
                fg_light = auto_fg(bg_light)
                # Derive a darker shade for dark mode (reduce brightness ~40%)
                r = int(bg_light[1:3], 16)
                g = int(bg_light[3:5], 16)
                b = int(bg_light[5:7], 16)
                bg_dark = "#{:02x}{:02x}{:02x}".format(
                    max(0, int(r * 0.45)),
                    max(0, int(g * 0.45)),
                    max(0, int(b * 0.45)),
                )
                fg_dark = "#{:02x}{:02x}{:02x}".format(
                    min(255, int(r * 1.7)),
                    min(255, int(g * 1.7)),
                    min(255, int(b * 1.7)),
                )
                chosen_color["light"] = (bg_light, fg_light)
                chosen_color["dark"]  = (bg_dark,  fg_dark)
                swatch_btn.configure(bg=bg_light, fg=fg_light,
                                     activebackground=bg_light)

        swatch_btn.configure(command=pick_color)

        def add_category():
            name = new_cat_entry.get().strip()
            if not name or name in self.categories:
                return
            self.categories.append(name)
            # Store custom colour if one was picked
            if chosen_color["light"]:
                self.category_colors[name] = {
                    "light": chosen_color["light"],
                    "dark":  chosen_color["dark"],
                }
                # Reset for next use
                chosen_color["light"] = None
                chosen_color["dark"]  = None
                swatch_btn.configure(bg=DEFAULT_SWATCH, fg=t["fg"],
                                     activebackground=t["border"])
            new_cat_entry.delete(0, tk.END)
            self.save_ui_config()
            self._build_category_filter_buttons()
            rebuild_cat_list()

        self._btn(add_row, t, "Add", add_category, primary=True).pack(side=tk.LEFT)
        new_cat_entry.bind("<Return>", lambda e: add_category())

        # ── LOCAL REST API ────────────────────────────
        section(pad, "LOCAL REST API")

        api_enabled_var = tk.BooleanVar(value=self.api_cfg.get("api_enabled", False))
        api_port_var    = tk.StringVar(value=str(self.api_cfg.get("api_port", 5000)))

        def _row_api(left, right_widget):
            r = tk.Frame(pad, bg=t["bg"])
            r.pack(fill=tk.X, pady=2)
            tk.Label(r, text=left, font=("TkDefaultFont", 9),
                     bg=t["bg"], fg=t["muted_fg"], width=16, anchor="w").pack(side=tk.LEFT)
            right_widget(r).pack(side=tk.LEFT)

        tk.Checkbutton(
            pad, variable=api_enabled_var,
            text="Enable local REST API  (requires app restart)",
            font=("TkDefaultFont", 9),
            bg=t["bg"], fg=t["fg"],
            selectcolor=t["entry_bg"],
            activebackground=t["bg"], activeforeground=t["fg"],
            cursor="hand2", relief=tk.FLAT, bd=0,
        ).pack(anchor="w", pady=(0, 6))

        port_row = tk.Frame(pad, bg=t["bg"])
        port_row.pack(anchor="w", pady=(0, 6))
        tk.Label(port_row, text="Port:", font=("TkDefaultFont", 9),
                 bg=t["bg"], fg=t["muted_fg"]).pack(side=tk.LEFT)
        port_entry = tk.Entry(port_row, textvariable=api_port_var, width=7,
                              bg=t["entry_bg"], fg=t["fg"],
                              insertbackground=t["fg"], relief=tk.FLAT,
                              font=("TkDefaultFont", 9),
                              highlightthickness=1, highlightbackground=t["border"])
        port_entry.pack(side=tk.LEFT, padx=(6, 0))

        # API key display
        try:
            from api.server import API_KEY as _key
            key_text = _key
        except Exception:
            key_text = "(start API to generate)"

        key_row = tk.Frame(pad, bg=t["bg"])
        key_row.pack(anchor="w", pady=(0, 4))
        tk.Label(key_row, text="API Key:", font=("TkDefaultFont", 9),
                 bg=t["bg"], fg=t["muted_fg"]).pack(side=tk.LEFT)
        key_lbl = tk.Label(key_row, text=key_text[:20] + "…",
                           font=("Courier", 8),
                           bg=t["entry_bg"], fg=t["fg"], padx=6, pady=2)
        key_lbl.pack(side=tk.LEFT, padx=(6, 0))

        def _copy_key():
            self.root.clipboard_clear()
            self.root.clipboard_append(key_text)
            key_lbl.configure(text="Copied!")
            pad.after(1500, lambda: key_lbl.configure(text=key_text[:20] + "…"))

        self._btn(key_row, t, "📋 Copy", _copy_key).pack(side=tk.LEFT, padx=(6, 0))

        api_msg = tk.Label(pad, text="", font=("TkDefaultFont", 9),
                           bg=t["bg"], fg="#4ADE80")
        api_msg.pack(anchor="w", pady=(0, 4))

        def _save_api():
            try:
                port = int(api_port_var.get())
                assert 1024 <= port <= 65535
            except (ValueError, AssertionError):
                api_msg.configure(text="Port must be 1024–65535", fg="#F87171")
                return
            self.api_cfg["api_enabled"] = api_enabled_var.get()
            self.api_cfg["api_port"]    = port
            self.save_ui_config()
            api_msg.configure(text="✓ Saved — restart to apply", fg="#4ADE80")
            pad.after(2000, lambda: api_msg.configure(text=""))

        self._btn(pad, t, "Save API Settings", _save_api, primary=True).pack(
            anchor="w", pady=(0, 16))

    def _manage_categories_gui(self):
        """Dialog to add/remove custom categories."""
        top = self._make_dialog("Manage Categories")
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        top.geometry("320x420")

        tk.Label(top, text="Your categories:", **self._lbl(t)).pack(anchor="w", padx=14, pady=(12, 4))

        list_frame = tk.Frame(top, bg=t["surface2"], bd=1, relief="flat")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        def rebuild_list():
            for w in list_frame.winfo_children():
                w.destroy()
            for cat in self.categories:
                row = tk.Frame(list_frame, bg=t["surface2"])
                row.pack(fill=tk.X, padx=6, pady=2)
                bg, fg = cat_module.get_color(cat, self.categories, self.dark_mode, self.category_colors)
                tk.Label(row, text=cat, bg=bg, fg=fg,
                         font=("TkDefaultFont", 9, "bold"),
                         padx=8, pady=2).pack(side=tk.LEFT)
                if cat != "General":
                    def make_delete(c=cat):
                        def do():
                            self.categories.remove(c)
                            # Re-assign tasks in that category to General
                            for task in self.manager.tasks:
                                if getattr(task, "category", "General") == c:
                                    task.category = "General"
                            self.save_ui_config()
                            self._build_category_filter_buttons()
                            rebuild_list()
                            self.refresh_tasks()
                        return do
                    tk.Button(row, text="✕", relief="flat", cursor="hand2",
                              bg=t["surface2"], fg=t["muted_fg"],
                              font=("TkDefaultFont", 8),
                              command=make_delete()).pack(side=tk.RIGHT)

        rebuild_list()

        # Add new category
        add_frame = tk.Frame(top, bg=t["bg"])
        add_frame.pack(fill=tk.X, padx=14, pady=8)
        new_entry = self._entry(add_frame, t, width=20)
        new_entry.pack(side=tk.LEFT, padx=(0, 6), ipady=4)

        def add_category():
            name = new_entry.get().strip()
            if not name or name in self.categories:
                return
            self.categories.append(name)
            new_entry.delete(0, tk.END)
            self.save_ui_config()
            self._build_category_filter_buttons()
            rebuild_list()

        self._btn(add_frame, t, "Add", add_category, primary=True).pack(side=tk.LEFT)
        new_entry.bind("<Return>", lambda e: add_category())

        self._btn(top, t, "Done", top.destroy).pack(pady=(0, 12))

    # ═══════════════════════════════════════════════
    #  TASK ACTIONS
    # ═══════════════════════════════════════════════

    def add_task_gui(self):
        top = self._make_dialog("Add Task")
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer MUST be packed before the form frame (pack reserves bottom space first)
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot_add = tk.Frame(top, bg=t["surface"], height=64)
        foot_add.pack(side=tk.BOTTOM, fill=tk.X)
        foot_add.pack_propagate(False)

        # Form in its own frame so grid and pack don't conflict on `top`
        form = tk.Frame(top, bg=t["bg"])
        form.pack(fill=tk.BOTH, expand=True)

        tk.Label(form, text="Task Name:", **self._lbl(t)).grid(row=0, column=0, sticky="e", padx=10, pady=8)
        name_entry = self._entry(form, t, width=38)
        name_entry.grid(row=0, column=1, padx=10, pady=8)
        name_entry.focus_set()

        tk.Label(form, text="Description:", **self._lbl(t)).grid(row=1, column=0, sticky="e", padx=10, pady=8)
        desc_entry = self._entry(form, t, width=38)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        tk.Label(form, text="Category:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        cat_var = tk.StringVar(value=self._category_filter or "General")
        cat_menu = tk.OptionMenu(form, cat_var, *self.categories)
        cat_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        cat_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Priority:", **self._lbl(t)).grid(row=3, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value="⚡ Medium")
        priority_menu = tk.OptionMenu(form, priority_var, "🔥 High", "⚡ Medium", "🌿 Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Due Date:", **self._lbl(t)).grid(row=4, column=0, sticky="ne", padx=10, pady=8)
        due_var = tk.StringVar()
        cal = Calendar(form, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.grid(row=4, column=1, padx=10, pady=8)

        due_lbl = tk.Label(form, text="No date selected", font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"])
        due_lbl.grid(row=5, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(form, t, "Select Date", select_due).grid(row=5, column=0, sticky="e", padx=10, pady=4)

        tk.Label(form, text="Recurrence:", **self._lbl(t)).grid(row=6, column=0, sticky="e", padx=10, pady=8)
        recur_var = tk.StringVar(value="None")
        recur_menu = tk.OptionMenu(form, recur_var, "None", "Daily", "Weekly", "Monthly")
        recur_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        recur_menu.grid(row=6, column=1, sticky="w", padx=10, pady=8)

        # ── Attachments ───────────────────────────────
        tk.Label(form, text="Attachments:", **self._lbl(t)).grid(
            row=7, column=0, sticky="ne", padx=10, pady=8)

        attach_frame = tk.Frame(form, bg=t["bg"])
        attach_frame.grid(row=7, column=1, sticky="w", padx=10, pady=4)

        _pending_attachments = []   # list of source paths to copy on confirm

        attach_list = tk.Listbox(
            attach_frame, height=3, width=36,
            bg=t["entry_bg"], fg=t["fg"],
            selectbackground=t["accent"], selectforeground=t["accent_fg"],
            relief="flat", font=("TkDefaultFont", 9),
            highlightthickness=1, highlightbackground=t["border"],
        )
        attach_list.pack(side=tk.LEFT)

        def _add_attachment():
            from tkinter.filedialog import askopenfilenames
            paths = askopenfilenames(
                title="Attach files",
                filetypes=[
                    ("Allowed files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.odf *.txt *.csv"),
                    ("Images",        "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                    ("Documents",     "*.odf *.txt *.csv"),
                ],
                parent=top,
            )
            for p in paths:
                fname = os.path.basename(p)
                if fname not in [os.path.basename(x) for x in _pending_attachments]:
                    _pending_attachments.append(p)
                    attach_list.insert(tk.END, fname)

        def _remove_attachment():
            sel = attach_list.curselection()
            if sel:
                idx = sel[0]
                attach_list.delete(idx)
                _pending_attachments.pop(idx)

        btn_col = tk.Frame(attach_frame, bg=t["bg"])
        btn_col.pack(side=tk.LEFT, padx=(6, 0))
        self._btn(btn_col, t, "📎 Add",   _add_attachment).pack(fill=tk.X, pady=(0, 4))
        self._btn(btn_col, t, "🗑 Remove", _remove_attachment).pack(fill=tk.X)

        def confirm():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Task must have a name!", parent=top)
                return
            task = self.manager.add_task(
                name,
                desc_entry.get().strip(),
                due_var.get() or None,
                priority_var.get().split()[-1]
            )
            if task:
                task.category   = cat_var.get()
                task.recurrence = None if recur_var.get() == "None" else recur_var.get()
            elif self.manager.tasks:
                task = self.manager.tasks[-1]
                task.category   = cat_var.get()
                task.recurrence = None if recur_var.get() == "None" else recur_var.get()
            # Copy attachments to user's folder
            if task:
                task.attachments = self._copy_attachments(_pending_attachments)
            if task and task in self.manager.tasks:
                self.manager.tasks.remove(task)
            if task:
                cmd = AddTaskCommand(self.manager, task)
                self.history.execute(cmd)
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            self._save_async()
            top.destroy()

        tk.Button(
            foot_add, text="✚  Add Task", command=confirm,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)

    def edit_task_gui(self):
        selected_item = self.task_tree.selection()
        if not selected_item:
            messagebox.showinfo("Edit Task", "Select a task to edit.")
            return

        task_index = self.task_tree.index(selected_item[0])
        task_to_edit = self.get_sorted_tasks()[task_index]

        top = self._make_dialog("Edit Task")
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Footer MUST be packed before the form frame (pack reserves bottom space first)
        tk.Frame(top, height=1, bg=t["border"]).pack(side=tk.BOTTOM, fill=tk.X)
        foot = tk.Frame(top, bg=t["surface"], height=64)
        foot.pack(side=tk.BOTTOM, fill=tk.X)
        foot.pack_propagate(False)

        # Form in its own frame so grid and pack don't conflict on `top`
        form = tk.Frame(top, bg=t["bg"])
        form.pack(fill=tk.BOTH, expand=True)

        tk.Label(form, text="Task Name:", **self._lbl(t)).grid(row=0, column=0, sticky="e", padx=10, pady=8)
        name_entry = self._entry(form, t, width=38)
        name_entry.insert(0, task_to_edit.name)
        name_entry.grid(row=0, column=1, padx=10, pady=8)

        tk.Label(form, text="Description:", **self._lbl(t)).grid(row=1, column=0, sticky="e", padx=10, pady=8)
        desc_entry = self._entry(form, t, width=38)
        desc_entry.insert(0, task_to_edit.description)
        desc_entry.grid(row=1, column=1, padx=10, pady=8)

        tk.Label(form, text="Category:", **self._lbl(t)).grid(row=2, column=0, sticky="e", padx=10, pady=8)
        current_cat = getattr(task_to_edit, "category", "General")
        cat_var = tk.StringVar(value=current_cat)
        cat_menu = tk.OptionMenu(form, cat_var, *self.categories)
        cat_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        cat_menu.grid(row=2, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Priority:", **self._lbl(t)).grid(row=3, column=0, sticky="e", padx=10, pady=8)
        priority_var = tk.StringVar(value=PRIORITY_ICONS.get(task_to_edit.priority, task_to_edit.priority))
        priority_menu = tk.OptionMenu(form, priority_var, "🔥 High", "⚡ Medium", "🌿 Low")
        priority_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        priority_menu.grid(row=3, column=1, sticky="w", padx=10, pady=8)

        tk.Label(form, text="Due Date:", **self._lbl(t)).grid(row=4, column=0, sticky="ne", padx=10, pady=8)
        init_date = task_to_edit.due_date if task_to_edit.due_date else datetime.now().date()
        cal = Calendar(
            form, selectmode="day",
            year=init_date.year, month=init_date.month, day=init_date.day,
            date_pattern="yyyy-mm-dd"
        )
        cal.grid(row=4, column=1, padx=10, pady=8)

        due_var = tk.StringVar(value=task_to_edit.due_date.strftime("%Y-%m-%d") if task_to_edit.due_date else "")
        due_lbl = tk.Label(
            form,
            text=f"Selected: {due_var.get()}" if due_var.get() else "No date selected",
            font=("TkDefaultFont", 10), bg=t["bg"], fg=t["muted_fg"]
        )
        due_lbl.grid(row=5, column=1, sticky="w", padx=10)

        def select_due():
            due_var.set(cal.get_date())
            due_lbl.configure(text=f"Selected: {due_var.get()}")

        self._btn(form, t, "Select Date", select_due).grid(row=5, column=0, sticky="e", padx=10, pady=4)

        tk.Label(form, text="Recurrence:", **self._lbl(t)).grid(row=6, column=0, sticky="e", padx=10, pady=8)
        cur_recur = getattr(task_to_edit, "recurrence", None) or "None"
        recur_var = tk.StringVar(value=cur_recur)
        recur_menu = tk.OptionMenu(form, recur_var, "None", "Daily", "Weekly", "Monthly")
        recur_menu.configure(bg=t["surface2"], fg=t["fg"], activebackground=t["border"], relief="flat")
        recur_menu.grid(row=6, column=1, sticky="w", padx=10, pady=8)

        # ── Attachments ───────────────────────────────
        tk.Label(form, text="Attachments:", **self._lbl(t)).grid(
            row=7, column=0, sticky="ne", padx=10, pady=8)

        attach_frame = tk.Frame(form, bg=t["bg"])
        attach_frame.grid(row=7, column=1, sticky="w", padx=10, pady=4)

        _pending_new   = []   # new source paths to copy
        _current_paths = list(getattr(task_to_edit, "attachments", []))

        attach_list = tk.Listbox(
            attach_frame, height=3, width=36,
            bg=t["entry_bg"], fg=t["fg"],
            selectbackground=t["accent"], selectforeground=t["accent_fg"],
            relief="flat", font=("TkDefaultFont", 9),
            highlightthickness=1, highlightbackground=t["border"],
        )
        attach_list.pack(side=tk.LEFT)
        for p in _current_paths:
            attach_list.insert(tk.END, os.path.basename(p))

        def _add_attachment_edit():
            from tkinter.filedialog import askopenfilenames
            paths = askopenfilenames(
                title="Attach files",
                filetypes=[
                    ("Allowed files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.odf *.txt *.csv"),
                    ("Images",        "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                    ("Documents",     "*.odf *.txt *.csv"),
                ],
                parent=top,
            )
            for p in paths:
                fname = os.path.basename(p)
                _pending_new.append(p)
                attach_list.insert(tk.END, fname)

        def _remove_attachment_edit():
            sel = attach_list.curselection()
            if not sel:
                return
            idx = sel[0]
            attach_list.delete(idx)
            n_current = len(_current_paths)
            if idx < n_current:
                _current_paths.pop(idx)
            else:
                _pending_new.pop(idx - n_current)

        btn_col = tk.Frame(attach_frame, bg=t["bg"])
        btn_col.pack(side=tk.LEFT, padx=(6, 0))
        self._btn(btn_col, t, "📎 Add",   _add_attachment_edit).pack(fill=tk.X, pady=(0, 4))
        self._btn(btn_col, t, "🗑 Remove", _remove_attachment_edit).pack(fill=tk.X)

        before_snap = snapshot(task_to_edit)

        def confirm():
            new_due_str = cal.get_date()
            copied = self._copy_attachments(_pending_new)
            updated_attachments = _current_paths + copied
            after_snap = {
                "name":        name_entry.get().strip(),
                "description": desc_entry.get().strip(),
                "category":    cat_var.get(),
                "priority":    priority_var.get().split()[-1],
                "due_date":    datetime.strptime(new_due_str, "%Y-%m-%d").date() if new_due_str else None,
                "done":        task_to_edit.done,
                "recurrence":  None if recur_var.get() == "None" else recur_var.get(),
                "attachments": updated_attachments,
            }
            cmd = EditTaskCommand(task_to_edit, before_snap, after_snap)
            self.history.execute(cmd)
            task_to_edit.update_status()
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            self._save_async()
            top.destroy()

        tk.Button(
            foot, text="💾  Save Changes", command=confirm,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 12, "bold"),
        ).place(x=14, y=10, relwidth=1.0, width=-28, height=44)
        self.root.wait_window(top)

    def delete_task_gui(self):
        selected = self.task_tree.selection()
        if not selected:
            return
        task = self._get_task(selected[0])
        if task:
            cmd = DeleteTaskCommand(self.manager, task)
            self.history.execute(cmd)
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            self._save_async()

    def mark_done_gui(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showinfo("Mark Done", "Select a task to mark done.")
            return
        task = self._get_task(selected[0])
        if task:
            cmd = MarkDoneCommand(task, task.done)
            self.history.execute(cmd)
            # ── Spawn next occurrence for recurring tasks ──
            if task.done and task.recurrence and task.due_date:
                next_due = task.next_due_date()
                if next_due:
                    self._spawn_recurrence(task, next_due)
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            self._save_async()

    def _copy_attachments(self, source_paths: list) -> list:
        """Copy source files into the user's attachments folder. Returns list of stored paths."""
        from core.storage import attachments_dir
        import shutil
        dest_dir = attachments_dir(self.username)
        stored = []
        for src in source_paths:
            try:
                fname = os.path.basename(src)
                dest  = os.path.join(dest_dir, fname)
                # Avoid name collision
                base, ext = os.path.splitext(fname)
                counter = 1
                while os.path.exists(dest):
                    dest = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                    counter += 1
                shutil.copy2(src, dest)
                stored.append(dest)
            except Exception as e:
                print(f"[attachments] Could not copy {src}: {e}")
        return stored

    def open_attachments_gui(self):
        """Show attachments panel for the selected task."""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showinfo("Attachments", "Select a task first.")
            return

        # Always use the parent task — subtasks don't have attachments
        parent, sub = self.get_task_from_selection(selected[0])
        task = parent
        if not task:
            return

        t   = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = self._make_dialog(f"📎  Attachments — {task.name[:40]}")
        top.geometry("480x400")
        top.resizable(False, True)

        # Header
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=f"📎  {task.name}", font=("TkDefaultFont", 11, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=16, pady=10)
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        # Listbox
        list_frame = tk.Frame(top, bg=t["bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        lb = tk.Listbox(
            list_frame, bg=t["entry_bg"], fg=t["fg"],
            selectbackground=t["accent"], selectforeground=t["accent_fg"],
            relief="flat", font=("TkDefaultFont", 10),
            highlightthickness=1, highlightbackground=t["border"],
            activestyle="none",
        )
        lb.pack(fill=tk.BOTH, expand=True)

        # Empty state label
        empty_lbl = tk.Label(list_frame, text="No attachments yet.\nClick '📎 Add' to attach files.",
                             font=("TkDefaultFont", 9), bg=t["entry_bg"],
                             fg=t["muted_fg"], justify="center")

        def _refresh_list():
            lb.delete(0, tk.END)
            if not task.attachments:
                lb.pack_forget()
                empty_lbl.pack(fill=tk.BOTH, expand=True, pady=20)
            else:
                empty_lbl.pack_forget()
                lb.pack(fill=tk.BOTH, expand=True)
                for p in task.attachments:
                    size = ""
                    try:
                        b = os.path.getsize(p)
                        size = f"  ({b/1024:.1f} KB)" if b < 1024*1024 else f"  ({b/1024/1024:.1f} MB)"
                    except Exception:
                        size = "  (missing)"
                    exists_icon = "" if os.path.exists(p) else "⚠ "
                    lb.insert(tk.END, f"{exists_icon}{os.path.basename(p)}{size}")

        _refresh_list()

        # Buttons row
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)
        btn_row = tk.Frame(top, bg=t["surface"], height=54)
        btn_row.pack(fill=tk.X)
        btn_row.pack_propagate(False)

        def _add():
            from tkinter.filedialog import askopenfilenames
            paths = askopenfilenames(
                title="Attach files",
                filetypes=[
                    ("Allowed files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.odf *.txt *.csv"),
                    ("Images",        "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                    ("Documents",     "*.odf *.txt *.csv"),
                ],
                parent=top,
            )
            if paths:
                new_paths = self._copy_attachments(list(paths))
                task.attachments.extend(new_paths)
                self._save_async()
                _refresh_list()
                self.refresh_tasks()

        def _open_selected():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Open", "Select a file first.", parent=top)
                return
            path = task.attachments[sel[0]]
            if os.path.exists(path):
                share_module.open_file(path)
            else:
                messagebox.showerror("Not found",
                    f"File not found:\n{path}", parent=top)

        def _remove():
            sel = lb.curselection()
            if not sel:
                return
            idx  = sel[0]
            path = task.attachments[idx]
            if messagebox.askyesno("Remove attachment",
                f"Remove '{os.path.basename(path)}' from this task?\n"
                "(The file is NOT deleted from disk.)", parent=top):
                task.attachments.pop(idx)
                self._save_async()
                _refresh_list()
                self.refresh_tasks()

        def _reveal():
            sel = lb.curselection()
            if not sel:
                return
            path = task.attachments[sel[0]]
            if os.path.exists(path):
                share_module.reveal_in_folder(path)
            else:
                messagebox.showerror("Not found", f"File not found:\n{path}", parent=top)

        # Double-click to open
        lb.bind("<Double-Button-1>", lambda e: _open_selected())

        for label, cmd in [("📎 Add", _add), ("🔍 Open", _open_selected),
                            ("📂 Reveal", _reveal), ("🗑 Remove", _remove)]:
            b = tk.Button(btn_row, text=label, command=cmd,
                          bg=t["accent"] if label == "📎 Add" else t["surface2"],
                          fg=t["accent_fg"] if label == "📎 Add" else t["fg"],
                          activebackground=t["accent_hover"] if label == "📎 Add" else t["border"],
                          relief="flat", cursor="hand2",
                          font=("TkDefaultFont", 9, "bold" if label == "📎 Add" else "normal"),
                          padx=10)
            b.pack(side=tk.LEFT, padx=(8 if label == "📎 Add" else 4, 0), pady=10)

    def open_subtasks_gui(self):
        """Manage subtasks for the selected parent task."""
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showinfo("Subtasks", "Select a task first.")
            return

        # Only work on top-level tasks
        parent, sub = self.get_task_from_selection(selected[0])
        if sub is not None:
            messagebox.showinfo("Subtasks",
                "Select the parent task (not a subtask) to manage subtasks.")
            return
        task = parent
        if not task:
            return

        t   = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = self._make_dialog(f"◈  Subtasks — {task.name[:40]}")
        top.geometry("500x420")
        top.resizable(False, True)

        # Header with progress bar
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=f"◈  {task.name}",
                 font=("TkDefaultFont", 11, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=16, pady=(10, 2))
        self._prog_lbl = tk.Label(hdr, text="",
                                  font=("TkDefaultFont", 9),
                                  bg=t["surface"], fg=t["muted_fg"])
        self._prog_lbl.pack(anchor="w", padx=16, pady=(0, 8))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        def _update_progress():
            done, total = task.subtask_progress
            pct = int(done / total * 100) if total else 0
            self._prog_lbl.configure(
                text=f"{done}/{total} subtasks done  ({pct}%)"
            )

        # Subtask list
        list_frame = tk.Frame(top, bg=t["bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        lb = tk.Listbox(
            list_frame, bg=t["entry_bg"], fg=t["fg"],
            selectbackground=t["accent"], selectforeground=t["accent_fg"],
            relief="flat", font=("TkDefaultFont", 10),
            highlightthickness=1, highlightbackground=t["border"],
            activestyle="none",
        )
        lb.pack(fill=tk.BOTH, expand=True)

        def _refresh_lb():
            lb.delete(0, tk.END)
            for s in task.subtasks:
                check = "☑" if s.done else "☐"
                prio  = {"High": "🔥", "Medium": "⚡", "Low": "🌿"}.get(s.priority, "")
                due   = f"  {s.due_date.strftime('%d %b')}" if s.due_date else ""
                lb.insert(tk.END, f"{check} {prio} {s.name}{due}")
            _update_progress()

        _refresh_lb()

        # ── Add subtask row ───────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)
        add_frame = tk.Frame(top, bg=t["bg"])
        add_frame.pack(fill=tk.X, padx=14, pady=8)

        tk.Label(add_frame, text="New subtask:",
                 font=("TkDefaultFont", 9), bg=t["bg"], fg=t["muted_fg"]).pack(side=tk.LEFT)
        name_var = tk.StringVar()
        name_entry = tk.Entry(
            add_frame, textvariable=name_var, width=26,
            bg=t["entry_bg"], fg=t["fg"],
            insertbackground=t["fg"], relief=tk.FLAT,
            font=("TkDefaultFont", 10),
            highlightthickness=1, highlightbackground=t["border"],
        )
        name_entry.pack(side=tk.LEFT, padx=(6, 4))

        prio_var = tk.StringVar(value="⚡ Medium")
        pm = tk.OptionMenu(add_frame, prio_var, "🔥 High", "⚡ Medium", "🌿 Low")
        pm.configure(bg=t["surface2"], fg=t["fg"],
                     activebackground=t["border"], relief="flat", font=("TkDefaultFont", 9))
        pm.pack(side=tk.LEFT, padx=(0, 4))

        def _add_sub():
            name = name_var.get().strip()
            if not name:
                return
            task.add_subtask(name, priority=prio_var.get().split()[-1])
            name_var.set("")
            _refresh_lb()
            self.refresh_tasks()
            self._save_async()

        add_btn = tk.Button(
            add_frame, text="Add", command=_add_sub,
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"],
            relief=tk.FLAT, cursor="hand2",
            font=("TkDefaultFont", 9, "bold"), padx=8,
        )
        add_btn.pack(side=tk.LEFT)
        name_entry.bind("<Return>", lambda e: _add_sub())

        # ── Action buttons ────────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)
        btn_row = tk.Frame(top, bg=t["surface"], height=50)
        btn_row.pack(fill=tk.X)
        btn_row.pack_propagate(False)

        def _toggle_done_sub():
            sel = lb.curselection()
            if not sel:
                return
            sub = task.subtasks[sel[0]]
            sub.done = not sub.done
            if sub.done:
                sub.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                sub.completed_at = None
            _refresh_lb()
            self.refresh_tasks()
            self._save_async()

        def _remove_sub():
            sel = lb.curselection()
            if not sel:
                return
            sub = task.subtasks[sel[0]]
            if messagebox.askyesno("Remove subtask",
                    f"Remove subtask '{sub.name}'?", parent=top):
                task.remove_subtask(sub)
                _refresh_lb()
                self.refresh_tasks()
                self._save_async()

        def _move_up():
            sel = lb.curselection()
            if not sel or sel[0] == 0:
                return
            idx = sel[0]
            task.subtasks[idx], task.subtasks[idx-1] = task.subtasks[idx-1], task.subtasks[idx]
            _refresh_lb()
            lb.selection_set(idx - 1)
            self._save_async()

        def _move_down():
            sel = lb.curselection()
            if not sel or sel[0] >= len(task.subtasks) - 1:
                return
            idx = sel[0]
            task.subtasks[idx], task.subtasks[idx+1] = task.subtasks[idx+1], task.subtasks[idx]
            _refresh_lb()
            lb.selection_set(idx + 1)
            self._save_async()

        for label, cmd in [
            ("☑ Toggle done", _toggle_done_sub),
            ("↑ Move up",     _move_up),
            ("↓ Move down",   _move_down),
            ("🗑 Remove",      _remove_sub),
        ]:
            tk.Button(btn_row, text=label, command=cmd,
                      bg=t["surface2"], fg=t["fg"],
                      activebackground=t["border"],
                      relief=tk.FLAT, cursor="hand2",
                      font=("TkDefaultFont", 9), padx=8
                      ).pack(side=tk.LEFT, padx=(8, 0), pady=10)

    def _spawn_recurrence(self, source_task, next_due):
        """Create the next occurrence of a recurring task."""
        from core.tasks import Task as _Task
        new_task = _Task(
            source_task.name,
            source_task.description,
            next_due,
            source_task.priority,
        )
        new_task.category   = source_task.category
        new_task.recurrence = source_task.recurrence
        cmd = AddTaskCommand(self.manager, new_task)
        self.history.execute(cmd)

    # ═══════════════════════════════════════════════
    #  DIALOG WIDGET HELPERS
    # ═══════════════════════════════════════════════

    def _make_dialog(self, title):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        top = tk.Toplevel(self.root)
        top.title(title)
        top.configure(bg=t["bg"])
        top.grab_set()
        top.resizable(False, False)
        return top

    def _lbl(self, t):
        return {"bg": t["bg"], "fg": t["fg"], "font": ("TkDefaultFont", 11)}

    def _entry(self, parent, t, width=30):
        return tk.Entry(
            parent, width=width, relief="flat",
            bg=t["entry_bg"], fg=t["fg"],
            insertbackground=t["fg"],
            font=("TkDefaultFont", 11),
            highlightthickness=1,
            highlightbackground=t["border"],
            highlightcolor=t["accent"]
        )

    def _btn(self, parent, t, text, cmd, primary=False):
        if primary:
            return tk.Button(
                parent, text=text, command=cmd, relief="flat", cursor="hand2",
                bg=t["accent"], fg=t["accent_fg"],
                activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
                font=("TkDefaultFont", 11, "bold"), padx=20, pady=8
            )
        return tk.Button(
            parent, text=text, command=cmd, relief="flat", cursor="hand2",
            bg=t["secondary_btn_bg"], fg=t["secondary_btn_fg"],
            activebackground=t["border"],
            font=("TkDefaultFont", 10), padx=12, pady=6
        )

    # ═══════════════════════════════════════════════
    #  FILTERING & SORTING
    # ═══════════════════════════════════════════════

    def _sort_by_column(self, col):
        """Called when a column header is clicked — toggles asc/desc."""
        sort_key = self._col_sort_map.get(col, "alphabetical")
        if self.sort_type.get() == sort_key:
            self.sort_reverse = not self.sort_reverse   # flip direction
        else:
            self.sort_type.set(sort_key)
            self.sort_reverse = False                   # reset to asc on new column
        self._update_sort_buttons()
        self.refresh_tasks()

    # ═══════════════════════════════════════════════
    #  CALENDAR SIDEBAR
    # ═══════════════════════════════════════════════

    def _on_calendar_day_click(self, event):
        """Filter task list to the selected day."""
        date_str = self.mini_cal.get_date()          # "yyyy-mm-dd"
        try:
            self._calendar_date_filter = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            self._calendar_date_filter = None
        self.refresh_tasks()

    def _calendar_reset(self):
        """Clear the calendar day filter and show all tasks."""
        self._calendar_date_filter = None
        self.refresh_tasks()

    def refresh_calendar(self):
        """Re-draw task-day markers on the mini calendar (batched — single redraw)."""
        self.mini_cal._begin_update()
        try:
            # Remove all existing events (no redraws during batch)
            self.mini_cal._events.clear()

            # Pre-build task-by-date lookup for tooltip hover
            self._tasks_by_date = {}
            today = datetime.now().date()
            for task in self.manager.tasks:
                if not task.due_date:
                    continue
                due = task.due_date if not isinstance(task.due_date, str) else \
                      datetime.strptime(task.due_date, "%Y-%m-%d").date()
                self._tasks_by_date.setdefault(due, []).append(task)
                if task.done:
                    tag = "done"
                elif due < today:
                    tag = "overdue"
                elif task.priority == "High":
                    tag = "high"
                else:
                    tag = "normal"
                self.mini_cal.calevent_create(due, task.name, tag)

            # Style the tags on the calendar (no redraws during batch)
            if self.dark_mode:
                self.mini_cal.tag_config("done",    background="#3A3F4B", foreground="#6EE7A0")
                self.mini_cal.tag_config("overdue", background="#3D1A1A", foreground="#F87171")
                self.mini_cal.tag_config("high",    background="#3D2A1A", foreground="#FCD34D")
                self.mini_cal.tag_config("normal",  background="#1A2E3D", foreground="#93C5FD")
            else:
                self.mini_cal.tag_config("done",    background="#D1FAE5", foreground="#065F46")
                self.mini_cal.tag_config("overdue", background="#FEE2E2", foreground="#991B1B")
                self.mini_cal.tag_config("high",    background="#FEF3C7", foreground="#92400E")
                self.mini_cal.tag_config("normal",  background="#DBEAFE", foreground="#1E40AF")
        finally:
            self.mini_cal._end_update()  # single redraw here
        # Trigger tooltip rebind (canvas-based, happens immediately)
        self._bind_cal_day_tooltips()

    # ═══════════════════════════════════════════════
    #  CALENDAR TOOLTIP
    # ═══════════════════════════════════════════════

    def _bind_nav_buttons(self):
        """Attach month-change triggers to canvas calendar nav buttons."""
        for btn in (self.mini_cal._l_month, self.mini_cal._r_month,
                    self.mini_cal._l_year,  self.mini_cal._r_year):
            btn.bind("<ButtonRelease-1>",
                     lambda e: self.refresh_calendar(), add="+")
        self.mini_cal.bind("<<CalendarMonthChanged>>",
                           lambda e: self.refresh_calendar())

    def _bind_cal_day_tooltips(self):
        """
        Bind Motion/Leave on the canvas for per-day hover tooltips.
        The MiniCalendar already handles hover highlighting internally;
        we just need to show our custom task tooltip on the canvas.
        """
        canvas = self.mini_cal._canvas

        def _motion(event):
            d = self.mini_cal._hit(event.x, event.y)
            if d == self._cal_tooltip_date:
                return
            self._hide_cal_tooltip()
            self._cal_tooltip_date = d
            if d:
                tasks_on_day = getattr(self, '_tasks_by_date', {}).get(d, [])
                if tasks_on_day:
                    self._show_cal_tooltip(event, tasks_on_day)

        def _leave(event):
            self._hide_cal_tooltip()
            self._cal_tooltip_date = None

        canvas.bind("<Motion>", _motion, add="+")
        canvas.bind("<Leave>",  _leave,  add="+")

    def _on_cal_day_enter(self, event, cell_date):
        if cell_date == self._cal_tooltip_date:
            return                     # already showing this day
        self._hide_cal_tooltip()
        tasks_on_day = [
            t for t in self.manager.tasks
            if t.due_date and t.due_date == cell_date
        ]
        if not tasks_on_day:
            return
        self._cal_tooltip_date = cell_date
        self._show_cal_tooltip(event, tasks_on_day)

    def _on_cal_day_leave(self, event):
        self._hide_cal_tooltip()

    def _on_cal_hover(self, event):
        pass   # kept so old bind("<Motion>") call is harmless

    def _on_cal_leave(self, event):
        self._hide_cal_tooltip()

    def _show_cal_tooltip(self, event, tasks):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        win = tk.Toplevel(self.root)
        win.wm_overrideredirect(True)          # borderless
        win.attributes("-topmost", True)
        win.configure(bg=t["border"])          # 1px border via bg bleed

        inner = tk.Frame(win, bg=t["surface2"], padx=10, pady=8)
        inner.pack(padx=1, pady=1)             # 1px gap = border illusion

        for i, task in enumerate(tasks):
            if i > 0:
                tk.Frame(inner, height=1, bg=t["border"]).pack(fill=tk.X, pady=4)

            icon = {"High": "🔥", "Medium": "⚡", "Low": "🌿"}.get(task.priority, "•")
            cat  = getattr(task, "category", "General")
            done_prefix = "✅ " if task.done else ""

            # Task name row
            name_row = tk.Frame(inner, bg=t["surface2"])
            name_row.pack(fill=tk.X)
            tk.Label(
                name_row,
                text=f"{done_prefix}{icon}  {task.name}",
                bg=t["surface2"], fg=t["fg"],
                font=("TkDefaultFont", 9, "bold"),
                anchor="w"
            ).pack(side=tk.LEFT)

            # Category badge
            from core import categories as cat_module
            bg_cat, fg_cat = cat_module.get_color(cat, self.categories, self.dark_mode, self.category_colors)
            tk.Label(
                name_row,
                text=f" {cat} ",
                bg=bg_cat, fg=fg_cat,
                font=("TkDefaultFont", 7, "bold"),
                padx=3, pady=1
            ).pack(side=tk.RIGHT, padx=(6, 0))

            # Description (if any)
            if task.description:
                tk.Label(
                    inner,
                    text=task.description,
                    bg=t["surface2"], fg=t["muted_fg"],
                    font=("TkDefaultFont", 8),
                    anchor="w", justify="left",
                    wraplength=200
                ).pack(fill=tk.X, pady=(2, 0))

        # Give the window an off-screen position first, render it, then move it
        win.geometry("+9999+9999")
        win.update_idletasks()               # forces Tk to compute actual size

        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()

        x = event.x_root + 14
        y = event.y_root + 10
        if x + w > sw:
            x = event.x_root - w - 6
        if y + h > sh:
            y = event.y_root - h - 6

        win.geometry(f"+{x}+{y}")
        self._cal_tooltip_win = win

    def _hide_cal_tooltip(self):
        if self._cal_tooltip_win:
            try:
                self._cal_tooltip_win.destroy()
            except Exception:
                pass
            self._cal_tooltip_win = None
        self._cal_tooltip_date = None

    # ═══════════════════════════════════════════════
    #  HOVER
    # ═══════════════════════════════════════════════

    def _on_tree_hover(self, event):
        row_id = self.task_tree.identify_row(event.y)
        if row_id == self._hovered_row:
            return
        # Clear previous hover tag
        if self._hovered_row and self.task_tree.exists(self._hovered_row):
            current_tags = list(self.task_tree.item(self._hovered_row, "tags"))
            current_tags = [t for t in current_tags if t != "hover"]
            self.task_tree.item(self._hovered_row, tags=current_tags)
        # Apply hover tag to new row
        self._hovered_row = row_id
        if row_id:
            current_tags = list(self.task_tree.item(row_id, "tags"))
            if "hover" not in current_tags:
                self.task_tree.item(row_id, tags=current_tags + ["hover"])

    def _on_tree_leave(self, event):
        if self._hovered_row and self.task_tree.exists(self._hovered_row):
            current_tags = list(self.task_tree.item(self._hovered_row, "tags"))
            current_tags = [t for t in current_tags if t != "hover"]
            self.task_tree.item(self._hovered_row, tags=current_tags)
        self._hovered_row = None

    def _on_tree_click(self, event):
        """Toggle task done/undone when the checkbox (Done) column is clicked."""
        region = self.task_tree.identify_region(event.x, event.y)
        col    = self.task_tree.identify_column(event.x)
        row_id = self.task_tree.identify_row(event.y)

        if region == "cell" and col == "#1" and row_id:
            task = self._get_task(row_id)
            if task:
                was_done = task.done
                cmd = ToggleDoneCommand(task)
                self.history.execute(cmd)
                # Spawn next occurrence when ticking a recurring task done
                if not was_done and task.done and task.recurrence and task.due_date:
                    next_due = task.next_due_date()
                    if next_due:
                        self._spawn_recurrence(task, next_due)
                self.refresh_tasks()
                self._update_undo_redo_buttons()
                self._save_async()
            return "break"

    def get_task_from_selection(self, item_id):
        """Return (parent_task, subtask_or_None). subtask is None for top-level rows."""
        raw_name = self.task_tree.item(item_id, "values")[1]
        # Strip badges
        name = raw_name.split("  🔁")[0].split("  📎")[0].split("  ◈")[0].strip()

        parent_id = self.task_tree.parent(item_id)
        if parent_id:
            # It's a subtask row — find the parent first
            parent_raw = self.task_tree.item(parent_id, "values")[1]
            parent_name = parent_raw.split("  🔁")[0].split("  📎")[0].split("  ◈")[0].strip()
            for task in self.manager.tasks:
                if task.name == parent_name:
                    # name has "  ↳ " prefix stripped
                    clean = name.lstrip("↳ ").strip()
                    for sub in task.subtasks:
                        if sub.name == clean:
                            return (task, sub)
            return (None, None)

        for task in self.manager.tasks:
            if task.name == name:
                return (task, None)
        return (None, None)

    def _get_task(self, item_id):
        """Convenience — return just the Task (parent or subtask)."""
        parent, sub = self.get_task_from_selection(item_id)
        return sub if sub is not None else parent

    def get_filtered_tasks(self):
        tasks = logic.get_filtered_tasks(
            self.manager.tasks,
            self.filter_type.get(),
            self.search_var.get(),
            self._calendar_date_filter,
        )
        if self._category_filter:
            tasks = [t for t in tasks if getattr(t, "category", "General") == self._category_filter]
        return tasks

    def get_sorted_tasks(self):
        return logic.get_sorted_tasks(
            self.get_filtered_tasks(),
            self.sort_type.get(),
            self.sort_reverse,
        )

    @staticmethod
    def _days_info(task):
        return logic.days_info(task)

    # ═══════════════════════════════════════════════
    #  REFRESH
    # ═══════════════════════════════════════════════

    def refresh_tasks(self):
        if hasattr(self, "_reminder_svc"):
            self._reminder_svc.reset_fired()

        # ── Batch-delete all existing rows ────────────────────────────────────
        tree = self.task_tree
        children = tree.get_children()
        if children:
            tree.delete(*children)   # single call vs looping delete

        tasks   = self.get_sorted_tasks()
        today   = datetime.now().date()   # compute once
        total   = len(self.manager.tasks)
        done_c  = sum(1 for t in self.manager.tasks if t.done)
        self.count_label.configure(text=f"{total - done_c} remaining · {done_c} done")

        # Hoist constants out of the loop
        RECUR_ICON  = {"Daily": "🔁 Daily", "Weekly": "🔁 Weekly", "Monthly": "🔁 Monthly"}
        prio_icons  = PRIORITY_ICONS
        days_info_fn = self._days_info

        # ── Single-pass treeview population ───────────────────────────────────
        for t in tasks:
            if isinstance(t.due_date, str):
                t.due_date = datetime.strptime(t.due_date, "%Y-%m-%d").date() if t.due_date else None

            due_str      = t.due_date.strftime("%Y-%m-%d") if t.due_date else "—"
            days_info    = "" if t.done else days_info_fn(t)
            checkbox     = "☑" if t.done else "☐"
            category     = t.category if hasattr(t, "category") else "General"
            recurrence   = t.recurrence if hasattr(t, "recurrence") else None
            attachments  = t.attachments if hasattr(t, "attachments") else []
            subtasks     = t.subtasks    if hasattr(t, "subtasks")    else []

            display_name = t.name
            if recurrence:
                display_name += f"  {RECUR_ICON[recurrence]}"
            if attachments:
                display_name += f"  📎{len(attachments)}"
            if subtasks:
                done_sub = sum(1 for s in subtasks if s.done)
                display_name += f"  ◈ {done_sub}/{len(subtasks)}"

            # Determine tag once
            if t.done:
                tag = "done"
            elif t.due_date and t.due_date < today:
                tag = "overdue"
            elif t.priority == "High":
                tag = "high"
            elif t.priority == "Medium":
                tag = "medium"
            else:
                tag = "low"

            row_id = tree.insert(
                "", tk.END,
                values=(checkbox, display_name, category,
                        prio_icons.get(t.priority, t.priority),
                        due_str, days_info, t.description),
                open=True,
                tags=(tag,),   # pass tag in insert, not a separate item() call
            )

            for sub in subtasks:
                sub_due   = sub.due_date.strftime("%Y-%m-%d") if sub.due_date else "—"
                sub_days  = "" if sub.done else days_info_fn(sub)
                sub_tag   = ("done" if sub.done else
                             "high" if sub.priority == "High" else
                             "medium" if sub.priority == "Medium" else "low")
                tree.insert(
                    row_id, tk.END,
                    values=("☑" if sub.done else "☐", f"  ↳ {sub.name}", "",
                            prio_icons.get(sub.priority, sub.priority),
                            sub_due, sub_days, sub.description),
                    tags=(sub_tag,),
                )

        # Only reconfigure tags when theme changes (moved to apply_theme)
        if not hasattr(self, '_tags_configured'):
            self._configure_tags()
            self._tags_configured = True

        # Update column sort headers
        active_sort = self.sort_type.get()
        arrow = "  ▼" if self.sort_reverse else "  ▲"
        for col, sort_key in self._col_sort_map.items():
            tree.heading(col, text=col + (arrow if sort_key == active_sort else ""),
                         command=lambda c=col: self._sort_by_column(c))

        # Defer expensive sidebar/tray updates to avoid blocking the UI
        self.root.after(1, self.refresh_calendar)
        self.root.after(1, self.refresh_stats)
        self.root.after(50, self._refresh_tray)

    def refresh_stats(self):
        """Recalculate all dashboard stat values and redraw the progress bar."""
        from datetime import date, timedelta
        today = date.today()
        week_end = today + timedelta(days=7)
        all_tasks = self.manager.tasks

        total   = len(all_tasks)
        done    = sum(1 for t in all_tasks if t.done)
        active  = total - done
        overdue = sum(
            1 for t in all_tasks
            if not t.done and t.due_date and t.due_date < today
        )
        due_today = sum(
            1 for t in all_tasks
            if t.due_date and not t.done and t.due_date == today
        )
        due_week  = sum(
            1 for t in all_tasks
            if t.due_date and not t.done and today <= t.due_date <= week_end
        )
        pct = int(done / total * 100) if total else 0

        # Update stat value labels
        values = {
            "total":   str(total),
            "active":  str(active),
            "done":    str(done),
            "overdue": str(overdue) if overdue == 0 else f"⚠ {overdue}",
            "today":   str(due_today),
            "week":    str(due_week),
        }
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        for key, (row, lbl, val) in self._stat_widgets.items():
            val.configure(text=values[key])
            # Highlight overdue count in red if non-zero
            if key == "overdue" and overdue > 0:
                val.configure(fg="#F87171" if self.dark_mode else "#DC2626")
            elif key == "today" and due_today > 0:
                val.configure(fg=t["accent"])
            else:
                val.configure(fg=t["fg"])

        # Progress bar
        self.progress_pct_label.configure(text=f"{pct}%")
        self.progress_canvas.update_idletasks()
        w = self.progress_canvas.winfo_width() or 180
        self.progress_canvas.delete("all")
        # Track
        self.progress_canvas.create_rectangle(
            0, 0, w, 6, fill=t["border"], outline="", width=0
        )
        # Fill
        if pct > 0:
            fill_color = t["accent"] if pct < 100 else "#4ADE80"
            self.progress_canvas.create_rectangle(
                0, 0, int(w * pct / 100), 6,
                fill=fill_color, outline="", width=0
            )
        # Heatmap is expensive — only redraw if task count changed
        new_sig = len(self.manager.tasks)
        if not hasattr(self, "_heatmap_sig") or self._heatmap_sig != new_sig:
            self._heatmap_sig = new_sig
            self.refresh_heatmap()

    def refresh_heatmap(self):
        """Redraw the GitHub-style activity heatmap (last ~3 months, by due date)."""
        from datetime import date, timedelta
        from collections import defaultdict

        WEEKS    = 17
        DAYS     =  7
        CELL     =  9
        GAP      =  1
        LEFT_PAD = 14
        TOP_PAD  = 14

        t      = DARK_THEME if self.dark_mode else LIGHT_THEME
        canvas = self.heatmap_canvas
        canvas.delete("all")

        today       = date.today()
        # Anchor: Monday of current week is the start of the last column
        this_monday = today - timedelta(days=today.weekday())
        grid_origin = this_monday - timedelta(weeks=WEEKS - 1)   # always exactly 13 cols
        start_date  = grid_origin
        total_cols  = WEEKS   # always exactly 13

        # ── Count tasks per due date ──────────────────
        day_counts: dict = defaultdict(int)
        for task in self.manager.tasks:
            if task.due_date:
                try:
                    d = task.due_date
                    if start_date <= d <= today:
                        day_counts[d] += 1
                except (TypeError, AttributeError):
                    pass

        max_count = max(day_counts.values(), default=1)

        # ── Colour scale (4 shades + empty) ──────────
        if self.dark_mode:
            EMPTY  = "#1C1F26"
            SHADES = ["#0F3D20", "#1A6B38", "#25A055", "#2ECC6B"]
        else:
            EMPTY  = "#ECEAE6"
            SHADES = ["#C6E9D4", "#7BC99A", "#3AA865", "#1E7D44"]

        def _shade(count):
            if count == 0:
                return EMPTY
            ratio = count / max_count
            idx   = min(int(ratio * len(SHADES)), len(SHADES) - 1)
            return SHADES[idx]

        # ── Day-of-week labels (Mon Wed Fri) ──────────
        DAY_LABELS = {0: "M", 2: "W", 4: "F"}
        for dow, lbl in DAY_LABELS.items():
            y = TOP_PAD + dow * (CELL + GAP) + CELL // 2
            canvas.create_text(
                LEFT_PAD - 4, y,
                text=lbl, anchor="e",
                font=("TkDefaultFont", 7),
                fill=t["muted_fg"]
            )

        # ── Draw cells ────────────────────────────────
        month_labels = {}
        cell_meta    = {}

        for week_idx in range(total_cols):
            for dow in range(DAYS):
                d = grid_origin + timedelta(weeks=week_idx, days=dow)
                if d < start_date or d > today:
                    continue   # skip days outside our window

                x1 = LEFT_PAD + week_idx * (CELL + GAP)
                y1 = TOP_PAD  + dow      * (CELL + GAP)
                x2, y2 = x1 + CELL, y1 + CELL

                color = _shade(day_counts.get(d, 0))
                item_id = canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=color, outline="", width=0,
                )
                cell_meta[item_id] = (d, day_counts.get(d, 0))

                # Month label on first Monday-ish of each month
                if dow == 0 and d.day <= 7:
                    month_labels[x1] = d.strftime("%b")

        # ── Month labels along the top ─────────────────
        for x, label in month_labels.items():
            canvas.create_text(
                x, TOP_PAD - 4,
                text=label, anchor="sw",
                font=("TkDefaultFont", 7),
                fill=t["muted_fg"]
            )

        # ── Date range label ──────────────────────────
        self.heatmap_range_lbl.configure(
            text=f"{start_date.strftime('%d %b')} – {today.strftime('%d %b %Y')}",
            bg=t["bg"], fg=t["muted_fg"]
        )

        # ── Tooltip: track current hovered item id ────
        tip      = self._heatmap_tip
        tip["last_id"] = None   # last item id that triggered a tooltip

        def _show_tip(item_id, ex, ey):
            """Destroy old tip, create new one for item_id."""
            if tip["win"]:
                try:    tip["win"].destroy()
                except: pass
                tip["win"] = None

            d, count = cell_meta[item_id]
            label = d.strftime("%d %B %Y")
            msg   = f"{label}\n{'No activity' if count == 0 else f'{count} task' + ('' if count == 1 else 's')}"

            th = DARK_THEME if self.dark_mode else LIGHT_THEME
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=th["border"])
            tk.Label(
                win, text=msg,
                bg=th["surface2"], fg=th["fg"],
                font=("TkDefaultFont", 9),
                justify="center", padx=10, pady=6
            ).pack(padx=1, pady=1)
            win.update_idletasks()
            wx = canvas.winfo_rootx() + ex + 12
            wy = canvas.winfo_rooty() + ey - win.winfo_reqheight() - 4
            win.geometry(f"+{wx}+{wy}")
            tip["win"] = win

        def _on_motion(e):
            item = canvas.find_closest(e.x, e.y)
            if not item:
                return
            iid = item[0]
            if iid not in cell_meta:
                # Hovering over a label/text — hide tip
                if tip["win"]:
                    try:    tip["win"].destroy()
                    except: pass
                    tip["win"] = None
                tip["last_id"] = None
                return
            if iid == tip["last_id"]:
                return   # same cell, don't recreate
            tip["last_id"] = iid
            _show_tip(iid, e.x, e.y)

        def _on_leave(e):
            if tip["win"]:
                try:    tip["win"].destroy()
                except: pass
                tip["win"] = None
            tip["last_id"] = None

        canvas.bind("<Motion>", _on_motion)
        canvas.bind("<Leave>",  _on_leave)

    def _shortcut_delete(self):
        """Delete only when the task tree has focus (not while typing)."""
        focused = self.root.focus_get()
        if focused == self.task_tree:
            self.delete_task_gui()

    def _shortcut_escape(self):
        """Escape: clear search, then clear category/calendar filters."""
        if self.search_var.get():
            self.search_var.set("")
            return
        if self._category_filter:
            self._set_category_filter(None)
            return
        if self._calendar_date_filter:
            self._calendar_reset()

    def _focus_search(self):
        """Ctrl+F: focus the search box and select all."""
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)

    def _select_first_task(self):
        children = self.task_tree.get_children()
        if children:
            self.task_tree.selection_set(children[0])
            self.task_tree.focus(children[0])
            self.task_tree.see(children[0])

    def _select_last_task(self):
        children = self.task_tree.get_children()
        if children:
            self.task_tree.selection_set(children[-1])
            self.task_tree.focus(children[-1])
            self.task_tree.see(children[-1])

    def _show_shortcuts_help(self):
        """Show a floating keyboard shortcuts reference card."""
        # Don't open if a dialog is already showing shortcuts
        for w in self.root.winfo_children():
            if isinstance(w, tk.Toplevel) and getattr(w, "_is_shortcuts_help", False):
                w.lift()
                return

        top = self._make_dialog("Keyboard Shortcuts")
        top._is_shortcuts_help = True
        top.resizable(False, False)
        t = DARK_THEME if self.dark_mode else LIGHT_THEME

        SHORTCUTS = [
            ("TASKS", [
                ("Ctrl + N",     "New task"),
                ("Ctrl + E",     "Edit selected task"),
                ("Delete",       "Delete selected task"),
                ("Ctrl + D",     "Mark selected task done"),
                ("Double-click", "Edit task"),
            ]),
            ("UNDO / REDO", [
                ("Ctrl + Z",     "Undo"),
                ("Ctrl + Y",     "Redo"),
                ("Ctrl + Shift + Z", "Redo"),
            ]),
            ("NAVIGATION", [
                ("Ctrl + F",     "Focus search box"),
                ("Escape",       "Clear search / filters"),
                ("Ctrl + Home",  "Select first task"),
                ("Ctrl + End",   "Select last task"),
            ]),
            ("VIEW", [
                ("Ctrl + T",     "Toggle dark / light mode"),
                ("Ctrl + ,",     "Open Settings"),
                ("?",            "Show this help"),
            ]),
        ]

        # ── Header ────────────────────────────────────────
        hdr = tk.Frame(top, bg=t["surface"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⌨️  Keyboard Shortcuts",
                 font=("Georgia", 13, "bold"),
                 bg=t["surface"], fg=t["fg"]).pack(anchor="w", padx=18, pady=(14, 12))
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X)

        body = tk.Frame(top, bg=t["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)

        for section_title, rows in SHORTCUTS:
            # Section heading
            tk.Label(body, text=section_title,
                     font=("TkDefaultFont", 8, "bold"),
                     bg=t["bg"], fg=t["muted_fg"]).pack(anchor="w", pady=(12, 3))
            tk.Frame(body, height=1, bg=t["border"]).pack(fill=tk.X, pady=(0, 6))

            for keys, desc in rows:
                row = tk.Frame(body, bg=t["bg"])
                row.pack(fill=tk.X, pady=2)

                # Key badge(s)
                badge = tk.Label(
                    row, text=keys,
                    font=("TkDefaultFont", 9, "bold"),
                    bg=t["surface2"], fg=t["fg"],
                    padx=8, pady=3,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground=t["border"],
                )
                badge.pack(side=tk.LEFT)

                tk.Label(row, text=desc,
                         font=("TkDefaultFont", 10),
                         bg=t["bg"], fg=t["fg"],
                         anchor="w").pack(side=tk.LEFT, padx=(10, 0))

        # ── Footer ────────────────────────────────────────
        tk.Frame(top, height=1, bg=t["border"]).pack(fill=tk.X, side=tk.BOTTOM)
        foot = tk.Frame(top, bg=t["surface"], height=56)
        foot.pack(fill=tk.X, side=tk.BOTTOM)
        foot.pack_propagate(False)
        tk.Button(
            foot, text="Close", command=top.destroy,
            relief="flat", cursor="hand2",
            bg=t["accent"], fg=t["accent_fg"],
            activebackground=t["accent_hover"], activeforeground=t["accent_fg"],
            font=("TkDefaultFont", 11, "bold"),
        ).place(x=14, y=8, relwidth=1.0, width=-28, height=40)

        top.bind("<Escape>", lambda e: top.destroy())

        # Size to content
        top.update_idletasks()
        top.geometry(f"380x{top.winfo_reqheight() + 20}")

    # ═══════════════════════════════════════════════
    #  UNDO / REDO
    # ═══════════════════════════════════════════════

    def undo_action(self):
        desc = self.history.undo()
        if desc:
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            self._save_async()

    def redo_action(self):
        desc = self.history.redo()
        if desc:
            self.refresh_tasks()
            self._update_undo_redo_buttons()
            self._save_async()

    def _update_undo_redo_buttons(self):
        t = DARK_THEME if self.dark_mode else LIGHT_THEME
        can_undo = self.history.can_undo()
        can_redo = self.history.can_redo()

        self.undo_btn.configure(
            text="↩  Undo",
            state="normal" if can_undo else "disabled",
            fg=t["secondary_btn_fg"] if can_undo else t["muted_fg"],
        )
        self.redo_btn.configure(
            text="↪  Redo",
            state="normal" if can_redo else "disabled",
            fg=t["secondary_btn_fg"] if can_redo else t["muted_fg"],
        )
        # Bind live tooltips showing the exact action name
        self._bind_tooltip(self.undo_btn,
            lambda: self.history.undo_label() if self.history.can_undo() else "")
        self._bind_tooltip(self.redo_btn,
            lambda: self.history.redo_label() if self.history.can_redo() else "")

    def auto_save(self):
        self._save_async()
        # Only save config if geometry changed (avoids redundant disk writes)
        current_geo = self.root.geometry()
        if getattr(self, '_last_saved_geo', None) != current_geo:
            self._last_saved_geo = current_geo
            self.save_ui_config()
        self.root.after(10000, self.auto_save)

    # ═══════════════════════════════════════════════
    #  SYSTEM TRAY
    # ═══════════════════════════════════════════════

    def _make_tray_image(self, size=64):
        """Draw a simple checklist icon as the tray image."""
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        t    = DARK_THEME if self.dark_mode else LIGHT_THEME

        # Background circle
        accent = t["accent"]
        r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
        draw.ellipse([2, 2, size - 2, size - 2], fill=(r, g, b, 255))

        # Checkmark lines
        s = size / 64
        draw.line([(18*s, 34*s), (27*s, 44*s), (46*s, 20*s)],
                  fill=(255, 255, 255, 255), width=max(1, int(6*s)))
        return img

    def _build_tray_menu(self):
        """Build the right-click context menu shown on the tray icon."""
        from datetime import date as _date
        _today  = _date.today()
        total   = len(self.manager.tasks)
        done    = sum(1 for t in self.manager.tasks if t.done)
        overdue = sum(1 for t in self.manager.tasks
                      if not t.done and t.due_date and t.due_date < _today)
        label   = f"{total - done} active  •  {overdue} overdue"

        return pystray.Menu(
            pystray.MenuItem(label,           None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show window",   self._tray_show),
            pystray.MenuItem("Add task",      self._tray_add_task),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",          self._tray_quit),
        )

    def _start_tray(self):
        """Create and start the tray icon in a daemon thread."""
        if not TRAY_AVAILABLE or self._tray_icon:
            return
        import threading
        icon = pystray.Icon(
            "MyTasks",
            self._make_tray_image(),
            "My Tasks",
            menu=self._build_tray_menu(),
        )
        self._tray_icon = icon
        threading.Thread(target=icon.run, daemon=True).start()

    def _refresh_tray(self):
        """Rebuild tray menu and icon after task changes."""
        if not self._tray_icon:
            return
        self._tray_icon.menu  = self._build_tray_menu()
        self._tray_icon.icon  = self._make_tray_image()
        self._tray_icon.title = "My Tasks"

    def _tray_show(self, icon=None, item=None):
        """Restore the window from tray."""
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _tray_add_task(self, icon=None, item=None):
        """Open Add Task dialog from the tray menu."""
        self.root.after(0, lambda: (self._show_window(), self.add_task_gui()))

    def _tray_quit(self, icon=None, item=None):
        """Fully quit — save state, stop tray, destroy window."""
        self.root.after(0, self.on_close)

    def _start_reminders(self):
        self._reminder_svc = ReminderService(
            self.root,
            lambda: list(self.manager.tasks),
            self.reminder_cfg,
        )
        self._reminder_svc.start()

    def _start_api_server(self):
        """Start the local REST API server if enabled in config."""
        cfg = self.reminder_cfg   # reuse existing config dict for simplicity
        if not self.api_cfg.get("api_enabled", False):
            self._api_server = None
            return
        try:
            from api.server import TaskAPIServer
            from core.storage import save_tasks as _save
            port = self.api_cfg.get("api_port", 5000)
            self._api_server = TaskAPIServer(
                manager  = self.manager,
                save_fn  = _save,
                username = self.username,
                enc_key  = self.enc_key,
                port     = port,
            )
            self._api_server.start()
        except Exception as e:
            print(f"[API] Failed to start: {e}")
            self._api_server = None

    def _on_window_close(self):
        """Minimise to tray or quit depending on user preference."""
        if TRAY_AVAILABLE and self._tray_icon and self.minimize_to_tray:
            self.root.withdraw()
            self._refresh_tray()
        else:
            self.on_close()

    def on_close(self):
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        if hasattr(self, "_reminder_svc"):
            self._reminder_svc.stop()
        if hasattr(self, "_api_server") and self._api_server:
            self._api_server.stop()
        # Synchronous save on exit — must complete before window is destroyed
        save_tasks(self.manager, self.username, self.enc_key,
                   workspace=self.workspace)
        self.save_ui_config()
        self.root.destroy()