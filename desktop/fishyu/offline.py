import shutil
import threading
import zipfile
from pathlib import Path

import requests

from .paths import models_dir

MODEL_URL = "https://github.com/thanhhfishyu/Fishyu-Translate/releases/download/models-v1/opus-{lang}-vi.zip"
FILES = ("model.bin", "config.json", "shared_vocabulary.json", "source.spm", "target.spm")


class _Offline:
    def __init__(self):
        self._lock = threading.Lock()
        self._models = {}

    @staticmethod
    def code(lang):
        return "ja" if lang == "JA" else "zh"

    def path(self, lang) -> Path:
        return models_dir() / f"opus-{self.code(lang)}-vi"

    def installed(self, lang) -> bool:
        p = self.path(lang)
        return all((p / f).exists() for f in FILES)

    def download(self, lang, progress=None):
        from .translator import TranslateError
        url = MODEL_URL.format(lang=self.code(lang))
        tmp = models_dir() / f"opus-{self.code(lang)}-vi.zip.part"
        try:
            with requests.get(url, stream=True, timeout=(15, 60)) as r:
                if r.status_code != 200:
                    raise TranslateError(f"không tải được gói offline (mã {r.status_code})")
                total = int(r.headers.get("content-length") or 0)
                done = 0
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                        done += len(chunk)
                        if progress and total:
                            progress(done, total)
            dest = self.path(lang)
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(tmp) as z:
                for n in z.namelist():
                    name = Path(n).name
                    if name in FILES:
                        with z.open(n) as src, open(dest / name, "wb") as out:
                            shutil.copyfileobj(src, out)
            if not self.installed(lang):
                raise TranslateError("gói offline bị thiếu tệp")
        except requests.RequestException as e:
            raise TranslateError(f"không tải được gói offline ({type(e).__name__})")
        finally:
            try:
                tmp.unlink()
            except Exception:
                pass

    def _load(self, lang):
        key = self.code(lang)
        if key in self._models:
            return self._models[key]
        if not self.installed(lang):
            self.download(lang)
        import ctranslate2
        import sentencepiece as spm
        p = str(self.path(lang))
        tr = ctranslate2.Translator(p, device="cpu", compute_type="int8")
        src = spm.SentencePieceProcessor(model_file=p + "/source.spm")
        tgt = spm.SentencePieceProcessor(model_file=p + "/target.spm")
        self._models[key] = (tr, src, tgt)
        return self._models[key]

    def translate(self, text, lang):
        from .translator import split_sentences
        with self._lock:
            tr, src, tgt = self._load(lang)
            out_lines = []
            for para in text.split("\n"):
                sents = split_sentences(para) if para.strip() else []
                if not sents:
                    continue
                toks = [src.encode(s, out_type=str)[:400] + ["</s>"] for s in sents]
                res = tr.translate_batch(toks, beam_size=4, max_decoding_length=256,
                                         repetition_penalty=1.2, no_repeat_ngram_size=3)
                out_lines.append(" ".join(tgt.decode(r.hypotheses[0]) for r in res))
            return "\n".join(out_lines)


OFFLINE = _Offline()
