import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops

PKG = "com.fishyu.translate"
OUT = sys.argv[2] if len(sys.argv) > 2 else "e2e-out"
APK = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
report = {"steps": []}


def adb(*args, check=False, timeout=120):
    r = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)}: {r.stdout} {r.stderr}")
    return r.stdout


def sh(cmd, **kw):
    return adb("shell", cmd, **kw)


def step(name, ok, info=""):
    report["steps"].append({"name": name, "ok": bool(ok), "info": info})
    print(("PASS " if ok else "FAIL ") + name + (f": {info}" if info else ""), flush=True)
    if not ok:
        finish(False)


def finish(ok):
    report["ok"] = ok
    with open(os.path.join(OUT, "logcat.txt"), "w") as fh:
        fh.write(adb("logcat", "-d", "-v", "time", timeout=60))
    crash = sh(f"run-as {PKG} cat files/last_error.txt 2>/dev/null")
    report["crash_log"] = crash
    with open(os.path.join(OUT, "report.json"), "w") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    sys.exit(0 if ok else 1)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    with open(path, "wb") as fh:
        fh.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout)
    return Image.open(path).convert("RGB")


def _raw_dump(name):
    out = sh("uiautomator dump /sdcard/ui.xml", timeout=60)
    if "dumped" not in out:
        return None
    xml = sh("cat /sdcard/ui.xml")
    with open(os.path.join(OUT, name + ".xml"), "w") as fh:
        fh.write(xml)
    try:
        return ET.fromstring(xml)
    except ET.ParseError:
        return None


def dismiss_dialogs(root):
    if root is None:
        return False
    texts = [n.get("text") or "" for n in root.iter("node")]
    if not any("isn't responding" in t or "keeps stopping" in t or "không phản hồi" in t for t in texts):
        return False
    for n in root.iter("node"):
        if (n.get("text") or "") in ("Wait", "Close app", "Đợi", "Close"):
            tap_node(n)
            time.sleep(2)
            return True
    sh("am broadcast -a android.intent.action.CLOSE_SYSTEM_DIALOGS")
    time.sleep(2)
    return True


def dump(name="ui"):
    for _ in range(8):
        root = _raw_dump(name)
        if root is not None and not dismiss_dialogs(root):
            return root
        time.sleep(1.5)
    return root


def bounds(node):
    x0, y0, x1, y1 = map(int, re.findall(r"\d+", node.get("bounds")))
    return x0, y0, x1, y1


def find(root, pred):
    if root is None:
        return []
    return [n for n in root.iter("node") if pred(n)]


def tap_node(n):
    x0, y0, x1, y1 = bounds(n)
    sh(f"input tap {(x0 + x1) // 2} {(y0 + y1) // 2}")


def has_cjk(s):
    return any("一" <= c <= "鿿" for c in s or "")


def resumed():
    out = sh("dumpsys activity activities")
    m = re.search(r"topResumedActivity=.*? ([\w.]+/[\w.$]+)", out) or re.search(r"mResumedActivity: .*? ([\w.]+/[\w.$]+)", out)
    return m.group(1) if m else ""


def wait(pred, sec, every=1.5):
    end = time.time() + sec
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(every)
    return pred()


TARGETS = ["com.google.android.documentsui", "com.android.documentsui", "com.google.android.contacts",
           "com.google.android.deskclock", "com.android.contacts"]
TARGET = None


def installed(pkg):
    return f"package:{pkg}" in sh(f"pm list packages {pkg}")


def open_target():
    sh(f"monkey -p {TARGET} -c android.intent.category.LAUNCHER 1")
    time.sleep(3)


def texts_of(root):
    return sorted({n.get("text") for n in root.iter("node") if n.get("text")}) if root is not None else []


def text_regions(root):
    out = []
    for n in find(root, lambda n: has_cjk(n.get("text"))):
        x0, y0, x1, y1 = bounds(n)
        if x1 - x0 > 20 and y1 - y0 > 12:
            out.append((n.get("text"), (x0, y0, x1, y1)))
    return out


def changed_regions(before, after, regions):
    res = []
    for text, box in regions:
        a = before.crop(box)
        b = after.crop(box)
        diff = ImageChops.difference(a, b).convert("L")
        hist = diff.histogram()
        moved = sum(hist[40:]) / max(1, sum(hist))
        res.append((text, round(moved, 3)))
    return res


def replaced(before, regions):
    img = shot("probe")
    r = changed_regions(before, img, regions)
    n = sum(1 for _, v in r if v > 0.04)
    return (n >= max(2, len(r) // 2), r, img)


def enable_replace():
    sh(f"am start -W -n {PKG}/.MainActivity")
    time.sleep(2)
    btn = None
    for _ in range(14):
        root = dump("main")
        hits = find(root, lambda n: n.get("text") in ("Bật thay chữ", "Tắt thay chữ"))
        if hits:
            x0, y0, x1, y1 = bounds(hits[0])
            if y1 < 2200 and y0 > 150:
                btn = hits[0]
                break
        sh("input swipe 540 1600 540 700 400")
        time.sleep(1)
    if btn is None:
        return "không thấy nút Bật thay chữ"
    if btn.get("text") == "Tắt thay chữ":
        return "ok"
    tap_node(btn)
    time.sleep(2.5)
    for _ in range(6):
        root = dump("consent")
        texts = [n.get("text") or "" for n in root.iter("node")] if root is not None else []
        if any("thay chữ" in t.lower() for t in texts) and not any(t in ("Start", "Start now", "Bắt đầu") for t in texts):
            break
        for want in ("Entire screen", "Share entire screen"):
            for n in find(root, lambda n, w=want: n.get("text") == w):
                tap_node(n)
                time.sleep(1)
        hits = find(root, lambda n: n.get("text") in ("Start", "Start now", "Bắt đầu", "Bắt đầu ngay", "Next"))
        if not hits:
            break
        tap_node(hits[-1])
        time.sleep(2)
    ok = wait(lambda: "Đang thay chữ" in sh("dumpsys notification --noredact"), 25)
    return "ok" if ok else "thông báo thay chữ không xuất hiện"


def main():
    adb("install", "-r", "-g", APK, check=True, timeout=300)
    sh(f"appops set {PKG} SYSTEM_ALERT_WINDOW allow")
    sh(f"appops set {PKG} PROJECT_MEDIA allow")
    sh(f"pm grant {PKG} android.permission.POST_NOTIFICATIONS")
    sh("settings put global window_animation_scale 0")
    sh("settings put global transition_animation_scale 0")
    sh("settings put global animator_duration_scale 0")
    prefs = ('<?xml version="1.0" encoding="utf-8" standalone="yes" ?>\n<map>\n'
             '<string name="replace_engine">OFFLINE</string>\n<string name="engine">OFFLINE</string>\n'
             '<string name="src">ZH</string>\n</map>\n')
    with open(os.path.join(OUT, "settings.xml"), "w") as fh:
        fh.write(prefs)
    adb("push", os.path.join(OUT, "settings.xml"), "/data/local/tmp/fishyu_settings.xml", check=True)
    sh("chmod 644 /data/local/tmp/fishyu_settings.xml")
    sh(f"am force-stop {PKG}")
    sh(f"run-as {PKG} mkdir -p shared_prefs")
    sh(f"run-as {PKG} cp /data/local/tmp/fishyu_settings.xml shared_prefs/settings.xml")
    sh("input keyevent KEYCODE_WAKEUP")
    sh("wm dismiss-keyguard")
    global TARGET
    regions = []
    for pkg in TARGETS:
        if not installed(pkg):
            continue
        sh(f"cmd locale set-app-locales {pkg} --locales zh-CN")
        sh(f"am force-stop {pkg}")
        TARGET = pkg
        open_target()
        for i in range(6):
            if "permission" in resumed().lower():
                sh("input keyevent KEYCODE_BACK")
            root = dump(f"target_{pkg}_{i}")
            regions = text_regions(root)
            print(pkg, i, resumed(), texts_of(root)[:8], flush=True)
            if len(regions) >= 3:
                break
            shot(f"target_{pkg}_{i}")
            time.sleep(4)
        if len(regions) >= 3:
            break
    before = shot("01_target_zh")
    step("target app shows Chinese text", len(regions) >= 3, f"{TARGET}: {len(regions)} vùng chữ")

    r = enable_replace()
    step("replace mode starts", r == "ok", r)
    open_target()
    res = wait(lambda: (lambda t: t if t[0] else None)(replaced(before, regions)), 150, every=4)
    if not res:
        res = replaced(before, regions)
    ok, diffs, img = res
    img.save(os.path.join(OUT, "02_replaced_app_overlay.png"))
    step("translation painted over Chinese text", ok, json.dumps(diffs, ensure_ascii=False)[:600])

    root = dump("target_with_overlay")
    targets = find(root, lambda n: has_cjk(n.get("text")) and n.get("clickable") == "true" or
                   has_cjk(n.get("text")) and bounds(n)[1] > 300)
    step("clickable Chinese item found", bool(targets))
    home = texts_of(root)
    tap_node(targets[min(1, len(targets) - 1)])
    nav = wait(lambda: texts_of(dump("after_tap")) != home, 10, every=1)
    step("tap passes through overlay (app overlay mode)", bool(nav), json.dumps(texts_of(dump("after_tap"))[:12], ensure_ascii=False))
    time.sleep(15)
    shot("04_subpage_replaced")

    sh(f"settings put secure enabled_accessibility_services {PKG}/{PKG}.OverlayAccess")
    sh("settings put secure accessibility_enabled 1")
    connected = wait(lambda: f"{PKG}/.OverlayAccess" in sh("dumpsys accessibility") or "OverlayAccess" in sh("dumpsys accessibility"), 20)
    step("accessibility service connects", bool(connected))
    sh("input keyevent KEYCODE_BACK")
    time.sleep(2)
    sh(f"am force-stop {TARGET}")
    open_target()
    res = wait(lambda: (lambda t: t if t[0] else None)(replaced(before, regions)), 120, every=4)
    if not res:
        res = replaced(before, regions)
    ok, diffs, img = res
    img.save(os.path.join(OUT, "05_replaced_trusted_overlay.png"))
    step("translation painted in trusted mode", ok, json.dumps(diffs, ensure_ascii=False)[:600])
    root = dump("target_trusted")
    targets = find(root, lambda n: has_cjk(n.get("text")) and n.get("clickable") == "true" or
                   has_cjk(n.get("text")) and bounds(n)[1] > 300)
    time.sleep(4)
    windows = sh("dumpsys window windows")
    report["windows"] = [l.strip() for l in windows.splitlines() if PKG in l or "ACCESSIBILITY_OVERLAY" in l][:30]
    shot("05b_before_trusted_tap")
    home = texts_of(root)
    tap_node(targets[min(1, len(targets) - 1)])
    nav = wait(lambda: texts_of(dump("after_tap_trusted")) != home, 10, every=1)
    step("tap passes through overlay (trusted mode)", bool(nav), json.dumps(texts_of(dump("after_tap_trusted"))[:12], ensure_ascii=False))
    time.sleep(10)
    shot("06_trusted_subpage")
    pid = sh(f"pidof {PKG}").strip()
    crash = sh(f"run-as {PKG} cat files/last_error.txt 2>/dev/null").strip()
    step("app still running without crash", bool(pid) and not crash, crash[:400])
    finish(True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        report["error"] = repr(e)
        finish(False)
