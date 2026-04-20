import tkinter as tk
from tkinter import ttk, messagebox
import calendar
from datetime import datetime
import webbrowser
import sqlite3
import sys
import os
import re

DB_NAME = "Ca_sql.db"

def init_db():
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS bitacora (
                fecha_id  TEXT PRIMARY KEY,
                contenido TEXT,
                alarma    TEXT
            )
        """)

def cargar_nota(fecha_id: str) -> str:
    with sqlite3.connect(DB_NAME) as con:
        cur = con.execute("SELECT contenido FROM bitacora WHERE fecha_id=?", (fecha_id,))
        fila = cur.fetchone()
    return fila[0] or "" if fila else ""

def guardar_nota(fecha_id: str, contenido: str):
    with sqlite3.connect(DB_NAME) as con:
        con.execute("""
            INSERT INTO bitacora (fecha_id, contenido, alarma)
            VALUES (?, ?, '')
            ON CONFLICT(fecha_id) DO UPDATE SET contenido = excluded.contenido
        """, (fecha_id, contenido))

PATRON_ALARMA = re.compile(r"^\((\d{2}:\d{2})\)\s*(.*)")

def extraer_alarmas(contenido: str) -> list:
    """Retorna lista de (hora_hhmm, linea_completa) para cada línea con (HH:MM)."""
    alarmas = []
    for linea in contenido.splitlines():
        m = PATRON_ALARMA.match(linea.strip())
        if m:
            alarmas.append((m.group(1), linea.strip()))
    return alarmas

def sonar(root, mensaje: str):
    try:
        if sys.platform == "win32":
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 400)
        elif sys.platform == "darwin":
            os.system("afplay /System/Library/Sounds/Glass.aiff")
        else:
            os.system(
                "paplay /usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga "
                "2>/dev/null || aplay /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null"
            )
    except Exception:
        pass
    root.bell()
    messagebox.showwarning("⏰  ALARMA", mensaje)

class BlocNotas:
    def __init__(self, ventana, dia, mes, año):
        self.ventana  = ventana
        self.fecha_id = f"{dia}_{mes}_{año}"

        self.ventana.title(f"Nota: {dia} de {mes} {año}")
        self.ventana.geometry("440x520")
        self.ventana.configure(bg="#161616")

        # ── Instrucción ──────────────────────────────────────────────
        tk.Label(
            self.ventana,
            text="💡  Escribe (HH:MM) al inicio de una línea para poner alarma   |   Formato 24 h",
            bg="#1a2a1a", fg="#90ee90",
            font=("Arial", 9), pady=6
        ).pack(fill="x")

        # ── Área de texto ────────────────────────────────────────────
        self.texto = tk.Text(
            self.ventana,
            bg="#161616", fg="#ffffff",
            insertbackground="white",
            font=("Consolas", 12),
            padx=10, pady=10,
            relief="flat",
        )
        self.texto.pack(expand=True, fill="both", padx=10, pady=(8, 4))
        self.texto.tag_configure("alarma_tag", foreground="#FFD700", font=("Consolas", 12, "bold"))
        self.texto.bind("<KeyRelease>", self._resaltar)

        # ── Botón guardar ────────────────────────────────────────────
        tk.Button(
            self.ventana,
            text="💾  Guardar Nota",
            command=self.guardar,
            bg="#272222", fg="white",
            relief="flat", font=("Arial", 11),
            cursor="hand2", pady=6
        ).pack(fill="x", padx=10, pady=(0, 10))

        self._cargar()

    def _cargar(self):
        contenido = cargar_nota(self.fecha_id)
        if contenido:
            self.texto.insert("1.0", contenido)
            self._resaltar()

    def _resaltar(self, event=None):
        """Pinta en dorado las líneas que empiezan con (HH:MM)."""
        self.texto.tag_remove("alarma_tag", "1.0", tk.END)
        for i, linea in enumerate(self.texto.get("1.0", tk.END).splitlines(), start=1):
            if PATRON_ALARMA.match(linea.strip()):
                self.texto.tag_add("alarma_tag", f"{i}.0", f"{i}.end")

    def guardar(self):
        contenido = self.texto.get("1.0", tk.END).rstrip("\n")
        try:
            guardar_nota(self.fecha_id, contenido)
            alarmas = extraer_alarmas(contenido)
            detalle = "\n".join(f"  • {h}  →  {t}" for h, t in alarmas) if alarmas else "  (ninguna)"
            messagebox.showinfo(
                "Guardado ✓",
                f"Nota guardada en Ca_sql.db\n\nAlarmas detectadas:\n{detalle}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar: {e}")

class CalendarioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Calendario")
        self.root.resizable(True, True)
        self.root.configure(bg="#161616")

        self.ahora      = datetime.now()
        self.mes_actual = self.ahora.month
        self.año_actual = self.ahora.year

        self.meses_nombres = [
            "Enero","Febrero","Marzo","Abril","Mayo","Junio",
            "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre",
            "open plis"
        ]
        self.años_lista = list(range(2000, 2041))

        # "fecha_id|HH:MM"  — evita disparar la misma alarma dos veces
        self._disparadas = set()

        self.contenedor = ttk.Frame(self.root)
        self.contenedor.pack(expand=True, fill="both", padx=10, pady=10)

        frame_yt = ttk.Frame(self.contenedor)
        frame_yt.pack(pady=(10, 5))

        self.busqueda_yt = tk.Entry(
            frame_yt, bg="#1e1e1e", fg="#aaaaaa",
            insertbackground="white", font=("comic sans", 10),
            width=30, relief="flat"
        )
        self.busqueda_yt.insert(0, "YouTube")
        self.busqueda_yt.bind("<FocusIn>",  self._ph_clear)
        self.busqueda_yt.bind("<FocusOut>", self._ph_restore)
        self.busqueda_yt.bind("<Return>",   self.buscar_yt)
        self.busqueda_yt.pack(side="left", padx=(0, 5), ipady=4)

        tk.Button(frame_yt, text="▶", command=lambda: self.buscar_yt(None),
                  bg="#ff0000", fg="white", relief="flat",
                  font=("Arial", 11), cursor="heart").pack(side="left")

        controles = ttk.Frame(self.contenedor, border=20)
        controles.pack(pady=(10, 5))

        self.combo_mes = ttk.Combobox(controles, values=self.meses_nombres,
                                       state="readonly", width=15)
        self.combo_mes.set(self.meses_nombres[self.mes_actual - 1])
        self.combo_mes.grid(row=0, column=0, padx=10)
        self.combo_mes.bind("<<ComboboxSelected>>", self.actualizar_calendario)

        self.combo_año = ttk.Combobox(controles, values=self.años_lista,
                                       state="readonly", width=8)
        self.combo_año.set(self.año_actual)
        self.combo_año.grid(row=0, column=1, padx=5)
        self.combo_año.bind("<<ComboboxSelected>>", self.actualizar_calendario)

        style = ttk.Style()
        style.configure("TFrame", background="#161616")
        style.configure("TLabel", background="#161616", foreground="white")

        self.grid_dias = ttk.Frame(self.contenedor, style="TFrame")
        self.grid_dias.pack(pady=10, padx=10)

        self.dibujar_dias()
        self.verificar_alarmas()   # loop cada 20 s

    def verificar_alarmas(self):
        """
        Cada 20 segundos revisa la nota de HOY.
        Busca todas las líneas (HH:MM) y dispara las que coincidan
        con la hora actual (formato 24 h).
        """
        ahora      = datetime.now()
        hora_hm    = ahora.strftime("%H:%M")
        mes_nombre = self.meses_nombres[ahora.month - 1]
        fecha_id   = f"{ahora.day}_{mes_nombre}_{ahora.year}"

        contenido = cargar_nota(fecha_id)
        for hora, linea in extraer_alarmas(contenido):
            clave = f"{fecha_id}|{hora}"
            if hora == hora_hm and clave not in self._disparadas:
                self._disparadas.add(clave)
                sonar(self.root, f"📅 {fecha_id.replace('_', ' ')}\n\n{linea}")

        self.root.after(20_000, self.verificar_alarmas)


    def _ph_clear(self, e):
        if self.busqueda_yt.get() == "YouTube":
            self.busqueda_yt.delete(0, tk.END)
            self.busqueda_yt.config(fg="#C54A4A")

    def _ph_restore(self, e):
        if not self.busqueda_yt.get():
            self.busqueda_yt.insert(0, "YouTube")
            self.busqueda_yt.config(fg="#aaaaaa")

    def buscar_yt(self, e):
        q = self.busqueda_yt.get().strip()
        if q and q != "YouTube":
            webbrowser.open(f"https://www.youtube.com/results?search_query={q.replace(' ', '+')}")


    def dibujar_dias(self):
        for w in self.grid_dias.winfo_children():
            w.destroy()

        hoy = self.ahora
        for i, d in enumerate(["Lun","Mar","Mié","Jue","Vie","Sáb","Dom"]):
            ttk.Label(self.grid_dias, text=d,
                      font=("Arial", 10, "bold"), style="TLabel"
                      ).grid(row=0, column=i, padx=10, pady=(0, 10))

        for f, semana in enumerate(calendar.monthcalendar(self.año_actual, self.mes_actual)):
            for c, dia in enumerate(semana):
                if dia == 0:
                    continue

                es_hoy    = (dia == hoy.day and
                              self.mes_actual == hoy.month and
                              self.año_actual == hoy.year)
                fecha_id  = f"{dia}_{self.meses_nombres[self.mes_actual-1]}_{self.año_actual}"
                contenido = cargar_nota(fecha_id)

                tiene_alarma = bool(extraer_alarmas(contenido))
                tiene_nota   = bool(contenido.strip())

                if tiene_alarma:
                    bg, fg = "#3a2a00", "#FFD700"   # 🟡 dorado = alarma
                elif tiene_nota:
                    bg, fg = "#2a4a2a", "#90ee90"   # 🟢 verde  = nota
                elif es_hoy:
                    bg, fg = "#1e3a5f", "#7ec8e3"   # 🔵 azul   = hoy
                else:
                    bg, fg = "#161616", "#ffffff"

                tk.Button(
                    self.grid_dias, text=str(dia), width=4,
                    command=lambda d=dia: self.clic_en_dia(d),
                    bg=bg, fg=fg, relief="flat", cursor="hand2"
                ).grid(row=f + 1, column=c, padx=2, pady=2)

    def actualizar_calendario(self, event=None):
        nombre_mes = self.combo_mes.get()
        if nombre_mes == "open plis":
            webbrowser.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            return
        self.mes_actual = self.meses_nombres.index(nombre_mes) + 1
        self.año_actual = int(self.combo_año.get())
        self.dibujar_dias()

    def clic_en_dia(self, dia):
        mes_nombre = self.combo_mes.get()
        self.root.title(f"Día: {dia} | {mes_nombre} {self.año_actual}")
        v = tk.Toplevel(self.root)
        self.bloc = BlocNotas(v, dia, mes_nombre, self.año_actual)
        v.protocol("WM_DELETE_WINDOW", lambda: self._cerrar_nota(v))

    def _cerrar_nota(self, v):
        v.destroy()
        self.dibujar_dias()

if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    CalendarioApp(root)
    root.mainloop()
