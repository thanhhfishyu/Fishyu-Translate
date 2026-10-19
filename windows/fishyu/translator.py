import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass

import requests

from . import config
from .offline import OFFLINE


@dataclass
class TranslateResult:
    text: str
    engine: str
    note: str = None


class TranslateError(Exception):
    pass


FREE_HOST = "https://api-free.deepl.com"
PRO_HOST = "https://api.deepl.com"

_session = requests.Session()
_cache = OrderedDict()
_cache_lock = threading.Lock()
_known_host = None


def _hosts(key):
    if _known_host and _known_host[0] == key:
        return [_known_host[1]]
    return [FREE_HOST, PRO_HOST] if key.endswith(":fx") else [PRO_HOST, FREE_HOST]


def _send(key, path, method="GET", json_body=None):
    global _known_host
    last = (0, "")
    for h in _hosts(key):
        r = _session.request(method, h + path, json=json_body, timeout=(10, 30),
                             headers={"Authorization": f"DeepL-Auth-Key {key}"})
        last = (r.status_code, r.text)
        if r.status_code != 403:
            _known_host = (key, h)
            return last
    return last


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _unesc(s):
    return s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")


def apply_glossary_xml(text, pairs):
    s = _esc(text)
    holders = []
    for src, dst in pairs:
        es = _esc(src)
        if es in s:
            ph = f"\x00{len(holders)}\x00"
            holders.append(f"<x>{_esc(dst)}</x>")
            s = s.replace(es, ph)
    for i, h in enumerate(holders):
        s = s.replace(f"\x00{i}\x00", h)
    return s


def deepl(text, lang, context=None):
    st = config.get()
    key = st.deepl_key.strip()
    marked = apply_glossary_xml(text, st.glossary_pairs())
    ctx = "\n".join(x for x in [st.domain_hint.strip(), (context or "").strip() if context and context.strip() != text else ""] if x)

    def body(with_model):
        b = {"text": [marked], "target_lang": "VI", "tag_handling": "xml", "ignore_tags": ["x"],
             "preserve_formatting": True}
        if lang in ("ZH", "JA"):
            b["source_lang"] = lang
        if ctx:
            b["context"] = ctx
        if with_model:
            b["model_type"] = "prefer_quality_optimized"
        return b

    try:
        code, resp = _send(key, "/v2/translate", "POST", body(True))
        if code == 400:
            code, resp = _send(key, "/v2/translate", "POST", body(False))
    except requests.RequestException as e:
        raise TranslateError(f"không kết nối được ({type(e).__name__})")
    if code == 200:
        try:
            out = json.loads(resp)["translations"][0]["text"]
        except Exception:
            raise TranslateError("phản hồi không hợp lệ")
        return TranslateResult(_unesc(out.replace("<x>", "").replace("</x>", "")), "DeepL")
    if code == 403:
        raise TranslateError("API key không hợp lệ")
    if code == 456:
        raise TranslateError("đã hết số ký tự của gói")
    if code == 429:
        raise TranslateError("gửi quá nhanh, thử lại sau")
    raise TranslateError(f"mã lỗi {code} {resp[:120]}")


def deepl_usage(key=None):
    key = (key if key is not None else config.get().deepl_key).strip()
    if not key:
        return "Chưa có key"
    try:
        code, resp = _send(key, "/v2/usage")
    except requests.RequestException:
        return "Không kết nối được"
    if code != 200:
        return "Key không hợp lệ" if code == 403 else f"Lỗi {code}"
    j = json.loads(resp)
    used, lim = j.get("character_count", 0), j.get("character_limit", 0)
    return f"Key hợp lệ. Đã dùng {used:,} / {lim:,} ký tự".replace(",", ".")


def offline(text, lang):
    st = config.get()
    t = text
    names = []
    for a, b in st.glossary_pairs():
        if a in t:
            names.append(b)
            t = t.replace(a, f" X{len(names)} ")
    try:
        out = OFFLINE.translate(t, lang)
    except TranslateError:
        raise
    except Exception as e:
        raise TranslateError(f"Dịch offline lỗi: {e}")
    if names:
        def back(m):
            i = int(m.group(1)) - 1
            return names[i] if 0 <= i < len(names) else m.group(0)
        out = re.sub(r"\bX\s?-?\s?(\d{1,2})\b", back, out)
    return TranslateResult(out, "Offline")


def translate(text, lang, context=None, engine=None):
    st = config.get()
    engine = engine or st.engine
    clean = text.strip()
    if not clean:
        raise TranslateError("Không có chữ để dịch")
    key = (engine, lang, hash(context), hash(st.glossary), hash(st.domain_hint), clean)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    use_deepl = engine == "DEEPL" and st.deepl_key.strip()
    if use_deepl:
        try:
            res = deepl(clean, lang, context)
        except TranslateError as e:
            if not st.fallback_offline:
                raise
            r = offline(clean, lang)
            res = TranslateResult(r.text, r.engine, f"DeepL lỗi: {e} -> đã dịch offline")
    else:
        r = offline(clean, lang)
        res = TranslateResult(r.text, r.engine, "Chưa nhập DeepL API key -> đang dịch offline") if engine == "DEEPL" else r
    with _cache_lock:
        _cache[key] = res
        while len(_cache) > 300:
            _cache.popitem(last=False)
    return res


_SENT = re.compile(r"(?<=[。！？!?；;\n])")


def split_sentences(text):
    parts = [p.strip() for p in _SENT.split(text) if p.strip()]
    return parts or [text]
