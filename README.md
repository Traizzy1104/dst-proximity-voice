# 🎙️ Don't Starve Together - Proximity Voice Chat (Mumble Bridge)

Realistischer 3D-Proximity-Voice-Chat für *Don't Starve Together* über Mumble Link.

* **Echtes 3D-Audio:** Je näher du an deinen Freunden stehst, desto lauter hörst du sie (inklusive Stereo-Richtung links/rechts).
* **Höhlen-Isolation:** Spieler an der Oberfläche und in den Höhlen hören sich nicht gegenseitig.
* **Kein Log-Spam:** Dank intelligenter Delta-Erkennung wird die Position nur bei Bewegung übertragen.
* **Plattformunabhängig:** Funktioniert nahtlos auf **Linux (Ubuntu/Debian)** und **Windows 10/11**.

---

## 🚀 Schnellanleitung für Spieler (Freunde)

### Schritt 1: Mod in DST aktivieren
1. Die Mod im Steam Workshop abonnieren (oder den Ordner `dst_mod` in deinen lokalen DST `mods`-Ordner als `dst_proximity_voice` kopieren).
2. Im Spiel unter **Mods** $\rightarrow$ **Client-Mods** die Mod `Proximity Voice (Mumble Bridge)` aktivieren.
   *(Da es eine Client-Mod ist, funktioniert sie auf JEDEM Server, auch wenn der Server die Mod nicht installiert hat).*

### Schritt 2: Mumble einrichten
1. **Mumble installieren:**
   * **Windows:** Download auf [mumble.info](https://www.mumble.info/)
   * **Linux:** `sudo apt install mumble`
2. **Positionsabhängiges Audio aktivieren:**
   * In Mumble auf **Einstellungen** $\rightarrow$ Haken bei *Erweitert* (unten links).
   * Unter **Plugins**: Haken bei **„Mit Spiel verbinden und Position übertragen“** (Link to Game and Transmit Position).
   * Unter **Audioausgabe** $\rightarrow$ **Positionsabhängiges Audio**:
     * Haken bei *Positionsabhängiges Audio aktivieren*.
     * Mindestentfernung: `2.0 m`
     * Höchstentfernung: `35.0 m`
     * **Mindestlautstärke: `0 %`** *(Wichtig! Damit weit entfernte Spieler komplett verstummen).*
3. Verbindet euch alle auf denselben Mumble-Server in denselben Raum.

### Schritt 3: Bridge starten
* **Linux:** Starte `run_linux.sh` (oder führe `python3 bridge/dst_mumble_bridge.py` aus).
* **Windows:** Starte `run_windows.bat` (oder die heruntergeladene `.exe`).

Sobald du der DST-Welt beitrittst, verbindet sich die Bridge automatisch und überträgt deine Position.

---

## 📦 GitHub Release / Standalone .exe Bauen

In diesem Repository ist ein automatischer GitHub-Action-Workflow enthalten:
* Sobald du einen Release erstellst oder den Workflow unter **Actions** manuell anstößt, baut GitHub automatisch:
  1. `DST-Voice-Bridge-Windows.exe` (Standalone-Datei für Windows-Freunde ohne Python)
  2. `DST-Voice-Bridge-Linux` (Eigenständige Binary für Linux)
