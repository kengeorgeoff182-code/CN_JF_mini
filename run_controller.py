"""Standalone launcher for the D1 OS-Ken controller application."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from os_ken.base import app_manager


# Make both `python -m sdn.run_controller` and
# `python sdn/run_controller.py` work from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# OS-Ken does not automatically enable INFO-level application logging when
# AppManager is launched this way. Configure it so D1 evidence such as
# switch connections and chat-flow classification is visible in the terminal.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


if __name__ == "__main__":
    logging.getLogger(__name__).info("Starting D1 Chat SDN Controller...")
    app_manager.AppManager.run_apps(["sdn.controller"])
