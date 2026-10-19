def is_han(c: str) -> bool:
    o = ord(c)
    return (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF) or (0xF900 <= o <= 0xFAFF) or (0x20000 <= o <= 0x2FA1F)


def is_kana(c: str) -> bool:
    o = ord(c)
    return (0x3040 <= o <= 0x30FF) or (0x31F0 <= o <= 0x31FF) or (0xFF66 <= o <= 0xFF9D)


def has_kana(s: str) -> bool:
    return any(is_kana(c) for c in s)


def han_count(s: str) -> int:
    return sum(1 for c in s if is_han(c))


def is_cjk(c: str) -> bool:
    o = ord(c)
    return is_han(c) or is_kana(c) or (0x3000 <= o <= 0x303F) or (0xFF00 <= o <= 0xFFEF)


def detect_lang(text: str, pref: str = "AUTO") -> str:
    if pref in ("ZH", "JA"):
        return pref
    kana = sum(1 for c in text if is_kana(c))
    if kana >= 2 and kana * 10 >= han_count(text):
        return "JA"
    if kana >= 1 and han_count(text) <= 2:
        return "JA"
    return "ZH"


def join_lines(lines):
    out = ""
    for s in lines:
        s = remove_cjk_spaces(s.strip())
        if not s:
            continue
        if out and not (is_cjk(out[-1]) or is_cjk(s[0])):
            out += " "
        out += s
    return out


def remove_cjk_spaces(s: str) -> str:
    r = []
    for i, c in enumerate(s):
        if c == " " and 0 < i < len(s) - 1 and is_cjk(s[i - 1]) and is_cjk(s[i + 1]):
            continue
        r.append(c)
    return "".join(r)
