"""Single-instance Linux process lock, shared by server and CLI mutations."""
import fcntl
import json
import os
from pathlib import Path


def process_start_ticks(pid):
    return int((Path('/proc')/str(pid)/'stat').read_text().rsplit(') ',1)[1].split()[19])


class InstanceLock:
    def __init__(self, path, metadata=None):
        self.path = Path(path)
        self.stream = None
        self.metadata=metadata or {}

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = os.fdopen(os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600),"r+")
        try:
            try:fcntl.flock(self.stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError("Für dieses Datenverzeichnis läuft bereits eine Instanz.") from None
            os.fchmod(self.stream.fileno(),0o600)
            record={**self.metadata,"schema_version":2,"pid":os.getpid(),"start_ticks":process_start_ticks(os.getpid())}
            self.stream.seek(0);self.stream.truncate();json.dump(record,self.stream);self.stream.flush()
            return self
        except BaseException:
            self.stream.close();self.stream=None;raise

    def __exit__(self, *args):
        if self.stream:
            fcntl.flock(self.stream, fcntl.LOCK_UN)
            self.stream.close()
