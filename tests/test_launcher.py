"""Launcher boundaries without touching a development process or data directory."""
import importlib.util
from pathlib import Path
import socket

import pytest

spec = importlib.util.spec_from_file_location("dev", Path(__file__).parents[1] / "scripts/dev.py")
dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dev)


def test_occupied_port():
    with socket.socket() as owner:
        owner.bind(("127.0.0.1", 0))
        with pytest.raises(RuntimeError, match="occupied"):
            dev.check_ports({"STORYROOM_API_PORT": str(owner.getsockname()[1])})
