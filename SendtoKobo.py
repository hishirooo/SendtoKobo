import os
import subprocess
import threading
import socket
import http.server
import socketserver
import urllib.request
import sys
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox
from PyQt6 import QtGui
from ui_SendFile import Ui_Form

PORT = 8080
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEPUBIFY_PATH = os.path.join(SCRIPT_DIR, "kepubify-windows-64bit.exe")
EBOOK_EXTENSIONS = [".epub", ".kepub.epub", ".pdf", ".mobi", ".azw3"]

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    # (Không có thay đổi ở class này)
    def list_directory(self, path):
        try:
            entries = os.listdir(path)
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None

        entries.sort(key=lambda a: a.lower())
        r = []
        displaypath = os.path.relpath(path, os.getcwd())
        enc = 'utf-8'
        r.append(f'<html><head><meta charset="{enc}"><title>Index of {displaypath}</title></head>')
        r.append(f'<body><h2>Index of {displaypath}</h2><hr><ul>')
        for name in entries:
            fullname = os.path.join(path, name)
            displayname = name
            if os.path.isdir(fullname):
                displayname = name + "/"
            elif not any(name.endswith(ext) for ext in EBOOK_EXTENSIONS):
                continue
            r.append(f'<li><a href="{displayname}">{displayname}</a></li>')
        r.append('</ul><hr></body></html>')
        encoded = '\n'.join(r).encode(enc, 'surrogateescape')
        f = self.wfile
        self.send_response(200)
        self.send_header("Content-Type", f"text/html; charset={enc}")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        f.write(encoded)
        return None

class SendToKobo(QWidget):
    server_shutdown_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.is_processing = False
        self.start_icon = QtGui.QIcon("icons/file_1119057.png")
        self.stop_icon = QtGui.QIcon("icons/cancel_4308034.png")
        self.ui.pushButton_Send.setIcon(self.start_icon)
        
        # --- THÊM MỚI: Các biến cho hoạt cảnh ---
        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(150)  # Tốc độ animation
        self.animation_timer.timeout.connect(self.update_log_animation)
        self.animation_chars = ["/", "-", "\\", "|"]
        self.animation_index = 0
        self.animated_log_item = None  # Lưu mục log đang được tạo hoạt cảnh
        # --- KẾT THÚC PHẦN THÊM MỚI ---
        
        self.ui.pushButton_SourceFolder.clicked.connect(self.select_source_folder)
        self.ui.pushButton_2.clicked.connect(self.select_destination_folder)
        self.ui.pushButton_Send.clicked.connect(self.toggle_process)
        self.ui.checkBox_Convert.stateChanged.connect(self.toggle_destination_enabled)
        
        self.server_shutdown_finished.connect(self.on_shutdown_finished)

        self.local_ip = get_local_ip()
        self.toggle_destination_enabled()
        self.httpd = None
        self.server_thread = None
        self.log(f"🚀 Gợi ý: Nhập địa chỉ IP trên Kobo/thiết bị: http://{self.local_ip}:{PORT}")

    # --- THÊM MỚI: Hàm để cập nhật hoạt cảnh ---
    def update_log_animation(self):
        if self.animated_log_item:
            char = self.animation_chars[self.animation_index]
            self.animated_log_item.setText(f"⏳ Đang dừng server, vui lòng chờ... {char}")
            self.animation_index = (self.animation_index + 1) % len(self.animation_chars)

    def closeEvent(self, event):
        # (Không có thay đổi ở hàm này)
        if self.is_processing and self.httpd:
             reply = QMessageBox.question(self, 'Thoát chương trình',
                                     "Server đang chạy. Bạn có chắc muốn tắt server và thoát?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        else:
            reply = QMessageBox.question(self, 'Thoát chương trình',
                                     "Bạn có chắc muốn thoát?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.is_processing and self.httpd:
                self.shutdown_server() 
            event.accept()
        else:
            event.ignore()
            
    def toggle_process(self):
        # (Không có thay đổi ở hàm này)
        if self.is_processing:
            self.stop_process()
        else:
            self.start_process()

    def stop_process(self):
        # (Không có thay đổi ở hàm này)
        if self.httpd:
            reply = QMessageBox.question(self, 'Dừng Server',
                                         "Bạn có chắc muốn dừng server chia sẻ file?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.shutdown_server()
        else:
            QMessageBox.information(self, "Thông báo", "Đang trong quá trình convert, không thể dừng lúc này.")

    # --- THAY ĐỔI: Hàm on_shutdown_finished sẽ dừng hoạt cảnh ---
    def on_shutdown_finished(self):
        self.animation_timer.stop()
        if self.animated_log_item:
            self.animated_log_item.setText("✅ Server đã dừng hoàn toàn.")
            self.animated_log_item = None
        
        self.httpd = None
        self.is_processing = False
        self.ui.pushButton_Send.setIcon(self.start_icon)
        self.ui.pushButton_Send.setEnabled(True)
        self.ui.progressBar.setValue(0)

    # --- THAY ĐỔI: Hàm shutdown_server sẽ bắt đầu hoạt cảnh ---
    def shutdown_server(self):
        if not self.httpd:
            return

        # Bắt đầu hoạt cảnh thay vì ghi log tĩnh
        self.log("") # Thêm một mục trống để bắt đầu animation
        self.animated_log_item = self.ui.listWidget_Log.item(self.ui.listWidget_Log.count() - 1)
        self.animation_index = 0
        self.animation_timer.start()

        self.ui.pushButton_Send.setEnabled(False)

        def shutdown_task():
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception as e:
                self.log(f"❌ Lỗi khi tắt server: {e}")
            finally:
                self.server_shutdown_finished.emit()

        threading.Thread(target=shutdown_task, daemon=True).start()

        def dummy_request_task():
            try:
                urllib.request.urlopen(f"http://{self.local_ip}:{PORT}", timeout=1)
            except Exception:
                pass

        threading.Thread(target=dummy_request_task, daemon=True).start()

    def log(self, message):
        # (Không có thay đổi ở hàm này)
        self.ui.listWidget_Log.addItem(message)
        self.ui.listWidget_Log.setCurrentRow(-1)
        QTimer.singleShot(0, self.ui.listWidget_Log.scrollToBottom)

    def toggle_destination_enabled(self):
        # (Không có thay đổi ở hàm này)
        enabled = self.ui.checkBox_Convert.isChecked()
        self.ui.lineEdit_Destination.setEnabled(enabled)
        self.ui.pushButton_2.setEnabled(enabled)

    def select_source_folder(self):
        # (Không có thay đổi ở hàm này)
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục nguồn")
        if folder:
            self.ui.lineEdit_SourceFolder.setText(folder)

    def select_destination_folder(self):
        # (Không có thay đổi ở hàm này)
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chia sẻ")
        if folder:
            self.ui.lineEdit_Destination.setText(folder)

    def convert_epub_to_kepub(self, source_folder, output_folder):
        # (Không có thay đổi ở hàm này)
        if not os.path.exists(KEPUBIFY_PATH):
            QMessageBox.critical(self, "Thiếu file", f"Không tìm thấy kepubify-windows-64bit.exe trong thư mục:\n{SCRIPT_DIR}\nVui lòng tải và đặt vào đúng thư mục.")
            return False

        files = [f for f in os.listdir(source_folder) if f.endswith(".epub") and not f.endswith(".kepub.epub")]
        total = len(files)
        
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
            
        for i, filename in enumerate(files, start=1):
            epub_path = os.path.join(source_folder, filename)
            output_file = os.path.join(output_folder, filename.replace(".epub", ".kepub.epub"))
            self.log(f"🔄 Converting: {filename}")
            subprocess.run([KEPUBIFY_PATH, epub_path, "--output", output_file], creationflags=creation_flags)
            self.ui.progressBar.setValue(int(i / total * 100))
            
        self.log("✅ Hoàn tất chuyển đổi.")
        return True

    def start_server(self, directory):
        # (Không có thay đổi ở hàm này)
        if self.httpd:
            self.log("⚠️ Server đã đang chạy rồi.")
            return
            
        os.chdir(directory)
        self.log(f"📁 Thư mục chia sẻ: {directory}")
        self.httpd = socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.log(f"✅ Server running: http://{self.local_ip}:{PORT}")
        self.is_processing = True
        self.ui.pushButton_Send.setIcon(self.stop_icon)

    def run(self):
        # (Không có thay đổi ở hàm này)
        self.show()

    def start_process(self):
        # (Không có thay đổi ở hàm này)
        self.is_processing = True
        self.ui.pushButton_Send.setIcon(self.stop_icon)
        
        self.log("⏳ Bắt đầu xử lý, vui lòng chờ...")
        
        source_folder = self.ui.lineEdit_SourceFolder.text()
        destination_folder = self.ui.lineEdit_Destination.text()
        convert_enabled = self.ui.checkBox_Convert.isChecked()

        if not os.path.exists(source_folder):
            self.log("❌ Thư mục nguồn không tồn tại.")
            self.is_processing = False
            self.ui.pushButton_Send.setIcon(self.start_icon)
            return

        if convert_enabled and not os.path.exists(destination_folder):
            self.log("❌ Thư mục đích không tồn tại.")
            self.is_processing = False
            self.ui.pushButton_Send.setIcon(self.start_icon)
            return

        server_folder = destination_folder if convert_enabled else source_folder

        def task():
            self.ui.progressBar.setValue(0)
            if convert_enabled:
                success = self.convert_epub_to_kepub(source_folder, destination_folder)
                if not success:
                    self.is_processing = False
                    self.ui.pushButton_Send.setIcon(self.start_icon)
                    return
            self.ui.progressBar.setValue(100)
            self.log("✅ Sẵn sàng chia sẻ.")
            self.log(f"🚀 Truy cập: http://{self.local_ip}:{PORT}")
            self.start_server(server_folder)

        threading.Thread(target=task, daemon=True).start()

if __name__ == '__main__':
    # (Không có thay đổi ở đây)
    app = QApplication(sys.argv)
    window = SendToKobo()
    window.run()
    sys.exit(app.exec())