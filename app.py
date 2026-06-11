#!/usr/bin/env python3
"""
SIG Platform — Local Docker Stack Manager

Standalone GUI for running and monitoring the local Docker stack.
Requires Python 3.8+ and Docker Desktop. No additional pip packages needed.

Usage:
    python app.py
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, List

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

# ── Theming ──────────────────────────────────────────────────────────────────
C = {
    "bg":         "#1e1e2e",
    "panel":      "#313244",
    "surface":    "#181825",
    "accent":     "#89b4fa",
    "green":      "#a6e3a1",
    "yellow":     "#f9e2af",
    "red":        "#f38ba8",
    "text":       "#cdd6f4",
    "dim":        "#6c7086",
    "btn":        "#45475a",
    "btn_hover":  "#585b70",
}

SERVICES = ["redis", "web", "nginx", "poller", "sigtools-db"]
REPO_ROOT = Path(__file__).resolve().parent

# Configuración de nginx embebida — se escribe automáticamente si falta
_NGINX_CONF = """\
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name _;

    client_max_body_size 50M;

    location /media/ {
        alias /app/media/;
        access_log off;
        expires 7d;
        add_header Cache-Control "public";
    }

    location /api/ {
        proxy_pass         http://django;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   Connection        "";
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 86400;
    }

    location /web-auth/ {
        proxy_pass         http://django;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
"""


def _ensure_nginx_conf(directory: Path) -> None:
    """Escribe nginx.conf junto al compose file si no existe (modo standalone)."""
    conf = directory / "nginx.conf"
    if not conf.exists():
        conf.write_text(_NGINX_CONF, encoding="utf-8")

# ── Docker Compose helpers ────────────────────────────────────────────────────
def _popen_kwargs() -> dict:
    """Suppress console popup on Windows."""
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


class DockerManager:
    def __init__(self, compose_files: List[Path]):
        self.compose_files = compose_files
        self.work_dir = compose_files[0].parent

    def _base_cmd(self) -> List[str]:
        cmd = ["docker", "compose"]
        for f in self.compose_files:
            cmd += ["-f", str(f)]
        return cmd

    def _stream(self, *args) -> subprocess.Popen:
        cmd = self._base_cmd() + list(args)
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=self.work_dir, **_popen_kwargs()
        )

    def _run(self, *args) -> subprocess.CompletedProcess:
        cmd = self._base_cmd() + list(args)
        return subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=self.work_dir, **_popen_kwargs()
        )

    def build(self, no_cache=False):
        args = ["build"]
        if no_cache:
            args.append("--no-cache")
        return self._stream(*args)

    def up(self):
        return self._stream("up", "-d")

    def down(self):
        return self._stream("down")

    def restart(self, service: Optional[str] = None):
        return self._stream("restart", *([service] if service else []))

    def logs(self, service: Optional[str] = None, tail: int = 200):
        args = ["logs", f"--tail={tail}", "-f"]
        if service:
            args.append(service)
        return self._stream(*args)

    def status(self) -> List[dict]:
        result = self._run("ps", "--format", "json")
        if result.returncode != 0 or not result.stdout.strip():
            return []
        services = []
        for line in result.stdout.strip().splitlines():
            try:
                services.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return services


# ── App ──────────────────────────────────────────────────────────────────────
class PlatformApp:
    def __init__(self, root: tk.Tk, docker: DockerManager, compose_files: List[Path]):
        self.root = root
        self.docker = docker
        self.compose_files = compose_files
        self._log_q: queue.Queue = queue.Queue()
        self._proc: Optional[subprocess.Popen] = None
        self._status_labels: dict = {}
        self._buttons: dict = {}

        root.title("SIG Platform — Local Docker Manager")
        root.configure(bg=C["bg"])
        root.geometry("960x680")
        root.minsize(800, 560)

        self._build_ui()
        self._poll_status()
        self._drain_logs()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_status_panel()
        self._build_buttons()
        self._build_log_area()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C["bg"], pady=10, padx=14)
        hdr.pack(fill="x")

        tk.Label(hdr, text="SIG Platform", font=("Helvetica", 17, "bold"),
                 bg=C["bg"], fg=C["accent"]).pack(side="left")

        compose_names = " + ".join(f.name for f in self.compose_files)
        tk.Label(hdr, text=f"  {compose_names}", font=("Courier", 9),
                 bg=C["bg"], fg=C["dim"]).pack(side="left", pady=2)

    def _build_status_panel(self):
        frame = tk.LabelFrame(self.root, text="Service Status",
                              bg=C["bg"], fg=C["accent"],
                              font=("Helvetica", 10, "bold"),
                              padx=10, pady=8, relief="groove", bd=1)
        frame.pack(fill="x", padx=14, pady=(0, 6))

        for i, svc in enumerate(SERVICES):
            col = tk.Frame(frame, bg=C["bg"])
            col.grid(row=0, column=i, padx=14, sticky="w")
            tk.Label(col, text=svc.upper(), font=("Helvetica", 8, "bold"),
                     bg=C["bg"], fg=C["text"]).pack(anchor="w")
            lbl = tk.Label(col, text="○ offline", font=("Courier", 9),
                           bg=C["bg"], fg=C["dim"])
            lbl.pack(anchor="w")
            self._status_labels[svc] = lbl

    def _build_buttons(self):
        bar = tk.Frame(self.root, bg=C["panel"], pady=9, padx=12)
        bar.pack(fill="x", padx=14, pady=(0, 6))

        specs = [
            ("Build",         self._do_build,          C["accent"]),
            ("Up",            self._do_up,              C["green"]),
            ("Restart",       self._do_restart,         C["yellow"]),
            ("Nginx Restart", self._do_nginx_restart,   C["yellow"]),
            ("Health Status", self._do_health,          C["accent"]),
            ("Seed DB",       self._do_seed_db,         C["yellow"]),
            ("Logs",          self._do_logs,            C["dim"]),
            ("Down",          self._do_down,            C["red"]),
        ]

        for label, cmd, fg in specs:
            btn = tk.Button(bar, text=label, command=cmd,
                            bg=C["btn"], fg=fg,
                            activebackground=C["btn_hover"], activeforeground=fg,
                            relief="flat", padx=11, pady=5,
                            font=("Helvetica", 10, "bold"), cursor="hand2",
                            bd=0)
            btn.pack(side="left", padx=3)
            self._buttons[label] = btn

        self._stop_btn = tk.Button(bar, text="⏹ Stop", command=self._do_stop,
                                   bg=C["red"], fg="white",
                                   activebackground="#eb5b5b", activeforeground="white",
                                   relief="flat", padx=11, pady=5,
                                   font=("Helvetica", 10, "bold"), cursor="hand2", bd=0)

    def _build_log_area(self):
        frame = tk.LabelFrame(self.root, text="Output",
                              bg=C["bg"], fg=C["accent"],
                              font=("Helvetica", 10, "bold"),
                              padx=6, pady=6, relief="groove", bd=1)
        frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        self._log = scrolledtext.ScrolledText(
            frame, bg=C["surface"], fg=C["text"],
            font=("Courier", 9), state="disabled",
            wrap="word", relief="flat",
            insertbackground=C["accent"]
        )
        self._log.pack(fill="both", expand=True)

        self._log.tag_configure("info",    foreground=C["accent"])
        self._log.tag_configure("success", foreground=C["green"])
        self._log.tag_configure("warn",    foreground=C["yellow"])
        self._log.tag_configure("error",   foreground=C["red"])
        self._log.tag_configure("dim",     foreground=C["dim"])

        self._log_line("SIG Platform Docker Manager ready.", "info")
        files_str = " + ".join(str(f) for f in self.compose_files)
        self._log_line(f"Compose: {files_str}", "dim")

    # ── Logging ───────────────────────────────────────────────────────────────
    def _log_line(self, text: str, tag: str = ""):
        self._log_q.put((text, tag))

    def _drain_logs(self):
        try:
            while True:
                text, tag = self._log_q.get_nowait()
                self._log.configure(state="normal")
                self._log.insert("end", text + "\n", tag or None)
                self._log.configure(state="disabled")
                self._log.see("end")
        except queue.Empty:
            pass
        self.root.after(40, self._drain_logs)

    # ── Async execution ───────────────────────────────────────────────────────
    def _run_async(self, fn):
        self._set_btns(False)
        self._stop_btn.pack(side="left", padx=3)

        def wrapper():
            try:
                fn()
            finally:
                self.root.after(0, self._set_btns, True)
                self.root.after(0, self._stop_btn.pack_forget)
                self._proc = None

        threading.Thread(target=wrapper, daemon=True).start()

    def _set_btns(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for b in self._buttons.values():
            b.configure(state=state)

    def _stream(self, proc: subprocess.Popen, label: str):
        self._proc = proc
        self._log_line(f"▶ {label}", "info")
        for line in proc.stdout:
            line = line.rstrip()
            low = line.lower()
            if any(w in low for w in ("error", "failed", "fatal", "exception", "traceback")):
                tag = "error"
            elif any(w in low for w in ("warning", "warn")):
                tag = "warn"
            elif any(w in low for w in ("done", "started", "healthy", "running", "success", "created", "built")):
                tag = "success"
            else:
                tag = ""
            self._log_line(line, tag)
        proc.wait()
        icon = "✓" if proc.returncode == 0 else "✗"
        tag = "success" if proc.returncode == 0 else "error"
        self._log_line(f"{icon} {label} exited ({proc.returncode})", tag)
        return proc.returncode

    # ── Button handlers ───────────────────────────────────────────────────────
    def _do_build(self):
        self._run_async(lambda: self._stream(self.docker.build(), "docker compose build"))

    def _do_up(self):
        self._run_async(lambda: self._stream(self.docker.up(), "docker compose up -d"))

    def _do_down(self):
        if not messagebox.askyesno("Confirm Down",
                                   "Stop and remove all containers?\n"
                                   "Volumes (database data) are preserved."):
            return
        self._run_async(lambda: self._stream(self.docker.down(), "docker compose down"))

    def _do_restart(self):
        self._run_async(lambda: self._stream(self.docker.restart(), "docker compose restart"))

    def _do_nginx_restart(self):
        self._run_async(lambda: self._stream(self.docker.restart("nginx"), "docker compose restart nginx"))

    def _do_logs(self):
        self._run_async(lambda: self._stream(self.docker.logs(), "docker compose logs -f (press ⏹ Stop to exit)"))

    def _do_health(self):
        def run():
            services = self.docker.status()
            self._log_line("─── Health Status ──────────────────────────────", "info")
            if not services:
                self._log_line("  No services running (or docker compose ps failed).", "warn")
            for svc in services:
                name  = svc.get("Service") or svc.get("Name") or "?"
                state  = svc.get("State", "?")
                health = svc.get("Health", "")
                ports  = svc.get("Publishers") or ""
                tag = "success" if state == "running" else "error"
                self._log_line(
                    f"  {name:<18} {state:<12} {('health: ' + health) if health else ''} {ports}",
                    tag
                )
            self._log_line("────────────────────────────────────────────────", "dim")
        threading.Thread(target=run, daemon=True).start()

    def _do_stop(self):
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
            self._log_line("Stopped by user.", "warn")

    # ── Seed DB ───────────────────────────────────────────────────────────────
    def _load_env(self) -> dict:
        """Parse .env files into a dict. docker/.env overrides root .env for Docker-specific vars."""
        env = {}
        for env_file in [REPO_ROOT / ".env", REPO_ROOT / "docker" / ".env"]:
            if env_file.exists():
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        env[key.strip()] = val.strip()
        return env

    def _do_seed_db(self):
        sql_path_str = filedialog.askopenfilename(
            title="Seleccionar snapshot SQL para inyectar en sigtools-db",
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")],
            initialdir=str(Path.home()),
        )
        if not sql_path_str:
            return  # usuario canceló

        sql_path = Path(sql_path_str)
        size_kb  = sql_path.stat().st_size // 1024

        if not messagebox.askyesno(
            "Inyectar SQL en sigtools-db",
            f"Archivo:  {sql_path.name}  ({size_kb:,} KB)\n\n"
            "Se inyectará en el contenedor local sigtools-db.\n"
            "Los datos actuales del contenedor serán reemplazados.\n\n"
            "¿Continuar?"
        ):
            return

        env = self._load_env()
        local_root_pass = env.get("LOCAL_SIGTOOLS_ROOT_PASSWORD", "localroot")

        def run():
            self._log_line(f"Inyectando {sql_path.name} ({size_kb:,} KB) en sigtools-db ...", "info")

            inject_cmd = self.docker._base_cmd() + [
                "exec", "-T",
                "-e", f"MYSQL_PWD={local_root_pass}",
                "sigtools-db",
                "mysql", "-uroot",
            ]

            # MySQL 8.0 no permite DEFAULT en columnas TEXT/BLOB/JSON/GEOMETRY (error 1101).
            # El dump viene de un servidor 5.x/8.0 permisivo — filtramos esas cláusulas en stream.
            _text_default = re.compile(
                r"(\b(?:tiny|medium|long)?(?:text|blob)\b|\bjson\b|\bgeometry\b)"
                r"([^,\n]*?)"
                r"\s+DEFAULT\s+(?:'[^']*'|\"[^\"]*\")",
                re.IGNORECASE,
            )

            proc = subprocess.Popen(
                inject_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                encoding="utf-8", errors="replace",
                **_popen_kwargs()
            )
            self._proc = proc

            def _feed():
                try:
                    with open(sql_path, "r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            proc.stdin.write(_text_default.sub(r"\1\2", line))
                except Exception as exc:
                    self._log_line(f"Feed error: {exc}", "error")
                finally:
                    proc.stdin.close()

            feed_thread = threading.Thread(target=_feed, daemon=True)
            feed_thread.start()

            for line in proc.stdout:
                line = line.rstrip()
                tag = "error" if "error" in line.lower() else "dim"
                self._log_line(line, tag)

            proc.wait()
            feed_thread.join()

            if proc.returncode == 0:
                self._log_line(f"✓ sigtools-db poblada desde {sql_path.name}", "success")
            else:
                self._log_line(f"✗ Inyección fallida (exit {proc.returncode})", "error")
                self._log_line("  Verifica que sigtools-db esté corriendo (botón Up).", "warn")

        self._run_async(run)

    # ── Status polling ────────────────────────────────────────────────────────
    def _poll_status(self):
        def fetch():
            services = self.docker.status()
            svc_map = {}
            for s in services:
                name   = s.get("Service") or s.get("Name") or ""
                state  = s.get("State", "unknown")
                health = s.get("Health", "")
                svc_map[name] = (state, health)
            self.root.after(0, self._apply_status, svc_map)

        threading.Thread(target=fetch, daemon=True).start()
        self.root.after(6000, self._poll_status)

    def _apply_status(self, svc_map: dict):
        for svc, lbl in self._status_labels.items():
            state, health = svc_map.get(svc, ("offline", ""))
            if state == "running":
                if health == "healthy":
                    text, color = "● healthy",   C["green"]
                elif health == "starting":
                    text, color = "◐ starting",  C["yellow"]
                elif health == "unhealthy":
                    text, color = "● unhealthy", C["red"]
                else:
                    text, color = "● running",   C["accent"]
            elif state in ("exited", "dead"):
                text, color = f"✗ {state}",    C["red"]
            elif state == "offline":
                text, color = "○ offline",     C["dim"]
            else:
                text, color = f"◌ {state}",   C["yellow"]
            lbl.configure(text=text, fg=color)


# ── Bootstrap ─────────────────────────────────────────────────────────────────
def find_compose_files(start: Path) -> Optional[List[Path]]:
    """
    Resuelve el/los compose file(s) a usar, con dos modos:

    Modo standalone (distribuible):
      Si existe docker-compose.local.yaml (o .yml) junto a app.py,
      se usa como archivo único. No se necesita el repositorio completo.
      También genera nginx.conf en ese directorio si no existe.

    Modo repo (desarrollo):
      Busca docker/docker-compose.yml como base y agrega el overlay
      docker-compose.local.yml o docker-compose.dev.yml si existe.
    """
    # ── Modo standalone ───────────────────────────────────────────────────────
    for name in ("docker-compose.local.yaml", "docker-compose.local.yml"):
        standalone = start / name
        if standalone.exists():
            _ensure_nginx_conf(start)
            return [standalone]

    # ── Modo repo ─────────────────────────────────────────────────────────────
    docker_dir = start / "docker"
    base = docker_dir / "docker-compose.yml"
    if not base.exists():
        base = start / "docker-compose.yml"
    if not base.exists():
        return None

    overlays = [
        docker_dir / "docker-compose.local.yml",
        docker_dir / "docker-compose.dev.yml",
    ]
    files = [base]
    for ov in overlays:
        if ov.exists():
            files.append(ov)
            break

    return files


def check_docker() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, text=True,
            timeout=10, **_popen_kwargs()
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main():
    root = tk.Tk()
    root.withdraw()

    if not check_docker():
        messagebox.showerror(
            "Docker Not Running",
            "Docker Desktop is not running or not installed.\n\n"
            "Start Docker Desktop and try again."
        )
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    compose_files = find_compose_files(script_dir)

    if not compose_files:
        messagebox.showerror(
            "Compose File Not Found",
            "No se encontró ningún archivo compose.\n\n"
            "Modo standalone: coloca docker-compose.local.yaml junto a app.py\n"
            "Modo repo: asegúrate de que exista docker/docker-compose.yml"
        )
        sys.exit(1)

    root.deiconify()
    docker = DockerManager(compose_files)
    PlatformApp(root, docker, compose_files)
    root.mainloop()


if __name__ == "__main__":
    main()
