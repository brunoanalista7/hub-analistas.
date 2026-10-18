"""Integração com o Windows, tudo sem administrador."""

import os
import subprocess
import sys
from pathlib import Path

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def keep_awake() -> None:
    # o PC reserva mostra a TV: nem ele nem a tela podem dormir
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)


def startup_file() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Hub.cmd"


def set_start_with_windows(enabled: bool, project_dir: Path) -> None:
    f = startup_file()
    if enabled:
        f.parent.mkdir(parents=True, exist_ok=True)
        # o cmd.exe lê .cmd na página de código OEM; em UTF-8 "Área" viraria lixo
        encoding = "oem" if sys.platform == "win32" else "utf-8"
        f.write_text(f'start "" /min "{Path(project_dir) / "iniciar.bat"}"\n', encoding=encoding)
    else:
        f.unlink(missing_ok=True)


def open_tv(url: str) -> None:
    """Abre a TV no Edge em tela cheia (modo quiosque), sem barras nem abas."""
    if sys.platform != "win32":
        import webbrowser

        webbrowser.open(url)
        return
    subprocess.Popen(
        ["cmd", "/c", "start", "", "msedge", "--kiosk", url, "--edge-kiosk-type=fullscreen", "--no-first-run"],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
