import os, tempfile
from pathlib import Path, PurePosixPath

from .err import Bad

CAP = 5_000_000


class Disk:
    def __init__(s, root): s.root = Path(root).resolve()

    def norm(s, p):
        if not isinstance(p, str) or not p.strip(): raise Bad('empty path')
        full = Path(p) if Path(p).is_absolute() else s.root/p
        try: rel = PurePosixPath(*full.resolve().relative_to(s.root).parts).as_posix()
        except ValueError: raise Bad(f'{p} is outside the workspace {s.root}') from None
        if rel in ('', '.'): raise Bad(f'{p} is the workspace root')
        if rel.split('/')[0].lower() == '.hive': raise Bad('.hive/ belongs to Hive')
        return rel

    def read(s, rel):
        f = s.root/rel
        if not f.exists(): return None
        if f.is_dir(): raise Bad(f'{rel} is a directory')
        if f.stat().st_size > CAP: raise Bad(f'{rel} is over {CAP} bytes; Hive coordinates text files')
        try:
            with open(f, encoding='utf-8', newline='') as h: return h.read()
        except UnicodeDecodeError: raise Bad(f'{rel} is not UTF-8 text') from None

    def write(s, rel, text):
        f = s.root/rel
        f.parent.mkdir(parents=True, exist_ok=True)
        mode = f.stat().st_mode & 0o7777 if f.exists() else None
        fd, tmp = tempfile.mkstemp(dir=f.parent, prefix=f'.{f.name}.', suffix='.hive')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as h: h.write(text)
            if mode is not None: os.chmod(tmp, mode)
            os.replace(tmp, f)
        except BaseException:
            if os.path.exists(tmp): os.unlink(tmp)
            raise
