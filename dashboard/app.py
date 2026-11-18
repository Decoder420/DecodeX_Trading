"""DecodeX Trading — Streamlit Dashboard Entrypoint (Redirect to Root app.py)."""

from pathlib import Path
import runpy

ROOT_APP = Path(__file__).resolve().parent.parent / "app.py"
runpy.run_path(str(ROOT_APP), run_name="__main__")
