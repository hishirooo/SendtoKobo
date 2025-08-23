import sys
import time
import subprocess
import threading
import socket
import http.server
import socketserver
from pathlib import Path
from typing import Optional
import shutil  # <--- thêm dòng này bên trên cùng các import khác
import os
import re
import mimetypes
import shutil
from urllib.parse import quote
from http import HTTPStatus


from PyQt6 import QtGui
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox

from ui_SendFile import Ui_Form  # UI sinh từ SendFile.ui

# Gom plugin SVG khi bundle (icon folder có .svg)
try:
    from PyQt6.QtSvgWidgets import QSvgWidget  # noqa: F401
except Exception:
    pass

PORT = 8080


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return str(Path(base) / rel)


KEPUBIFY_PATH = resource_path("kepubify-windows-64bit.exe")


class RangeDownloadHandler(http.server.SimpleHTTPRequestHandler):
    """
    Handler phục vụ file có hỗ trợ Range, gửi Content-Length chính xác,
    Connection: close và Content-Disposition: attachment.
    """
    protocol_version = "HTTP/1.1"

    def log_message(self, *args, **kwargs):
        pass  # giữ yên tĩnh

    def guess_type(self, path):
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        # EPUB/KEPUB
        if path.lower().endswith((".epub", ".kepub.epub")):
            ctype = "application/epub+zip"
        return ctype

    def _send_file_with_range(self, path, is_head=False):
        if not os.path.isfile(path):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        ctype = self.guess_type(path)
        fs = os.stat(path)
        size = fs.st_size
        start, end = 0, size - 1

        # Parse Range header (nếu có)
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2)) if m.group(2) else end
                if start > end or start >= size:
                    self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    return
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                # Range header không hợp lệ -> trả full
                self.send_response(HTTPStatus.OK)
        else:
            self.send_response(HTTPStatus.OK)

        length = end - start + 1
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        # Ép tải xuống và hỗ trợ tên Unicode
        filename = os.path.basename(path)
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename)}")
        # Đảm bảo client kết thúc phiên sau response
        self.send_header("Connection", "close")
        self.end_headers()

        if is_head:
            return

        # Gửi chính xác 'length' byte, rồi flush
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            bufsize = 64 * 1024
            while remaining > 0:
                chunk = f.read(min(bufsize, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)
            try:
                self.wfile.flush()
                # Thêm dòng này: Gửi tín hiệu kết thúc việc ghi dữ liệu (FIN packet)
                self.connection.shutdown(socket.SHUT_WR)
            except (socket.error, BrokenPipeError, ConnectionResetError):
                # Lỗi này là bình thường nếu client tự đóng kết nối trước
                pass
            except Exception:
                # Các lỗi khác nếu có
                pass
        # Đóng kết nối ở phía server
        self.close_connection = True

    # Nếu là thư mục, dùng xử lý mặc định (trả HTML listing)
    def do_GET(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().do_GET()
        return self._send_file_with_range(path, is_head=False)

    def do_HEAD(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().do_HEAD()
        return self._send_file_with_range(path, is_head=True)


class ReusableThreadingServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

class SendToKobo(QWidget):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # ----- state -----
        self.state = "idle"  # idle | processing | serving | stopping
        self.cancel_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        self.httpd: Optional[ReusableThreadingServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.local_ip = self._get_local_ip()

        # ----- wire UI -----
        self.ui.pushButton_SourceFolder.clicked.connect(self.choose_source)
        self.ui.pushButton_2.clicked.connect(self.choose_dest)
        self.ui.pushButton_Send.clicked.connect(self.on_send_clicked)
        self.ui.checkBox_Convert.toggled.connect(self.on_convert_toggle)

        # ----- icons -----
        self._init_icons()
        self._update_button_icon()
        self.on_convert_toggle(self.ui.checkBox_Convert.isChecked())

        # ----- log/progress -----
        self.log_signal.connect(self._append_log)
        self.ui.progressBar.setRange(0, 100)
        self.ui.progressBar.setValue(0)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(lambda: None)
        self.timer.start()

    # ========== ICON ==========
    def _init_icons(self):
        self.icon_send = QtGui.QIcon(resource_path('icons/file_1119057.png'))
        self.icon_cancel = QtGui.QIcon(resource_path('icons/cancel_4308034.png'))
        self.icon_folder = QtGui.QIcon(resource_path('icons/flat-color-icons--folder.svg'))
        try:
            self.setWindowIcon(self.icon_send)
        except Exception:
            pass
        self.ui.pushButton_SourceFolder.setIcon(self.icon_folder)
        self.ui.pushButton_2.setIcon(self.icon_folder)
        self.ui.pushButton_Send.setIcon(self.icon_send)
        # Xóa text – chỉ dùng PNG
        self.ui.pushButton_Send.setText("")
        for name in ('pushButton_Big', 'toolButton_Big', 'pushButton', 'toolButton'):
            w = getattr(self.ui, name, None)
            if w:
                w.setIcon(self.icon_send)
                try:
                    w.setText("")
                except Exception:
                    pass

    def _update_button_icon(self):
        """Chỉ đổi icon theo state (không đặt text)."""
        if self.state in ("processing", "serving", "stopping"):
            self.ui.pushButton_Send.setIcon(self.icon_cancel)
        else:
            self.ui.pushButton_Send.setIcon(self.icon_send)
        for name in ('pushButton_Big', 'toolButton_Big', 'pushButton', 'toolButton'):
            w = getattr(self.ui, name, None)
            if w:
                w.setIcon(self.icon_cancel if self.state in ("processing", "serving", "stopping") else self.icon_send)

    # ========== LOG ==========
    def _append_log(self, text: str):
        self.ui.listWidget_Log.addItem(text)
        self.ui.listWidget_Log.scrollToBottom()

    def log(self, text: str):
        self.log_signal.emit(text)

    # ========== BUSY UI ==========
    def _set_busy(self, busy: bool):
        """Hiển thị progress bar ‘indeterminate’ khi busy=True."""
        if busy:
            self.ui.progressBar.setRange(0, 0)
            self.ui.pushButton_Send.setEnabled(False)
        else:
            self.ui.progressBar.setRange(0, 100)
            self.ui.pushButton_Send.setEnabled(True)

    # ========== DEST enable ==========
    def on_convert_toggle(self, checked: bool):
        self.ui.lineEdit_Destination.setEnabled(checked)
        self.ui.pushButton_2.setEnabled(checked)

    # ========== browse ==========
    def choose_source(self):
        path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục nguồn')
        if path:
            self.ui.lineEdit_SourceFolder.setText(path)

    def choose_dest(self):
        path = QFileDialog.getExistingDirectory(self, 'Chọn thư mục đích')
        if path:
            self.ui.lineEdit_Destination.setText(path)

    # ========== network ==========
    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start_server(self, folder: Path):
        if self.httpd:
            return
        handler = lambda *a, directory=str(folder): RangeDownloadHandler(*a, directory=directory)
        self.httpd = ReusableThreadingServer(("", PORT), handler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.state = "serving"
        self._update_button_icon()
        self.log(f'🌐 Đã bật chia sẻ: http://{self.local_ip}:{PORT}/')


    def stop_server_async(self, notify: bool = True):
        """Tắt server dưới thread riêng, có animation & log mượt."""
        if not self.httpd:
            return
        if notify:
            self.log('⏹ Đang tắt chia sẻ… (đang đóng cổng)')
        self.state = "stopping"
        self._update_button_icon()
        self._set_busy(True)

        def _do_stop():
            try:
                try:
                    self.httpd.shutdown()
                finally:
                    self.httpd.server_close()
            except Exception as e:
                self.log(f'⚠️ Lỗi khi tắt server: {e}')
            finally:
                if self.server_thread:
                    self.server_thread.join(timeout=2.0)
                self.httpd = None
                self.server_thread = None
                # Đảm bảo người dùng thấy animation tối thiểu
                time.sleep(0.35)
                self._set_busy(False)
                self.state = "idle"
                self._update_button_icon()
                if notify:
                    self.log('✅ Đã tắt chia sẻ.')

        threading.Thread(target=_do_stop, daemon=True).start()

    def stop_server_blocking(self, notify: bool = False):
        """Tắt server và chờ hoàn tất (dùng khi thoát ứng dụng)."""
        if not self.httpd:
            return
        if notify:
            self.log('⏹ Đang tắt chia sẻ…')
        try:
            try:
                self.httpd.shutdown()
            finally:
                self.httpd.server_close()
        except Exception as e:
            self.log(f'⚠️ Lỗi khi tắt server: {e}')
        finally:
            if self.server_thread:
                self.server_thread.join(timeout=2.0)
            self.httpd = None
            self.server_thread = None
            self.state = "idle"
            self._update_button_icon()
            if notify:
                self.log('✅ Đã tắt chia sẻ.')

    # ========== convert ==========
    def _convert_folder(self, src: Path, dst: Path) -> int:
        if not Path(KEPUBIFY_PATH).exists():
            raise FileNotFoundError(f'Không tìm thấy kepubify: {KEPUBIFY_PATH}')
        dst.mkdir(parents=True, exist_ok=True)
        files = [p for p in src.glob('*.epub')
                 if p.is_file() and not p.name.lower().endswith('.kepub.epub')]
        total = len(files)
        count = 0
        for i, p in enumerate(files, start=1):
            if self.cancel_event.is_set():
                self.log('⏹ Đã huỷ theo yêu cầu.')
                break
            try:
                out = dst / (p.stem + '.kepub.epub')
                cmd = [KEPUBIFY_PATH, str(p), '-o', str(out)]
                creationflags = 0x08000000  # CREATE_NO_WINDOW
                cp = subprocess.run(
                    cmd, creationflags=creationflags,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='ignore'
                )
                if cp.returncode == 0 and out.exists():
                    count += 1
                    self.log(f'✅ {p.name} → {out.name}')
                else:
                    self.log(f'⚠️ Lỗi chuyển {p.name}: {cp.stdout[-400:]}')
            except Exception as e:
                self.log(f'❌ Lỗi {p.name}: {e}')
            finally:
                if total:
                    self.ui.progressBar.setValue(int(i * 100 / total))
        return count

    # ========== action ==========
    def on_send_clicked(self):
        # đang convert → Stop = huỷ
        if self.state == "processing":
            self.cancel_event.set()
            self.log("⏳ Đang huỷ tác vụ chuyển đổi...")
            return
        # đang share → Stop = tắt server
        if self.state == "serving":
            self.stop_server_async(notify=True)
            return
        if self.state == "stopping":
            return  # đang tắt, bỏ qua click

        # idle → bắt đầu tác vụ mới
        src = Path(self.ui.lineEdit_SourceFolder.text().strip())
        if not src.exists():
            QMessageBox.warning(self, 'Thiếu thư mục', 'Chưa chọn thư mục nguồn hoặc không tồn tại.')
            return

        if not self.ui.checkBox_Convert.isChecked():
            self.ui.progressBar.setValue(0)
            self.start_server(src)
            return

        dst_text = self.ui.lineEdit_Destination.text().strip()
        if not dst_text:
            QMessageBox.warning(self, 'Thiếu thư mục', 'Chưa chọn thư mục đích.')
            return
        dst = Path(dst_text)

        self.cancel_event.clear()
        self.state = "processing"
        self._update_button_icon()
        self.ui.progressBar.setValue(5)
        self.log('🔄 Đang chuyển đổi EPUB → KEPUB...')

        def task():
            try:
                n = self._convert_folder(src, dst)
                if not self.cancel_event.is_set():
                    if n == 0:
                        self.log('ℹ️ Không có tệp .epub nào cần chuyển đổi (hoặc tất cả đã là .kepub.epub).')
                    else:
                        self.log(f'✅ Hoàn tất chuyển {n} tệp.')
                    self.ui.progressBar.setValue(100)
                    self.start_server(dst)
            except FileNotFoundError as e:
                self.log(str(e))
                QMessageBox.critical(self, 'Thiếu công cụ',
                                     f'{e}\nHãy chắc rằng file kepubify nằm cạnh SendToKobo.exe')
                self.state = "idle"
                self._update_button_icon()
            except Exception as e:
                self.log(f'Lỗi: {e}')
                self.state = "idle"
                self._update_button_icon()
            finally:
                if self.cancel_event.is_set():
                    self.state = "idle"
                    self._update_button_icon()
                self.cancel_event.clear()

        self.worker_thread = threading.Thread(target=task, daemon=True)
        self.worker_thread.start()

    # ========== lifecycle ==========
    def closeEvent(self, event):
        try:
            self.cancel_event.set()
            self.stop_server_blocking(notify=True)
        finally:
            event.accept()


if __name__ == '__main__':
    # Safety harness: thông báo nếu lỗi khởi chạy
    from PyQt6.QtWidgets import QMessageBox
    import traceback
    try:
        app = QApplication(sys.argv)
        w = SendToKobo()
        w.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "Lỗi khởi chạy",
                             f"{e}\n\n{traceback.format_exc()}")
        raise
