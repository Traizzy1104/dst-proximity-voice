#!/usr/bin/env python3
"""
DST -> Mumble Link Positional Audio Bridge
Autor: Robin & Antigravity
Kompatibel mit: Linux (Ubuntu/Debian) & Windows 10/11
"""

import os
import sys
import time
import math
import ctypes
import threading
from pathlib import Path

# --- 1. MumbleLink C-Struktur Definition ---
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

class MumbleLink:
    def __init__(self):
        self.tick = 0
        self.is_windows = sys.platform.startswith("win")
        self.mem = None
        self.lock = threading.Lock()
        self.running = True

        self._init_shared_memory()
        self._init_static_fields()

        # Startet einen Hintergrund-Ticker (10 Hz), damit Mumble die Verbindung
        # auch dann aufrechterhält, wenn der Spieler minutenlang regungslos steht.
        self.ticker_thread = threading.Thread(target=self._keepalive_ticker, daemon=True)
        self.ticker_thread.start()

    def _init_shared_memory(self):
        if self.is_windows:
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            PAGE_READWRITE = 0x04
            FILE_MAP_ALL_ACCESS = 0xF001F
            
            size = ctypes.sizeof(LinkedMem)
            handle = kernel32.CreateFileMappingW(
                wintypes.HANDLE(-1), None, PAGE_READWRITE, 0, size, "MumbleLink"
            )
            if not handle:
                raise OSError(f"Konnte MumbleLink FileMapping auf Windows nicht erstellen. Error: {kernel32.GetLastError()}")
            ptr = kernel32.MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, size)
            if not ptr:
                raise OSError(f"MapViewOfFile fehlgeschlagen. Error: {kernel32.GetLastError()}")
            self.mem = LinkedMem.from_address(ptr)
        else:
            # Linux: POSIX Shared Memory
            import mmap
            uid = os.getuid()
            size = ctypes.sizeof(LinkedMem)
            
            # Hauptpfad für Linux Mumble: /dev/shm/MumbleLink.<uid>
            self.shm_path = f"/dev/shm/MumbleLink.{uid}"
            self.shm_file = open(self.shm_path, "w+b")
            self.shm_file.truncate(size)
            self.mm = mmap.mmap(self.shm_file.fileno(), size)
            self.mem = LinkedMem.from_buffer(self.mm)

            # Fallback-Symlink auf /dev/shm/MumbleLink (manche ältere Mumble-Versionen)
            try:
                fallback_path = "/dev/shm/MumbleLink"
                if not os.path.exists(fallback_path):
                    os.symlink(self.shm_path, fallback_path)
            except Exception:
                pass

    def _init_static_fields(self):
        with self.lock:
            self.mem.uiVersion = 2
            self.mem.name = "Don't Starve Together"
            self.mem.description = "DST Proximity Voice Bridge"
            
            # Fester Kontext: Alle Spieler in DST teilen sich diesen Kontext.
            # Nur Spieler mit gleichem Kontext hören sich in Mumble räumlich!
            ctx = b"DST_PROXIMITY_WORLD"
            self.mem.context_len = len(ctx)
            for i, b in enumerate(ctx):
                self.mem.context[i] = b

            # Oben-Vektor (Y zeigt nach oben)
            self.mem.fAvatarTop[0] = 0.0
            self.mem.fAvatarTop[1] = 1.0
            self.mem.fAvatarTop[2] = 0.0
            self.mem.fCameraTop[0] = 0.0
            self.mem.fCameraTop[1] = 1.0
            self.mem.fCameraTop[2] = 0.0

            # Standard-Blickrichtung (nach vorne)
            self.mem.fAvatarFront[0] = 0.0
            self.mem.fAvatarFront[1] = 0.0
            self.mem.fAvatarFront[2] = 1.0
            self.mem.fCameraFront[0] = 0.0
            self.mem.fCameraFront[1] = 0.0
            self.mem.fCameraFront[2] = 1.0

    def update_position(self, x, y, z, rotation_deg):
        with self.lock:
            self.tick += 1
            self.mem.uiTick = self.tick

            # Mumble-Koordinatensystem:
            # X = Rechts, Y = Oben, Z = Vorne (in Metern)
            self.mem.fAvatarPosition[0] = float(x)
            self.mem.fAvatarPosition[1] = float(y)
            self.mem.fAvatarPosition[2] = float(z)

            self.mem.fCameraPosition[0] = float(x)
            self.mem.fCameraPosition[1] = float(y)
            self.mem.fCameraPosition[2] = float(z)

            # Blickrichtung berechnen
            rad = math.radians(rotation_deg)
            front_x = -math.sin(rad)
            front_z = math.cos(rad)

            self.mem.fAvatarFront[0] = front_x
            self.mem.fAvatarFront[1] = 0.0
            self.mem.fAvatarFront[2] = front_z

            self.mem.fCameraFront[0] = front_x
            self.mem.fCameraFront[1] = 0.0
            self.mem.fCameraFront[2] = front_z

    def _keepalive_ticker(self):
        """Erhöht uiTick periodisch, damit Mumble die Verbindung aktiv hält."""
        while self.running:
            with self.lock:
                self.tick += 1
                self.mem.uiTick = self.tick
            time.sleep(0.1)

    def close(self):
        self.running = False
        if not self.is_windows and hasattr(self, "mm"):
            try:
                self.mm.close()
                self.shm_file.close()
                if os.path.exists(self.shm_path):
                    os.unlink(self.shm_path)
            except Exception:
                pass


# --- 2. Automatische Pfadsuche nach client_log.txt ---
def find_log_file():
    home = Path.home()
    
    candidates = [
        # Linux Nativ
        home / ".klei/DoNotStarveTogether/client_log.txt",
        # Windows Standard & OneDrive
        home / "Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / "OneDrive/Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / "OneDrive/Dokumente/Klei/DoNotStarveTogether/client_log.txt",
        # Linux via Steam Proton / Steam Deck
        home / ".steam/steam/steamapps/compatdata/322330/pfx/drive_c/users/steamuser/Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / ".local/share/Steam/steamapps/compatdata/322330/pfx/drive_c/users/steamuser/Documents/Klei/DoNotStarveTogether/client_log.txt",
    ]

    for p in candidates:
        if p.exists():
            return p

    # Falls client_log.txt in einem Unterordner (z.B. mit Steam-ID) liegt:
    klei_dir = home / ".klei/DoNotStarveTogether"
    if klei_dir.exists():
        found = list(klei_dir.glob("**/client_log.txt"))
        if found:
            return found[0]

    return None


# --- 3. Hauptprogramm ---
def main():
    print("==================================================")
    print("   Don't Starve Together - Proximity Voice Bridge")
    print("   Verbindung zu Mumble Link")
    print("==================================================")

    try:
        link = MumbleLink()
        print("[OK] Mumble-Link Shared Memory erfolgreich initialisiert.")
    except Exception as e:
        print(f"[FEHLER] Konnte Mumble-Link nicht starten: {e}")
        input("Drücke ENTER zum Beenden...")
        return

    print("\nSuche nach Don't Starve Together Logdatei...")
    log_path = None
    dots = 0
    while log_path is None:
        log_path = find_log_file()
        if not log_path:
            dots = (dots + 1) % 4
            print(f"\rWarte auf Spielstart (client_log.txt wird gesucht){'.' * dots}   ", end="", flush=True)
            time.sleep(1.5)

    print(f"\n[OK] Logdatei gefunden:\n    -> {log_path}")
    print("\nBridge ist aktiv! Sobald du einer Welt beitrittst, werden 3D-Daten übertragen.")
    print("(Dieses Fenster während des Spielens einfach im Hintergrund offen lassen)\n")

    last_pos_str = ""
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # An das aktuelle Ende der Datei springen
            f.seek(0, 2)
            last_size = os.path.getsize(log_path)

            while True:
                # Prüfe, ob DST neu gestartet wurde (Dateigröße schrumpft)
                try:
                    current_size = os.path.getsize(log_path)
                    if current_size < last_size:
                        print("\n[INFO] Spiel wurde neu gestartet. Setze Lesezeiger zurück...")
                        f.seek(0, 0)
                    last_size = current_size
                except Exception:
                    pass

                line = f.readline()
                if not line:
                    time.sleep(0.02)
                    continue

                if "[MUMBLE_LINK]" in line:
                    try:
                        # Format: [MUMBLE_LINK] POS:10.50,0.00,25.30 ROT:180.00 GHOST:false
                        parts = line.strip().split()
                        pos_str = ""
                        rot_str = "0"

                        for part in parts:
                            if part.startswith("POS:"):
                                pos_str = part[4:]
                            elif part.startswith("ROT:"):
                                rot_str = part[4:]

                        if pos_str:
                            coords = [float(c) for c in pos_str.split(",")]
                            rot = float(rot_str)
                            link.update_position(coords[0], coords[1], coords[2], rot)

                            status = f"\r[AKTIV] Position: X={coords[0]:.1f}, Z={coords[2]:.1f}, Blickrichtung={rot:.0f}°  "
                            if status != last_pos_str:
                                print(status, end="", flush=True)
                                last_pos_str = status
                    except Exception:
                        pass

    except KeyboardInterrupt:
        print("\n\nBeende Bridge...")
    finally:
        link.close()
        print("Auf Wiedersehen!")

if __name__ == "__main__":
    main()
