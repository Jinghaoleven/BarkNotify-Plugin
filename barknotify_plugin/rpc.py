"""Read local Codex hook metadata without starting a model turn or trusting hooks."""

import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

from . import __version__


def inspect_hooks(binary, home):
    messages = queue.Queue()
    process = subprocess.Popen([binary, "app-server"], env={**os.environ, "CODEX_HOME": str(home)},
                               cwd=home, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)

    def read():
        for line in process.stdout:
            messages.put(line)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def request(identifier, method, params):
        process.stdin.write(json.dumps({"id": identifier, "method": method, "params": params}) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            message = json.loads(messages.get(timeout=max(0.01, deadline - time.monotonic())))
            if message.get("id") == identifier:
                if "error" in message:
                    raise ValueError("Codex does not support hook inspection through this app-server.")
                return message["result"]
        raise ValueError("Codex hook inspection timed out.")

    try:
        request(1, "initialize", {"clientInfo": {"name": "barknotify-plugin", "version": __version__},
                                  "capabilities": {"experimentalApi": True}})
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        result = request(2, "hooks/list", {"cwds": [str(home)]})
        entries = result.get("data", [])
        if not entries or entries[0].get("errors"):
            raise ValueError("Codex reported hook configuration errors. Review /hooks.")
        return entries[0].get("hooks", [])
    except (OSError, ValueError, queue.Empty, KeyError, TypeError):
        raise ValueError("Unable to inspect hooks through the local Codex app-server.") from None
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        reader.join(timeout=1)
        process.stdin.close()
        process.stdout.close()
