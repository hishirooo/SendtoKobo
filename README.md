
# SendtoKobo

> **Công cụ chuyển đổi và gửi sách EPUB sang máy đọc sách Kobo qua WiFi**

<img width="486" height="502" alt="image" src="https://github.com/user-attachments/assets/b049aba9-af3a-4a94-8c9f-2d92f952de4d" />
<img width="716" height="582" alt="image" src="https://github.com/user-attachments/assets/d23cb910-a187-4383-8d6c-e61ef4f1ffb8" />


---

## Tính năng

- **Chuyển đổi EPUB sang KEPUB** tối ưu cho Kobo bằng [kepubify](https://github.com/pgaskin/kepubify)
- **Chia sẻ sách qua WiFi/LAN**: Tải trực tiếp từ máy tính sang Kobo mà không cần dây cáp
- **Giao diện thân thiện**: Kéo-thả, chọn thư mục, nhật ký hoạt động rõ ràng, hiển thị tiến trình
- **Hỗ trợ hủy tác vụ, tắt server nhanh**

---

## Yêu cầu hệ thống

- **Windows** (khuyến nghị)
- **Python 3.10+** ([Tải tại đây](https://www.python.org/downloads/))
- **Máy tính và Kobo kết nối cùng một mạng WiFi**

---

## Cài đặt

### 1. Cài Python

- Tải và cài đặt Python 3.10 hoặc mới hơn từ [python.org](https://www.python.org/downloads/)
- **Chú ý:** Khi cài, chọn **Add Python to PATH**

### 2. Cài thư viện Python cần thiết

Mở **CMD** tại thư mục dự án, chạy lệnh sau:

```sh
pip install PyQt6 PyQt6-Qt6 PyQt6-Qt6-Svg
```

> Nếu máy bạn chưa có pip, hãy cài đặt lại Python và đảm bảo tick “Add Python to PATH”.

### 3. Tải và đặt công cụ chuyển đổi

- Tải **kepubify-windows-64bit.exe** từ trang chủ [kepubify Releases](https://github.com/pgaskin/kepubify/releases)
- Đặt file `kepubify-windows-64bit.exe` vào **cùng thư mục** với `SendtoKobo.py`

### 4. Cấu trúc thư mục mẫu

```
SendtoKobo.py
kepubify-windows-64bit.exe
ui_SendFile.py
icons/
    file_1119057.png
    cancel_4308034.png
    flat-color-icons--folder.svg
```

> Nếu thiếu thư mục `icons`, bạn hãy tạo và thêm các icon như trên (có thể tự dùng icon khác).

---

## Sử dụng chương trình

### 1. Chạy chương trình

Mở CMD tại thư mục chứa `SendtoKobo.py` và chạy:

```sh
python SendtoKobo.py
```

### 2. Giao diện chính

- **Source folder**: Chọn thư mục chứa sách `.epub` gốc
- **Convert to kepub**: (Nên bật) Chuyển đổi EPUB sang KEPUB, tối ưu cho Kobo
- **Destination folder**: Thư mục lưu file KEPUB (chỉ dùng khi Convert)
- **Send**: Nhấn để chuyển đổi và/hoặc chia sẻ sách qua mạng LAN

### 3. Chia sẻ sách qua WiFi

- Sau khi nhấn **Send**, chương trình sẽ cung cấp một link LAN, ví dụ:  
  ```
  🌐 Đã bật chia sẻ: http://192.168.1.10:8080/
  ```
- **Dùng trình duyệt trên Kobo** (hoặc điện thoại, máy tính khác) truy cập link để tải sách về.

### 4. Hủy chuyển đổi / Tắt server

- Trong lúc đang chuyển đổi, nhấn **Send** lần nữa để **hủy**.
- Khi đang chia sẻ, nhấn **Send** để **tắt server**.

---

## Các thư viện cần thiết

Chương trình sử dụng:

- **PyQt6** (GUI)
- **PyQt6-Qt6-Svg** (hỗ trợ icon SVG)
- **Các thư viện chuẩn Python**: os, sys, time, subprocess, threading, socket, http.server, pathlib, typing, shutil, re, mimetypes, urllib.parse, http, traceback (không cần cài thêm)

> **Cài bằng một lệnh:**  
> `pip install PyQt6 PyQt6-Qt6 PyQt6-Qt6-Svg`

---

## Lưu ý

- **Máy tính và Kobo phải cùng WiFi/LAN**
- **Không cần root máy Kobo**
- Để tạo file chạy độc lập (`.exe`), có thể dùng [PyInstaller](https://pyinstaller.org/)  
  (Liên hệ tác giả nếu muốn hướng dẫn chi tiết đóng gói .exe)

---

## Troubleshooting

- **Không chạy được?**  
  Đảm bảo Python bản mới, đã cài đủ PyQt6 và các icon/`kepubify-windows-64bit.exe` đúng vị trí.
- **Không hiện giao diện?**  
  Thường do thiếu PyQt6 hoặc thư viện SVG. Hãy chạy lại lệnh pip bên trên.
- **Lỗi “Could not find kepubify…”?**  
  Hãy chắc chắn file `kepubify-windows-64bit.exe` nằm cùng thư mục với `SendtoKobo.py`

---

## Đóng góp & Bản quyền

- **Mã nguồn mở**, sử dụng tự do cho mục đích cá nhân/học tập.
- Tác giả: **HISHIRO**
- Dự án sử dụng icon từ [Flat Color Icons](https://github.com/flat-icon/flat-color-icons), [iconfinder](https://www.iconfinder.com/), v.v.
- Công cụ chuyển đổi: [kepubify](https://github.com/pgaskin/kepubify) – bản quyền thuộc tác giả gốc.

---

## Liên hệ

- Nếu gặp lỗi hoặc cần hướng dẫn chi tiết hơn, hãy tạo issue trên GitHub hoặc liên hệ qua email.

---
