from .textutil import has_kana, is_han


def normalize(s: str) -> str:
    return "".join(c for c in s if c.isalnum())


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        ai = a[i - 1]
        for j in range(1, m + 1):
            cost = 0 if ai == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return 1.0 - prev[m] / max(n, m)


class Decision:
    EMPTY = "empty"
    NOT_CJK = "not_cjk"
    SAME = "same"
    WAIT = "wait"
    REUSE = "reuse"
    TRANSLATE = "translate"

    def __init__(self, kind, norm="", translation=""):
        self.kind = kind
        self.norm = norm
        self.translation = translation


class LiveGate:
    def __init__(self):
        self.pending = ""
        self.shown = ""
        self.done = {}

    def offer(self, text: str) -> Decision:
        norm = normalize(text)
        if len(norm) < 2:
            self.pending = ""
            return Decision(Decision.EMPTY)
        cjk = sum(1 for c in norm if is_han(c) or has_kana(c))
        if cjk < 2 or cjk * 10 < len(norm) * 3:
            self.pending = ""
            return Decision(Decision.NOT_CJK)
        if similarity(norm, self.shown) >= 0.8:
            self.pending = ""
            return Decision(Decision.SAME)
        if similarity(norm, self.pending) < 0.9:
            self.pending = norm
            return Decision(Decision.WAIT)
        self.pending = ""
        self.shown = norm
        for k, v in self.done.items():
            if similarity(k, norm) >= 0.85:
                return Decision(Decision.REUSE, norm, v)
        return Decision(Decision.TRANSLATE, norm)

    @property
    def has_pending(self):
        return bool(self.pending)

    @property
    def has_shown(self):
        return bool(self.shown)

    def remember(self, norm, translation):
        self.done[norm] = translation
        while len(self.done) > 40:
            self.done.pop(next(iter(self.done)))

    def failed(self):
        self.shown = ""

    def reset(self, clear_done=False):
        self.pending = ""
        self.shown = ""
        if clear_done:
            self.done.clear()
