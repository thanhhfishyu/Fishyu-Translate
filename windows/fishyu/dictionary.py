import gzip
import threading
from dataclasses import dataclass

from .paths import resource
from .textutil import is_han


@dataclass
class Entry:
    trad: str
    simp: str
    pinyin: str
    defs: str


class _Dict:
    def __init__(self):
        self.words = {}
        self.hanviet = {}
        self.max_len = 1
        self._loaded = threading.Event()
        self._loading = False
        self._lock = threading.Lock()
        self.error = None

    def preload(self):
        with self._lock:
            if self._loading:
                return
            self._loading = True
        threading.Thread(target=self._load, name="dict-load", daemon=True).start()

    def ready(self, timeout=30.0) -> bool:
        self.preload()
        return self._loaded.wait(timeout)

    def _load(self):
        try:
            words = {}
            ml = 1
            with gzip.open(resource("cedict.dat"), "rt", encoding="utf-8") as f:
                for line in f:
                    p = line.rstrip("\n").split("\t")
                    if len(p) < 4:
                        continue
                    e = Entry(p[0], p[1], p[2], p[3])
                    words.setdefault(e.simp, []).append(e)
                    if e.trad != e.simp:
                        words.setdefault(e.trad, []).append(e)
                    ml = max(ml, len(e.simp))
            hv = {}
            with gzip.open(resource("hanviet.dat"), "rt", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if len(line) > 2 and line[1] == "\t":
                        hv[line[0]] = line[2:]
            self.words, self.hanviet, self.max_len = words, hv, min(ml, 12)
        except Exception as e:
            self.error = e
            from . import crashlog
            crashlog.save(e, "dictionary")
        finally:
            self._loaded.set()

    def lookup(self, word: str):
        return self.words.get(word.strip(), [])

    def han_viet(self, text: str) -> str:
        out = []
        for c in text:
            if is_han(c):
                v = self.hanviet.get(c)
                out.append(v.split(",")[0].strip() if v else c)
        return " ".join(out)

    def segment(self, text: str):
        out = []
        i = 0
        n = len(text)
        while i < n:
            if not is_han(text[i]):
                i += 1
                continue
            found = 1
            for ln in range(min(self.max_len, n - i), 1, -1):
                if text[i:i + ln] in self.words:
                    found = ln
                    break
            out.append(text[i:i + found])
            i += found
        return out


DICT = _Dict()
