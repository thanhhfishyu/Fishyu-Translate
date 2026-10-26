# Giấy phép của thành phần bên thứ ba

Mã nguồn của Fishyu Translate (Android, Windows, Linux) được phát hành theo giấy phép MIT, xem file `LICENSE`.

Các thư viện, dữ liệu, mô hình và phông chữ dưới đây đi kèm hoặc được tải về khi dùng app. Mỗi thành phần vẫn giữ giấy phép riêng của nó; giấy phép MIT của dự án không thay thế các giấy phép đó.

## Dữ liệu dùng chung (cả ba bản)

| Thành phần | Giấy phép | Nguồn |
|---|---|---|
| CC-CEDICT (từ điển Trung - Anh, pinyin) © MDBG | CC BY-SA 4.0 | https://www.mdbg.net/chinese/dictionary?page=cc-cedict |
| Unicode Unihan Database (âm Hán Việt, trường kVietnamese) © Unicode, Inc. | Unicode License v3 | https://www.unicode.org/license.txt |
| Phông chữ Baloo 2 © Ek Type | SIL Open Font License 1.1 | https://github.com/EkType/Baloo2 |

Dữ liệu từ điển trong `cedict.dat` là bản chuyển định dạng của CC-CEDICT và vẫn theo giấy phép CC BY-SA 4.0: được dùng, chia sẻ, chỉnh sửa với điều kiện ghi nguồn và giữ nguyên giấy phép này cho phần dữ liệu đó.

## Bản Android

| Thành phần | Giấy phép |
|---|---|
| Kotlin, kotlinx.coroutines (JetBrains) | Apache-2.0 |
| AndroidX Core, AppCompat (Google) | Apache-2.0 |
| Material Components for Android (Google) | Apache-2.0 |
| OkHttp (Square) | Apache-2.0 |
| Google ML Kit: Text Recognition v2 (Chinese, Japanese), Translation | Điều khoản dịch vụ ML Kit: https://developers.google.com/ml-kit/terms |

## Bản Windows và Linux

| Thành phần | Giấy phép |
|---|---|
| Python (Python Software Foundation) | PSF License |
| Qt 6, PySide6, Shiboken6 (The Qt Company) | LGPL-3.0 |
| RapidOCR | Apache-2.0 |
| Mô hình nhận dạng chữ PaddleOCR PP-OCR (Baidu) | Apache-2.0 |
| ONNX Runtime (Microsoft) | MIT |
| OpenCV | Apache-2.0 |
| NumPy | BSD-3-Clause |
| Pillow | MIT-CMU |
| Shapely | BSD-3-Clause |
| pyclipper | MIT |
| OmegaConf | BSD-3-Clause |
| PyYAML | MIT |
| colorlog, six, charset-normalizer, urllib3 | MIT |
| tqdm | MPL-2.0 và MIT |
| certifi | MPL-2.0 |
| idna, click, httpx2, httpcore2, MarkupSafe | BSD-3-Clause |
| requests | Apache-2.0 |
| flatbuffers | Apache-2.0 |
| protobuf | BSD-3-Clause |
| packaging | Apache-2.0 hoặc BSD-2-Clause |
| CTranslate2 (OpenNMT) | MIT |
| SentencePiece (Google) | Apache-2.0 |
| Mô hình dịch offline Opus-MT zh-vi, ja-vi (Helsinki-NLP, Jörg Tiedemann và cộng sự), tải về khi dùng lần đầu | CC-BY 4.0 |
| PyInstaller (bootloader) | GPL-2.0 kèm ngoại lệ cho phép đóng gói phần mềm theo giấy phép bất kỳ |

Chỉ có trong bản Windows:

| Thành phần | Giấy phép |
|---|---|
| Inno Setup (trình cài đặt) | Inno Setup License |

Chỉ có trong bản Linux:

| Thành phần | Giấy phép |
|---|---|
| python-xlib | LGPL-2.1 trở lên |
| jeepney | MIT |
| Phông chữ Noto Sans CJK (Google, Adobe) | SIL Open Font License 1.1 |
| Thư viện hệ thống đóng kèm trong AppImage (libxcb, libxkbcommon, fontconfig, freetype, glib, dbus...) | Giấy phép riêng của từng thư viện (MIT/X11, LGPL...) |
| AppImage runtime | MIT |

## Về các thư viện LGPL (Qt, PySide6, python-xlib)

Các thư viện này được đóng kèm dưới dạng thư viện liên kết động, nằm thành các file riêng trong thư mục cài đặt (Windows), trong gói .deb, trong file .tar.gz, hoặc bên trong AppImage (giải nén bằng `--appimage-extract`). Bạn có thể thay chúng bằng phiên bản khác tương thích. Mã nguồn của Qt, PySide6 và python-xlib có tại:

- https://download.qt.io/official_releases/qt/ và https://code.qt.io/
- https://code.qt.io/cgit/pyside/pyside-setup.git/
- https://github.com/python-xlib/python-xlib

Phiên bản chính xác của từng thư viện Python được ghi trong `desktop/requirements.txt` và `app/build.gradle.kts`.
