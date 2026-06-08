#!/usr/bin/env python3
"""
Teleprompter - a tiny always-on-top window that parks right under your webcam.

Shows two lines at a time: the CURRENT line bright on top, the NEXT line
dimmed below. Press SPACE (or click) to slide to the next line.

Several people can read off one PC: in Settings (press C) you assign a color to
a starting letter, so every line beginning with that letter shows in that color
(e.g. "J: my line" in red, "M: your line" in blue). Settings are saved to
teleprompter_config.json next to this script.

Run:  python teleprompter.py
"""

import os
import json
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, colorchooser

# ---------------------------------------------------------------- script source
# Put your script here (one line per line), OR press "E" to edit in the window,
# OR press "L" to load a .txt file.
DEFAULT_SCRIPT = """J: Welcome to your teleprompter.
M: Type your own script in this file,
J: or press E to edit, or L to load a .txt file.
M: Each line slides up as you press space.
J: Press C to set a color for a starting letter.
M: Lines starting with that letter show in that color.
J: Great for two people reading off one PC.
M: That's it - happy recording!"""

# Default letter -> color map (used the first time, before you customize it in
# Settings). After that, your choices live in teleprompter_config.json.
DEFAULT_SPEAKER_COLORS = {
    "J": "#ff6363",
    "M": "#4f8cff",
}
DEFAULT_COLOR = (255, 255, 255)
DIM_FACTOR = 0.62           # how far the "next" line fades toward black (0..1)

BG = (0, 0, 0)
STEPS = 14                  # animation frames
INTERVAL = 14               # ms between frames

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "teleprompter_config.json")


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def hexcol(rgb):
    return "#%02x%02x%02x" % rgb


def to_rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def dim_of(rgb):
    """A darkened version of a color, used for the upcoming (next) line."""
    return lerp(rgb, BG, DIM_FACTOR)


def ease(t):
    return 1 - (1 - t) ** 3      # ease-out cubic


class Teleprompter:
    def __init__(self, root):
        self.root = root
        self.lines = []
        self.idx = 0
        self.font_size = 40
        self.editing = False
        self.in_settings = False
        self.animating = False
        self.colors = {}             # letter -> (r, g, b)
        self.load_config()

        # --- window: always on top, borderless, dark, draggable -------------
        root.title("Teleprompter")
        root.configure(bg="black")
        root.attributes("-topmost", True)
        root.overrideredirect(True)          # remove title bar / borders
        root.geometry("900x230+200+120")
        root.attributes("-alpha", 0.96)

        self.font = tkfont.Font(family="Segoe UI", size=self.font_size, weight="bold")
        self.small = tkfont.Font(family="Segoe UI", size=11)

        # canvas holds the two animated text lines
        self.canvas = tk.Canvas(root, bg="black", highlightthickness=0, height=200)
        self.canvas.pack(fill="both", expand=True)

        self.cur_item = self.canvas.create_text(0, 0, text="", fill=hexcol(DEFAULT_COLOR),
                                                font=self.font, justify="center")
        self.next_item = self.canvas.create_text(0, 0, text="", fill=hexcol(BG),
                                                 font=self.font, justify="center")
        self.extra_item = self.canvas.create_text(0, 0, text="", fill=hexcol(BG),
                                                  font=self.font, justify="center")

        # hint / status bar
        self.hint = tk.Label(root, text=self.RUN_HINT, font=self.small,
                             fg="#777", bg="#111", anchor="center")
        self.hint.pack(fill="x", side="bottom")

        # editor (hidden until needed)
        self.editor = tk.Text(root, bg="#1c1c1c", fg="white", insertbackground="white",
                              font=("Segoe UI", 13), bd=0, padx=12, pady=12,
                              wrap="word", undo=True)

        # settings panel (hidden until needed)
        self.settings = tk.Frame(root, bg="#161616")

        # --- bindings -------------------------------------------------------
        root.bind("<space>", lambda e: self.next())
        root.bind("<Down>", lambda e: self.next())
        root.bind("<Right>", lambda e: self.next())
        root.bind("<Up>", lambda e: self.prev())
        root.bind("<Left>", lambda e: self.prev())
        root.bind("r", lambda e: self.restart())
        root.bind("R", lambda e: self.restart())
        root.bind("<plus>", lambda e: self.resize_font(4))
        root.bind("<KP_Add>", lambda e: self.resize_font(4))
        root.bind("<equal>", lambda e: self.resize_font(4))
        root.bind("<minus>", lambda e: self.resize_font(-4))
        root.bind("<KP_Subtract>", lambda e: self.resize_font(-4))
        root.bind("e", lambda e: self.toggle_edit())
        root.bind("E", lambda e: self.toggle_edit())
        root.bind("l", lambda e: self.load_file())
        root.bind("L", lambda e: self.load_file())
        root.bind("c", lambda e: self.toggle_settings())
        root.bind("C", lambda e: self.toggle_settings())
        root.bind("<Escape>", lambda e: self.on_escape())

        # click to advance; drag (left or right button) to move the window
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.hint.bind("<ButtonPress-3>", self._press)
        self.hint.bind("<B3-Motion>", self._drag)
        self.canvas.bind("<Configure>", lambda e: self.render())

        self.set_script(DEFAULT_SCRIPT)
        root.focus_force()

    RUN_HINT = ("SPACE/click next  ·  ←back  ·  R restart  ·  +/- size  ·  "
                "C colors  ·  E edit  ·  L load  ·  drag to move  ·  ESC quit")

    # -------------------------------------------------------------- config I/O
    def load_config(self):
        data = {}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        raw = data.get("speaker_colors", DEFAULT_SPEAKER_COLORS)
        self.colors = {}
        for letter, hexc in raw.items():
            if letter:
                try:
                    self.colors[letter[0].upper()] = to_rgb(hexc)
                except (ValueError, IndexError):
                    pass

    def save_config(self):
        data = {"speaker_colors": {k: hexcol(v) for k, v in self.colors.items()}}
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    # ---------------------------------------------------------- color lookup
    def color_for(self, text):
        """Base (bright) color for a line, picked from its first letter/digit."""
        for ch in text:
            if ch.isalnum():
                return self.colors.get(ch.upper(), DEFAULT_COLOR)
            if not ch.isspace():
                break
        return DEFAULT_COLOR

    # ---------------------------------------------------------- geometry helpers
    def positions(self):
        h = self.canvas.winfo_height() or 200
        w = self.canvas.winfo_width() or 900
        return w / 2, h * 0.33, h * 0.72, w - 40   # cx, y_cur, y_next, wrap

    def text_at(self, i):
        return self.lines[i] if 0 <= i < len(self.lines) else ""

    # -------------------------------------------------------------- script ops
    def set_script(self, text):
        self.lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        self.idx = 0
        self.render()

    def render(self):
        """Static layout: current line (bright) on top, next (dim) below.
        Each line is tinted by its speaker color."""
        cx, y_cur, y_next, wrap = self.positions()
        end = self.idx >= len(self.lines)
        cur_text = "— end —" if end else self.text_at(self.idx)
        next_text = self.text_at(self.idx + 1)
        self.canvas.itemconfig(self.cur_item, text=cur_text,
                               fill=hexcol(self.color_for(cur_text)), width=wrap)
        self.canvas.itemconfig(self.next_item, text=next_text,
                               fill=hexcol(dim_of(self.color_for(next_text))), width=wrap)
        self.canvas.itemconfig(self.extra_item, text="", fill=hexcol(BG), width=wrap)
        self.canvas.coords(self.cur_item, cx, y_cur)
        self.canvas.coords(self.next_item, cx, y_next)
        self.canvas.coords(self.extra_item, cx, y_next + (y_next - y_cur))

    # ------------------------------------------------------------- navigation
    def next(self):
        if self.editing or self.in_settings or self.animating:
            return
        if self.idx < len(self.lines):
            self.idx += 1
            self.animate(direction=1)

    def prev(self):
        if self.editing or self.in_settings or self.animating:
            return
        if self.idx > 0:
            self.idx -= 1
            self.animate(direction=-1)

    def restart(self):
        if self.editing or self.in_settings or self.animating:
            return
        self.idx = 0
        self.render()

    # -------------------------------------------------------------- animation
    def animate(self, direction):
        cx, y_cur, y_next, wrap = self.positions()
        gap = y_next - y_cur

        if direction == 1:
            # new current = lines[idx] (was the dim "next"); slide everything up
            t_out, t_cur, t_in = (self.text_at(self.idx - 1), self.text_at(self.idx),
                                  self.text_at(self.idx + 1))
            c_out, c_cur, c_in = (self.color_for(t_out), self.color_for(t_cur),
                                  self.color_for(t_in))
            self.canvas.itemconfig(self.cur_item, text=t_out,
                                   fill=hexcol(c_out), width=wrap)
            self.canvas.itemconfig(self.next_item, text=t_cur,
                                   fill=hexcol(dim_of(c_cur)), width=wrap)
            self.canvas.itemconfig(self.extra_item, text=t_in,
                                   fill=hexcol(BG), width=wrap)
            self.canvas.coords(self.cur_item, cx, y_cur)
            self.canvas.coords(self.next_item, cx, y_next)
            self.canvas.coords(self.extra_item, cx, y_next + gap)
            start = {self.cur_item: y_cur, self.next_item: y_next,
                     self.extra_item: y_next + gap}
            end = {self.cur_item: y_cur - gap, self.next_item: y_cur,
                   self.extra_item: y_next}
            cols = {self.cur_item: (c_out, BG), self.next_item: (dim_of(c_cur), c_cur),
                    self.extra_item: (BG, dim_of(c_in))}
        else:
            # going back: slide everything down
            t_cur, t_next, t_far = (self.text_at(self.idx), self.text_at(self.idx + 1),
                                    self.text_at(self.idx + 2))
            c_cur, c_next, c_far = (self.color_for(t_cur), self.color_for(t_next),
                                    self.color_for(t_far))
            self.canvas.itemconfig(self.cur_item, text=t_cur,
                                   fill=hexcol(BG), width=wrap)
            self.canvas.itemconfig(self.next_item, text=t_next,
                                   fill=hexcol(c_next), width=wrap)
            self.canvas.itemconfig(self.extra_item, text=t_far,
                                   fill=hexcol(dim_of(c_far)), width=wrap)
            self.canvas.coords(self.cur_item, cx, y_cur - gap)
            self.canvas.coords(self.next_item, cx, y_cur)
            self.canvas.coords(self.extra_item, cx, y_next)
            start = {self.cur_item: y_cur - gap, self.next_item: y_cur,
                     self.extra_item: y_next}
            end = {self.cur_item: y_cur, self.next_item: y_next,
                   self.extra_item: y_next + gap}
            cols = {self.cur_item: (BG, c_cur), self.next_item: (c_next, dim_of(c_next)),
                    self.extra_item: (dim_of(c_far), BG)}

        self.animating = True
        self._step(0, cx, start, end, cols)

    def _step(self, n, cx, start, end, cols):
        t = ease((n + 1) / STEPS)
        for item in start:
            y = start[item] + (end[item] - start[item]) * t
            self.canvas.coords(item, cx, y)
            c0, c1 = cols[item]
            self.canvas.itemconfig(item, fill=hexcol(lerp(c0, c1, t)))
        if n + 1 < STEPS:
            self.root.after(INTERVAL, self._step, n + 1, cx, start, end, cols)
        else:
            self.animating = False
            self.render()

    # ----------------------------------------------------------------- visuals
    def resize_font(self, delta):
        self.font_size = max(12, min(120, self.font_size + delta))
        self.font.configure(size=self.font_size)
        self.render()

    # -------------------------------------------------------- mouse / dragging
    def _press(self, event):
        self._ox, self._oy = event.x_root, event.y_root
        self._wx, self._wy = self.root.winfo_x(), self.root.winfo_y()
        self._moved = False

    def _drag(self, event):
        dx, dy = event.x_root - self._ox, event.y_root - self._oy
        if abs(dx) > 3 or abs(dy) > 3:
            self._moved = True
        self.root.geometry(f"+{self._wx + dx}+{self._wy + dy}")

    def _release(self, event):
        if not getattr(self, "_moved", False):
            self.next()       # a plain click (no drag) advances

    # -------------------------------------------------------------- edit mode
    def toggle_edit(self):
        if self.in_settings:
            return
        if self.editing:
            self.set_script(self.editor.get("1.0", "end"))
            self.editor.pack_forget()
            self.canvas.pack(fill="both", expand=True, before=self.hint)
            self.editing = False
            self.hint.config(text=self.RUN_HINT)
            self.root.focus_force()
            self.render()
        else:
            self.canvas.pack_forget()
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", "\n".join(self.lines))
            self.editor.pack(fill="both", expand=True, before=self.hint)
            self.editing = True
            self.hint.config(text="Editing — press E again (or ESC) to save & return")
            self.editor.focus_set()

    def load_file(self):
        if self.editing or self.in_settings:
            return
        path = filedialog.askopenfilename(
            title="Open script", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.set_script(f.read())
            except Exception as exc:
                self.canvas.itemconfig(self.cur_item, text=f"Could not open: {exc}")
        self.root.focus_force()

    # ------------------------------------------------------------- settings UI
    def toggle_settings(self):
        if self.editing:
            return
        if self.in_settings:
            self.settings.pack_forget()
            self.canvas.pack(fill="both", expand=True, before=self.hint)
            self.in_settings = False
            self.hint.config(text=self.RUN_HINT)
            self.root.focus_force()
            self.render()
        else:
            self.canvas.pack_forget()
            self.build_settings()
            self.settings.pack(fill="both", expand=True, before=self.hint)
            self.in_settings = True
            self.hint.config(text="Speaker colors — press C (or ESC) to close")

    def build_settings(self):
        for w in self.settings.winfo_children():
            w.destroy()

        tk.Label(self.settings, text="Speaker colors", bg="#161616", fg="white",
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
        tk.Label(self.settings,
                 text="Each line starting with a letter shows in that letter's color.",
                 bg="#161616", fg="#999", font=("Segoe UI", 10)).pack(anchor="w", padx=14)

        # --- add row ---
        add = tk.Frame(self.settings, bg="#161616")
        add.pack(fill="x", padx=14, pady=8)
        tk.Label(add, text="Letter:", bg="#161616", fg="#ccc",
                 font=("Segoe UI", 11)).pack(side="left")
        self.letter_var = tk.StringVar()
        entry = tk.Entry(add, textvariable=self.letter_var, width=3, justify="center",
                         font=("Segoe UI", 12), bg="#262626", fg="white",
                         insertbackground="white", bd=0)
        entry.pack(side="left", padx=(6, 10), ipady=3)
        tk.Button(add, text="Pick color & add", command=self.add_color,
                  bg="#4f8cff", fg="white", bd=0, padx=12, pady=4,
                  font=("Segoe UI", 10, "bold"), activebackground="#3a78ee",
                  cursor="hand2").pack(side="left")

        # --- list of current mappings ---
        listf = tk.Frame(self.settings, bg="#161616")
        listf.pack(fill="both", expand=True, padx=14, pady=(2, 10))
        if not self.colors:
            tk.Label(listf, text="No colors yet — add one above.", bg="#161616",
                     fg="#777", font=("Segoe UI", 10)).pack(anchor="w")
        for letter in sorted(self.colors):
            rgb = self.colors[letter]
            row = tk.Frame(listf, bg="#161616")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=" ", bg=hexcol(rgb), width=3).pack(side="left")
            tk.Label(row, text=f"  {letter}", bg="#161616", fg=hexcol(rgb),
                     font=("Segoe UI", 13, "bold"), width=4, anchor="w").pack(side="left")
            tk.Label(row, text=hexcol(rgb), bg="#161616", fg="#999",
                     font=("Consolas", 10), width=10, anchor="w").pack(side="left")
            tk.Button(row, text="Change",
                      command=lambda l=letter: self.add_color(l),
                      bg="#2a2a2a", fg="white", bd=0, padx=8, pady=2,
                      font=("Segoe UI", 9), activebackground="#383838",
                      cursor="hand2").pack(side="left", padx=4)
            tk.Button(row, text="Remove",
                      command=lambda l=letter: self.remove_color(l),
                      bg="#2a2a2a", fg="#ff8a8a", bd=0, padx=8, pady=2,
                      font=("Segoe UI", 9), activebackground="#383838",
                      cursor="hand2").pack(side="left")

    def add_color(self, letter=None):
        if letter is None:
            raw = self.letter_var.get().strip()
            if not raw:
                return
            letter = raw[0].upper()
        initial = hexcol(self.colors.get(letter, (255, 255, 255)))
        rgb, _ = colorchooser.askcolor(color=initial,
                                       title=f"Color for lines starting with '{letter}'")
        if rgb:
            self.colors[letter] = tuple(int(c) for c in rgb)
            self.letter_var.set("")
            self.save_config()
            self.build_settings()

    def remove_color(self, letter):
        self.colors.pop(letter, None)
        self.save_config()
        self.build_settings()

    # --------------------------------------------------------------- escape
    def on_escape(self):
        if self.editing:
            self.toggle_edit()
        elif self.in_settings:
            self.toggle_settings()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    Teleprompter(root)
    root.mainloop()
