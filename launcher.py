#!/usr/bin/env python3
"""
DST Proximity Voice - All-in-One Launcher & Auto-Setup
Autor: Robin & Antigravity
Unterstützt: Modernes GUI (wenn Tkinter vorhanden) & Farbiges CLI-Menü (wenn Tkinter fehlt)
Plattform: Linux (Ubuntu/Debian) & Windows 10/11
"""

import os
import sys
import json
import time
import math
import shutil
import ctypes
import threading
from pathlib import Path

# --- 1. Prüfen, ob GUI (Tkinter) verfügbar ist ---
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False


# --- 2. MumbleLink Shared Memory Manager ---
class LinkedMem(ctypes.Structure):
    _fields_ = [
        ("uiVersion", ctypes.c_uint32),
        ("uiTick", ctypes.c_uint32),
        ("fAvatarPosition", ctypes.c_float * 3),
        ("fAvatarFront", ctypes.c_float * 3),
        ("fAvatarTop", ctypes.c_float * 3),
        ("name", ctypes.c_wchar * 256),
        ("fCameraPosition", ctypes.c_float * 3),
        ("fCameraFront", ctypes.c_float * 3),
        ("fCameraTop", ctypes.c_float * 3),
        ("identity", ctypes.c_wchar * 256),
        ("context_len", ctypes.c_uint32),
        ("context", ctypes.c_ubyte * 256),
        ("description", ctypes.c_wchar * 2048),
    ]

class MumbleLinkManager:
    def __init__(self):
        self.tick = 0
        self.is_windows = sys.platform.startswith("win")
        self.mem = None
        self.lock = threading.Lock()
        self.running = True
        self._init_shared_memory()
        self._init_static_fields()
        self.ticker = threading.Thread(target=self._keepalive_loop, daemon=True)
        self.ticker.start()

    def _init_shared_memory(self):
        size = ctypes.sizeof(LinkedMem)
        if self.is_windows:
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            PAGE_READWRITE = 0x04
            FILE_MAP_ALL_ACCESS = 0xF001F
            handle = kernel32.CreateFileMappingW(
                wintypes.HANDLE(-1), None, PAGE_READWRITE, 0, size, "MumbleLink"
            )
            ptr = kernel32.MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, size)
            self.mem = LinkedMem.from_address(ptr)
        else:
            import mmap
            uid = os.getuid()
            self.shm_path = f"/dev/shm/MumbleLink.{uid}"
            self.shm_file = open(self.shm_path, "w+b")
            self.shm_file.truncate(size)
            self.mm = mmap.mmap(self.shm_file.fileno(), size)
            self.mem = LinkedMem.from_buffer(self.mm)
            try:
                if not os.path.exists("/dev/shm/MumbleLink"):
                    os.symlink(self.shm_path, "/dev/shm/MumbleLink")
            except Exception:
                pass

    def _init_static_fields(self):
        with self.lock:
            self.mem.uiVersion = 2
            self.mem.name = "Don't Starve Together"
            self.mem.description = "DST Proximity Voice Bridge"
            ctx = b"DST_PROXIMITY_WORLD"
            self.mem.context_len = len(ctx)
            for i, b in enumerate(ctx):
                self.mem.context[i] = b

            self.mem.fAvatarTop[0], self.mem.fAvatarTop[1], self.mem.fAvatarTop[2] = 0.0, 1.0, 0.0
            self.mem.fCameraTop[0], self.mem.fCameraTop[1], self.mem.fCameraTop[2] = 0.0, 1.0, 0.0
            self.mem.fAvatarFront[0], self.mem.fAvatarFront[1], self.mem.fAvatarFront[2] = 0.0, 0.0, 1.0
            self.mem.fCameraFront[0], self.mem.fCameraFront[1], self.mem.fCameraFront[2] = 0.0, 0.0, 1.0

    def update(self, x, y, z, rotation_deg):
        with self.lock:
            self.tick += 1
            self.mem.uiTick = self.tick
            self.mem.fAvatarPosition[0], self.mem.fAvatarPosition[1], self.mem.fAvatarPosition[2] = float(x), float(y), float(z)
            self.mem.fCameraPosition[0], self.mem.fCameraPosition[1], self.mem.fCameraPosition[2] = float(x), float(y), float(z)

            rad = math.radians(rotation_deg)
            fx, fz = -math.sin(rad), math.cos(rad)
            self.mem.fAvatarFront[0], self.mem.fAvatarFront[1], self.mem.fAvatarFront[2] = fx, 0.0, fz
            self.mem.fCameraFront[0], self.mem.fCameraFront[1], self.mem.fCameraFront[2] = fx, 0.0, fz

    def _keepalive_loop(self):
        while self.running:
            with self.lock:
                self.tick += 1
                self.mem.uiTick = self.tick
            time.sleep(0.1)

    def close(self):
        self.running = False


# --- 3. Konfiguration & Auto-Erkennung ---
CONFIG_FILE = Path.home() / ".dst_proximity_voice_config.json"

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"custom_log_path": ""}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

def auto_detect_dst_log():
    home = Path.home()
    candidates = [
        home / ".klei/DoNotStarveTogether/client_log.txt",
        home / "Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / "OneDrive/Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / "OneDrive/Dokumente/Klei/DoNotStarveTogether/client_log.txt",
        home / ".steam/steam/steamapps/compatdata/322330/pfx/drive_c/users/steamuser/Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / ".local/share/Steam/steamapps/compatdata/322330/pfx/drive_c/users/steamuser/Documents/Klei/DoNotStarveTogether/client_log.txt",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    klei_dir = home / ".klei/DoNotStarveTogether"
    if klei_dir.exists():
        found = list(klei_dir.glob("**/client_log.txt"))
        if found:
            return str(found[0])
    return ""

def auto_configure_mumble():
    """Richtet Mumble automatisch optimal für Proximity Chat ein."""
    is_windows = sys.platform.startswith("win")
    results = []

    if not is_windows:
        # 1. liblink.so in Mumble Plugins-Ordner kopieren
        system_liblink = Path("/usr/lib/x86_64-linux-gnu/mumble/plugins/liblink.so")
        target_dir = Path.home() / ".local/share/Mumble/Mumble/Plugins"
        if system_liblink.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / "liblink.so"
            if not target_file.exists():
                shutil.copy(system_liblink, target_file)
                results.append("Plugin liblink.so in Mumble-Ordner kopiert")
            else:
                results.append("Plugin liblink.so bereits vorhanden")

        # 2. mumble_settings.json anpassen
        settings_path = Path.home() / ".config/Mumble/Mumble/mumble_settings.json"
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                data.setdefault("positional_audio", {})
                data["positional_audio"]["enable_positional_audio"] = True
                data["positional_audio"]["transmit_position"] = True
                data["positional_audio"]["use_headphone_mode"] = True
                data["positional_audio"]["minimum_volume"] = 0.0
                data["positional_audio"]["minimum_distance"] = 3.0
                data["positional_audio"]["maximum_distance"] = 35.0

                data.setdefault("plugins", {})
                plugin_key = "0cbcab4f3d9b3bfe1cf72b763a856a1010cf3a94"
                data["plugins"][plugin_key] = {
                    "enabled": True,
                    "keyboard_monitoring_allowed": False,
                    "path": str(target_dir / "liblink.so"),
                    "positional_data_enabled": True
                }

                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                results.append("3D-Audio & Link-Plugin in Einstellungen aktiviert")
            except Exception as e:
                results.append(f"Settings Fehler: {e}")
    else:
        results.append("Unter Windows nutzt Mumble automatisch das interne MumbleLink-Modul.")

    return results


# --- 4. CLI Modus (Fallback, falls Tkinter nicht installiert ist) ---
def run_cli():
    cfg = load_config()
    log_path = cfg.get("custom_log_path") or auto_detect_dst_log()

    while True:
        print("\n" + "=" * 60)
        print("  🎙️  Don't Starve Together - Proximity Voice Launcher")
        print("=" * 60)
        
        if log_path and Path(log_path).exists():
            print(f" [✔] DST Logdatei: {log_path}")
        else:
            print(f" [⚠] DST Logdatei: Nicht gefunden! (Spiel noch nicht gestartet?)")

        shm_file = Path.home() / ".local/share/Mumble/Mumble/Plugins/liblink.so"
        if sys.platform.startswith("win") or shm_file.exists():
            print(" [✔] Mumble Status: Bereit für 3D-Verbindung")
        else:
            print(" [⚠] Mumble Status: Link-Plugin noch nicht eingerichtet")

        print("-" * 60)
        print(" [1] ▶ Voice Bridge Starten (Standard)")
        print(" [2] ⚙️  Mumble Auto-Setup ausführen")
        print(" [3] 📁 Pfad zur client_log.txt manuell ändern")
        print(" [4] ❌ Beenden")
        print("-" * 60)
        print(" Tipp: 'sudo apt install python3-tk' installiert das grafische Fenster.")
        print("-" * 60)

        choice = input("Wähle eine Option (1-4) [Enter für 1]: ").strip()
        if not choice or choice == "1":
            if not log_path or not Path(log_path).exists():
                print("\n[FEHLER] Keine gültige client_log.txt gefunden! Bitte wähle Option 3.")
                time.sleep(2)
                continue
            run_bridge_cli(log_path)
            break
        elif choice == "2":
            res = auto_configure_mumble()
            print("\nErgebnis:")
            for r in res:
                print(f" • {r}")
            input("\nDrücke ENTER zum Fortfahren...")
        elif choice == "3":
            new_path = input("\nGib den absoluten Pfad zu client_log.txt ein: ").strip()
            if new_path and Path(new_path).exists():
                log_path = new_path
                cfg["custom_log_path"] = new_path
                save_config(cfg)
                print("[OK] Pfad gespeichert!")
            else:
                print("[FEHLER] Datei existiert nicht!")
            time.sleep(1.5)
        elif choice == "4":
            print("Auf Wiedersehen!")
            sys.exit(0)

def run_bridge_cli(log_path):
    print("\n" + "=" * 60)
    print("  Starte Voice-Bridge... (Beenden mit Strg + C)")
    print("=" * 60)
    try:
        link = MumbleLinkManager()
        print("[OK] MumbleLink aktiv. Warte auf Bewegung im Spiel...\n")
    except Exception as e:
        print(f"[FEHLER] Konnte MumbleLink nicht starten: {e}")
        return

    last_status = ""
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)
            last_size = os.path.getsize(log_path)

            while True:
                try:
                    cur_size = os.path.getsize(log_path)
                    if cur_size < last_size:
                        f.seek(0, 0)
                    last_size = cur_size
                except Exception:
                    pass

                line = f.readline()
                if not line:
                    time.sleep(0.02)
                    continue

                if "[MUMBLE_LINK]" in line:
                    try:
                        parts = line.strip().split()
                        pos_str, rot_str = "", "0"
                        for p in parts:
                            if p.startswith("POS:"):
                                pos_str = p[4:]
                            elif p.startswith("ROT:"):
                                rot_str = p[4:]

                        if pos_str:
                            coords = [float(c) for c in pos_str.split(",")]
                            rot = float(rot_str)
                            link.update(coords[0], coords[1], coords[2], rot)

                            status = f"\r[VERBUNDEN] Position: X={coords[0]:.1f}, Z={coords[2]:.1f} | Blickrichtung={rot:.0f}°  "
                            if status != last_status:
                                print(status, end="", flush=True)
                                last_status = status
                    except Exception:
                        pass
    except KeyboardInterrupt:
        print("\n\nBridge beendet.")
    finally:
        link.close()


# --- 5. GUI Modus (Tkinter) ---
if HAS_TKINTER:
    class GuiApp(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("DST Proximity Voice - Setup & Launcher")
            self.geometry("640x580")
            self.minsize(580, 520)

            self.configure(bg="#1e1e24")
            self.style = ttk.Style(self)
            self.style.theme_use("clam")

            self.style.configure(".", background="#1e1e24", foreground="#ffffff", font=("Segoe UI", 10))
            self.style.configure("TLabel", background="#1e1e24", foreground="#e0e0e0")
            self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#ffd166")
            self.style.configure("Sub.TLabel", font=("Segoe UI", 9), foreground="#888899")
            self.style.configure("Card.TFrame", background="#2b2d42")
            self.style.configure("TEntry", fieldbackground="#13141c", foreground="#ffffff", bordercolor="#4a4e69")

            self.cfg = load_config()
            self.bridge_running = False
            self.link_manager = None
            self.bridge_thread = None

            self._build_ui()
            self._check_status()

        def _build_ui(self):
            header = ttk.Frame(self)
            header.pack(fill="x", padx=20, pady=(15, 10))
            ttk.Label(header, text="🎙️ DST Proximity Voice Chat", style="Header.TLabel").pack(anchor="w")
            ttk.Label(header, text="All-in-One Launcher & Auto-Setup für Mumble Link", style="Sub.TLabel").pack(anchor="w")

            # Card 1: DST Log
            dst_card = ttk.Frame(self, style="Card.TFrame", padding=12)
            dst_card.pack(fill="x", padx=20, pady=6)
            ttk.Label(dst_card, text="🎮 Don't Starve Together - Logdatei", font=("Segoe UI", 10, "bold"), background="#2b2d42", foreground="#ffd166").pack(anchor="w")

            path_row = ttk.Frame(dst_card, style="Card.TFrame")
            path_row.pack(fill="x", pady=(6, 0))
            
            self.dst_path_var = tk.StringVar(value=self.cfg.get("custom_log_path") or auto_detect_dst_log())
            self.dst_entry = ttk.Entry(path_row, textvariable=self.dst_path_var)
            self.dst_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

            btn_browse = tk.Button(path_row, text="Durchsuchen...", bg="#4a4e69", fg="#ffffff", activebackground="#6b7094", bd=0, padx=8, pady=3, command=self._browse_log)
            btn_browse.pack(side="right")

            self.lbl_dst_status = ttk.Label(dst_card, text="Status: Prüfe...", background="#2b2d42", font=("Segoe UI", 9))
            self.lbl_dst_status.pack(anchor="w", pady=(4, 0))

            # Card 2: Mumble
            mumble_card = ttk.Frame(self, style="Card.TFrame", padding=12)
            mumble_card.pack(fill="x", padx=20, pady=6)
            ttk.Label(mumble_card, text="🔊 Mumble Integration", font=("Segoe UI", 10, "bold"), background="#2b2d42", foreground="#ffd166").pack(anchor="w")

            mumble_row = ttk.Frame(mumble_card, style="Card.TFrame")
            mumble_row.pack(fill="x", pady=(6, 0))

            self.lbl_mumble_status = ttk.Label(mumble_row, text="Mumble Link wird geprüft...", background="#2b2d42")
            self.lbl_mumble_status.pack(side="left", fill="x", expand=True)

            btn_auto_fix = tk.Button(mumble_row, text="⚙️ Mumble Auto-Setup", bg="#118ab2", fg="#ffffff", activebackground="#06d6a0", bd=0, padx=10, pady=4, command=self._run_mumble_autofix)
            btn_auto_fix.pack(side="right")

            # Card 3: Live Status & Button
            bridge_card = ttk.Frame(self, style="Card.TFrame", padding=14)
            bridge_card.pack(fill="x", padx=20, pady=8)
            
            self.lbl_live_status = ttk.Label(
                bridge_card, 
                text="Bereit zum Starten. Starte Mumble & DST und klicke unten auf 'Bridge Starten'.", 
                background="#2b2d42", 
                wraplength=540,
                justify="center",
                font=("Segoe UI", 10)
            )
            self.lbl_live_status.pack(pady=8)

            self.btn_toggle = tk.Button(
                self, 
                text="▶ VOICE BRIDGE STARTEN", 
                font=("Segoe UI", 12, "bold"),
                bg="#06d6a0", 
                fg="#1e1e24", 
                activebackground="#05b386", 
                activeforeground="#1e1e24",
                bd=0, 
                pady=10, 
                command=self._toggle_bridge
            )
            self.btn_toggle.pack(fill="x", padx=20, pady=(10, 15))

        def _browse_log(self):
            f = filedialog.askopenfilename(
                title="client_log.txt auswählen",
                filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")]
            )
            if f:
                self.dst_path_var.set(f)
                self.cfg["custom_log_path"] = f
                save_config(self.cfg)
                self._check_status()

        def _check_status(self):
            p = Path(self.dst_path_var.get())
            if p.exists() and p.is_file():
                self.lbl_dst_status.config(text="✔ Logdatei gefunden und bereit!", foreground="#06d6a0")
            else:
                self.lbl_dst_status.config(text="⚠ client_log.txt nicht gefunden", foreground="#ef476f")

            if sys.platform.startswith("win"):
                self.lbl_mumble_status.config(text="Mumble (Windows): Bereit für Shared Memory", foreground="#06d6a0")
            else:
                shm_target = Path.home() / ".local/share/Mumble/Mumble/Plugins/liblink.so"
                if shm_target.exists():
                    self.lbl_mumble_status.config(text="✔ Mumble Link-Plugin eingerichtet", foreground="#06d6a0")
                else:
                    self.lbl_mumble_status.config(text="⚠ Klicke auf 'Auto-Setup', um Mumble einzurichten", foreground="#ffd166")

        def _run_mumble_autofix(self):
            res = auto_configure_mumble()
            self._check_status()
            messagebox.showinfo("Mumble Auto-Setup", "Ergebnis:\n\n" + "\n".join(f"• {r}" for r in res))

        def _toggle_bridge(self):
            if not self.bridge_running:
                log_path = self.dst_path_var.get()
                if not Path(log_path).exists():
                    messagebox.showerror("Fehler", f"Logdatei existiert nicht:\n{log_path}")
                    return

                self.bridge_running = True
                self.btn_toggle.config(text="⏹ BRIDGE STOPPEN", bg="#ef476f")
                self.lbl_live_status.config(text="[AKTIV] Mumble-Link initialisiert. Warte auf Positionsdaten...", foreground="#06d6a0")
                
                self.bridge_thread = threading.Thread(target=self._run_bridge_worker, args=(log_path,), daemon=True)
                self.bridge_thread.start()
            else:
                self.bridge_running = False
                self.btn_toggle.config(text="▶ VOICE BRIDGE STARTEN", bg="#06d6a0")
                self.lbl_live_status.config(text="Bridge angehalten.", foreground="#ffffff")
                if self.link_manager:
                    self.link_manager.close()
                    self.link_manager = None

        def _run_bridge_worker(self, log_path):
            try:
                self.link_manager = MumbleLinkManager()
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Fehler", f"Konnte Mumble-Link nicht starten:\n{e}"))
                self.bridge_running = False
                self.after(0, lambda: self.btn_toggle.config(text="▶ VOICE BRIDGE STARTEN", bg="#06d6a0"))
                return

            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, 2)
                last_size = os.path.getsize(log_path)

                while self.bridge_running:
                    try:
                        cur_size = os.path.getsize(log_path)
                        if cur_size < last_size:
                            f.seek(0, 0)
                        last_size = cur_size
                    except Exception:
                        pass

                    line = f.readline()
                    if not line:
                        time.sleep(0.02)
                        continue

                    if "[MUMBLE_LINK]" in line:
                        try:
                            parts = line.strip().split()
                            pos_str, rot_str = "", "0"
                            for p in parts:
                                if p.startswith("POS:"):
                                    pos_str = p[4:]
                                elif p.startswith("ROT:"):
                                    rot_str = p[4:]

                            if pos_str:
                                coords = [float(c) for c in pos_str.split(",")]
                                rot = float(rot_str)
                                self.link_manager.update(coords[0], coords[1], coords[2], rot)

                                status_text = f"[VERBUNDEN] Position: X={coords[0]:.1f}, Z={coords[2]:.1f} | Blickrichtung={rot:.0f}°"
                                self.after(0, lambda st=status_text: self.lbl_live_status.config(text=st, foreground="#06d6a0"))
                        except Exception:
                            pass

# --- 6. Startpunkt ---
def main():
    if HAS_TKINTER:
        app = GuiApp()
        app.mainloop()
    else:
        run_cli()

if __name__ == "__main__":
    main()
