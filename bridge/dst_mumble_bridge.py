#!/usr/bin/env python3
"""
Don't Starve Together -> Mumble Link Positional Audio Bridge
Funktioniert nativ auf Linux (Ubuntu/Debian) und Windows.
Unterstützt Spielfigur-Position & Kamera-Drehung (Q/E).
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
            ptr = kernel32.MapViewOfFile(handle, FILE_MAP_ALL_ACCESS, 0, 0, size)
            self.mem = LinkedMem.from_address(ptr)
        else:
            import mmap
            uid = os.getuid()
            size = ctypes.sizeof(LinkedMem)
            
            self.shm_path = f"/dev/shm/MumbleLink.{uid}"
            self.shm_file = open(self.shm_path, "w+b")
            self.shm_file.truncate(size)
            self.mm = mmap.mmap(self.shm_file.fileno(), size)
            self.mem = LinkedMem.from_buffer(self.mm)

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
            
            ctx = b"DST_PROXIMITY_WORLD"
            self.mem.context_len = len(ctx)
            for i, b in enumerate(ctx):
                self.mem.context[i] = b

            self.mem.fAvatarTop[0], self.mem.fAvatarTop[1], self.mem.fAvatarTop[2] = 0.0, 1.0, 0.0
            self.mem.fCameraTop[0], self.mem.fCameraTop[1], self.mem.fCameraTop[2] = 0.0, 1.0, 0.0
            self.mem.fAvatarFront[0], self.mem.fAvatarFront[1], self.mem.fAvatarFront[2] = 0.0, 0.0, 1.0
            self.mem.fCameraFront[0], self.mem.fCameraFront[1], self.mem.fCameraFront[2] = 0.0, 0.0, 1.0

    def update_position(self, x, y, z, avatar_rot_deg, cam_heading_deg):
        with self.lock:
            self.tick += 1
            self.mem.uiTick = self.tick

            self.mem.fAvatarPosition[0] = float(x)
            self.mem.fAvatarPosition[1] = float(y)
            self.mem.fAvatarPosition[2] = float(z)

            self.mem.fCameraPosition[0] = float(x)
            self.mem.fCameraPosition[1] = float(y)
            self.mem.fCameraPosition[2] = float(z)

            # Avatar Ausrichtung
            ar_rad = math.radians(avatar_rot_deg)
            afx, afz = -math.sin(ar_rad), math.cos(ar_rad)
            self.mem.fAvatarFront[0], self.mem.fAvatarFront[1], self.mem.fAvatarFront[2] = afx, 0.0, afz

            # Kamera Ausrichtung (reagiert auf Q / E)
            cam_rad = math.radians(cam_heading_deg)
            cfx, cfz = -math.cos(cam_rad), -math.sin(cam_rad)
            self.mem.fCameraFront[0], self.mem.fCameraFront[1], self.mem.fCameraFront[2] = cfx, 0.0, cfz

    def _keepalive_ticker(self):
        while self.running:
            with self.lock:
                self.tick += 1
                self.mem.uiTick = self.tick
            time.sleep(0.1)

    def close(self):
        self.running = False


# --- 2. Automatische Pfadsuche nach client_log.txt ---
def find_log_file():
    home = Path.home()
    candidates = [
        home / ".klei/DoNotStarveTogether/client_log.txt",
        home / "Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / "OneDrive/Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / "OneDrive/Dokumente/Klei/DoNotStarveTogether/client_log.txt",
        home / ".steam/steam/steamapps/compatdata/322330/pfx/drive_c/users/steamuser/Documents/Klei/DoNotStarveTogether/client_log.txt",
        home / ".local/share/Steam/steamapps/compatdata/322330/pfx/drive_c/users/steamuser/Documents/Klei/DoNotStarveTogether/client_log.txt",
    ]

    for p in candidates:
        if p.exists():
            return p

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
    print("   Mit Kamera-Rotation (Q/E) & Mumble Link")
    print("==================================================")

    try:
        link = MumbleLink()
        print("[OK] Mumble-Link Shared Memory initialisiert.")
    except Exception as e:
        print(f"[FEHLER] Mumble-Link Fehler: {e}")
        return

    log_path = None
    while log_path is None:
        log_path = find_log_file()
        if not log_path:
            time.sleep(1.5)

    print(f"[OK] Logdatei gefunden: {log_path}\n")

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
                        pos_str, rot_str, cam_str = "", "0", "0"

                        for part in parts:
                            if part.startswith("POS:"):
                                pos_str = part[4:]
                            elif part.startswith("ROT:"):
                                rot_str = part[4:]
                            elif part.startswith("CAM:"):
                                cam_str = part[4:]

                        if pos_str:
                            coords = [float(c) for c in pos_str.split(",")]
                            rot = float(rot_str)
                            cam = float(cam_str)
                            link.update_position(coords[0], coords[1], coords[2], rot, cam)

                            status = f"\r[AKTIV] Pos: X={coords[0]:.1f}, Z={coords[2]:.1f} | Kamera={cam:.0f}° | Wilson={rot:.0f}°  "
                            if status != last_status:
                                print(status, end="", flush=True)
                                last_status = status
                    except Exception:
                        pass
    except KeyboardInterrupt:
        print("\nBeende Bridge...")
    finally:
        link.close()

if __name__ == "__main__":
    main()
