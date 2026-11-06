# Fishyu Translate

App dịch chữ tiếng Trung và tiếng Nhật trên màn hình sang tiếng Việt, dùng DeepL. Có bản Android, Windows và Linux.
<Tui làm app này theo order của anh rể tui, mọi người có thể tham khảo và sử dụng>

## Tính năng

- Bong bóng nổi: chạm vào để khoanh vùng cần dịch, chạm vào một đoạn chữ để dịch cả đoạn, hoặc dịch cả màn hình.
- Thay chữ trên màn hình: app đọc chữ Trung/Nhật rồi viết đè bản dịch tiếng Việt lên đúng chỗ đó, giữ màu chữ và màu nền, như thể chữ đã được thay. Vẫn chạm, cuộn, lật trang, chơi game bình thường; khi nội dung đổi, bản dịch tự cập nhật. Mỗi đoạn chỉ dịch một lần nên quay lại trang cũ không tốn thêm ký tự DeepL.
- Bôi đen chữ trong app bất kỳ rồi chọn "Dịch (Fishyu)" trong menu. Cũng có trong mục Chia sẻ.
- Dịch trực tiếp cho game: khoanh khung thoại một lần, app tự dịch lại mỗi khi chữ thay đổi mà không chặn thao tác trong game. Chọn được DeepL hoặc dịch offline.
- Dịch chữ đã copy (giữ bong bóng để mở menu).
- Tra từ: pinyin, âm Hán Việt, nghĩa theo ngữ cảnh.
- Bảng thuật ngữ để giữ cố định tên riêng và thuật ngữ chuyên ngành.
- Gợi ý lĩnh vực (y học, sinh học, tiểu thuyết...) gửi kèm làm ngữ cảnh.
- OCR offline cho chữ Trung (giản thể, phồn thể) và chữ Nhật.
- Dịch offline khi chưa có key DeepL hoặc hết quota.
- Nút bật/tắt trong thanh cài đặt nhanh.

## Cài đặt (Android)

1. Tải file apk mới nhất ở mục Releases và cài lên điện thoại.
2. Mở app, dán DeepL API key (lấy miễn phí tại https://www.deepl.com/pro-api, gói Developer cho 1 triệu ký tự dùng một lần).
3. Bấm "Bật bong bóng" và cấp quyền hiển thị trên ứng dụng khác, thông báo, ghi màn hình. Từ Android 14 trở lên chọn "Toàn bộ màn hình".
4. Muốn dùng "Thay chữ trên màn hình": giữ bong bóng và chọn mục đó, hoặc bấm "Bật thay chữ" trong app. Từ Android 12, lớp phủ cho chạm xuyên qua chỉ được che tối đa 80% nên chữ gốc còn hiện mờ; bật thêm quyền Trợ năng "Fishyu Translate - hiển thị rõ nét" để che kín. Nếu mục này bị mờ: Thông tin ứng dụng, chạm ⋮, chọn "Cho phép cài đặt bị hạn chế".
anyway, nếu không biết lấy API DeepL kiểu gì thì tự tìm trên internet nhớ :V
## Fishyu Translate for Windows

Bản cho máy tính Windows 10/11 (64-bit), có các tính năng tương tự bản Android:

- Bong bóng cá mập nổi trên màn hình. Bấm `Ctrl+Alt+Q` (hoặc bấm vào bong bóng) để khoanh vùng dịch, bấm vào một đoạn chữ để dịch cả đoạn.
- Thay chữ trên màn hình (`Ctrl+Alt+R`): bản dịch được viết đè ngay lên chữ gốc trên màn hình đang dùng, chuột và bàn phím đi xuyên qua, tự cập nhật khi nội dung đổi.
- Cửa sổ dịch được ghim luôn nằm trên cùng: chuyển sang game hay app đọc truyện vẫn thấy, không bị trôi ra sau.
- Dịch trực tiếp cho game (`Ctrl+Alt+W`): khoanh khung thoại một lần, app tự dịch lại khi chữ đổi. Bấm vào khung dịch không làm game mất chuột/bàn phím.
- Bôi đen chữ rồi bấm `Ctrl+C` hai lần, hoặc `Ctrl+Alt+E`, để dịch chữ đã copy.
- Tra từ, bảng thuật ngữ, gợi ý lĩnh vực, DeepL hoặc dịch offline (gói offline tự tải khi dùng lần đầu).
- Đổi được phím tắt, chạy ẩn ở khay hệ thống, khởi động cùng Windows.

Cài đặt: vào mục Releases, tải `FishyuTranslate-for-Windows-Setup-v1.0.x.exe` rồi chạy. Nếu Windows báo "Windows protected your PC", chọn "More info" rồi "Run anyway". Bản `Portable` thì giải nén rồi chạy `FishyuTranslate.exe`.

Với game chạy toàn màn hình, hãy chọn chế độ hiển thị Borderless hoặc Windowed trong game để cửa sổ dịch hiện được lên trên.

## Fishyu Translate for Linux

Bản cho Linux 64-bit (Ubuntu 22.04+, Debian 12+, Fedora 36+, Linux Mint, Pop!_OS...), giữ các tính năng như bản Windows: bong bóng cá mập, khoanh vùng dịch, cửa sổ dịch ghim trên cùng, dịch trực tiếp cho game, tra từ, bảng thuật ngữ, DeepL hoặc dịch offline.

Cài đặt, vào mục Releases và chọn một trong ba:

- `fishyu-translate_1.0.x_amd64.deb` cho Ubuntu, Debian, Mint...: `sudo apt install ./fishyu-translate_1.0.x_amd64.deb`, sau đó mở "Fishyu Translate" trong menu ứng dụng hoặc chạy `fishyu-translate`.
- `FishyuTranslate-for-Linux-x86_64-v1.0.x.AppImage` cho mọi bản Linux: `chmod +x` rồi chạy. Nếu báo thiếu FUSE thì cài `libfuse2` (Ubuntu) hoặc chạy kèm `--appimage-extract-and-run`.
- `...tar.gz`: giải nén rồi chạy `FishyuTranslate/FishyuTranslate`.

Lưu ý khi dùng:

- Trên X11: mọi tính năng chạy giống bản Windows, phím tắt mặc định `Ctrl+Alt+Q`, `Ctrl+Alt+R`, `Ctrl+Alt+W`, `Ctrl+Alt+E`. Khi đang thay chữ, mỗi lần bấm chuột hay phím lớp dịch tắt rất nhanh rồi hiện lại để kiểm tra nội dung có đổi không.
- Trên Wayland (mặc định của Ubuntu, Fedora đời mới): lần đầu khoanh vùng, hệ thống sẽ hỏi quyền chụp màn hình, hãy cho phép. Phím tắt được đăng ký qua hệ thống nếu máy hỗ trợ; nếu không, mở Cài đặt của app, chép các lệnh `--capture`, `--replace`, `--live`, `--clipboard` rồi gắn vào phím tắt tuỳ chỉnh của hệ thống. Thay chữ trên Wayland không tự cập nhật được: mỗi lần bấm phím tắt, app chụp và dịch lại màn hình hiện tại.
- `Ctrl+Alt+E` dịch luôn chữ đang bôi đen, không cần Ctrl+C. Trên Wayland nên cài thêm `wl-clipboard`.
- Biểu tượng ở khay hệ thống trên GNOME cần tiện ích AppIndicator (Ubuntu có sẵn).

## Build

```
./gradlew assembleRelease
```

Bản Windows và Linux dùng chung mã nguồn trong thư mục `desktop/` (Python, PySide6, RapidOCR):

```
cd desktop
pip install -r requirements.txt pyinstaller
pyinstaller FishyuTranslate.spec
```

Trên Linux, `packaging/linux/build_packages.sh` tạo AppImage, .deb và .tar.gz từ thư mục `dist/`.

Mỗi lần push lên nhánh main, GitHub Actions sẽ build và tạo Release mới (bản Windows được kiểm tra tự động trên máy Windows, bản Linux trên Ubuntu 22.04, Ubuntu 24.04, Debian 12 và Fedora 41 trước khi phát hành).

## Dữ liệu

- CC-CEDICT, MDBG, CC BY-SA 4.0
- Unicode Unihan Database
- Google ML Kit
- RapidOCR / PaddleOCR, Opus-MT (Helsinki-NLP, CC-BY 4.0)

## Giấy phép

Fishyu Translate (cả bản Android, Windows và Linux) là phần mềm mã nguồn mở theo [giấy phép MIT](LICENSE): được dùng, sửa, chia sẻ và phát hành lại tự do, miễn là giữ lại thông báo bản quyền và giấy phép.

Các thư viện, mô hình, từ điển và phông chữ đi kèm vẫn theo giấy phép riêng của chúng, xem [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Trong app, mở mục "Giấy phép mã nguồn mở" ở cuối màn hình chính (Android) hoặc cuối cửa sổ cài đặt (Windows, Linux) để xem.
