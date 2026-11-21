"""Single-instance Linux process lock, shared by server and CLI mutations."""
import fcntl
import json
import os
from pathlib import Path


class InstanceLock:
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+")
        try:
            fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stream.close()
            raise RuntimeError("Für dieses Programmverzeichnis läuft bereits eine Instanz.") from None
        self.stream.seek(0)
        self.stream.truncate()
        json.dump({"pid": os.getpid()}, self.stream)
        self.stream.flush()
        return self

    def __exit__(self, *args):
        if self.stream:
            fcntl.flock(self.stream, fcntl.LOCK_UN)
            self.stream.close()
