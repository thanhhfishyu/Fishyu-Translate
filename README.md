# Fishyu Translate

App Android dịch chữ tiếng Trung và tiếng Nhật trên màn hình sang tiếng Việt, dùng DeepL.
<Tui làm app này theo order của anh rể tui, mọi người có thể tham khảo và sử dụng>

## Tính năng

- Bong bóng nổi: chạm vào để khoanh vùng cần dịch, chạm vào một đoạn chữ để dịch cả đoạn, hoặc dịch cả màn hình.
- Bôi đen chữ trong app bất kỳ rồi chọn "Dịch (Fishyu)" trong menu. Cũng có trong mục Chia sẻ.
- Dịch chữ đã copy (giữ bong bóng để mở menu).
- Tra từ: pinyin, âm Hán Việt, nghĩa theo ngữ cảnh.
- Bảng thuật ngữ để giữ cố định tên riêng và thuật ngữ chuyên ngành.
- Gợi ý lĩnh vực (y học, sinh học, tiểu thuyết...) gửi kèm làm ngữ cảnh.
- OCR offline cho chữ Trung (giản thể, phồn thể) và chữ Nhật.
- Dịch offline khi chưa có key DeepL hoặc hết quota.
- Nút bật/tắt trong thanh cài đặt nhanh.

## Cài đặt

1. Tải file apk mới nhất ở mục Releases và cài lên điện thoại.
2. Mở app, dán DeepL API key (lấy miễn phí tại https://www.deepl.com/pro-api, gói API Free cho dev 500.000 ký tự/tháng).
3. Bấm "Bật bong bóng" và cấp quyền hiển thị trên ứng dụng khác, thông báo, ghi màn hình. Từ Android 14 trở lên chọn "Toàn bộ màn hình".
anyway, nếu không biết lấy API DeepL kiểu gì thì tự tìm trên internet nhớ :V
## Build

```
./gradlew assembleRelease
```

Mỗi lần push lên nhánh main, GitHub Actions sẽ build và tạo Release mới.

## Dữ liệu

- CC-CEDICT, MDBG, CC BY-SA 4.0
- Unicode Unihan Database
- Google ML Kit
