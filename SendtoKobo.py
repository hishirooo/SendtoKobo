import os
import subprocess
import threading
import socket
import http.server
import socketserver
import urllib.request
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox
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
                continue  # skip non-ebook files
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
    def __init__(self):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # Connect buttons
        self.ui.pushButton_SourceFolder.clicked.connect(self.select_source_folder)
        self.ui.pushButton_2.clicked.connect(self.select_destination_folder)
        self.ui.pushButton_Send.clicked.connect(self.start_process)
        self.ui.checkBox_Convert.stateChanged.connect(self.toggle_destination_enabled)

        self.local_ip = get_local_ip()
        self.toggle_destination_enabled()  # Initialize state
        self.httpd = None
        self.server_thread = None
        self.log(f"🚀 Gợi ý: Nhập địa chỉ IP trên Kobo/thiết bị: http://{self.local_ip}:{PORT}")


    def closeEvent(self, event):
        self.log("🛑 Yêu cầu thoát chương trình, chuẩn bị tắt server...")
        reply = QMessageBox.question(self, 'Thoát chương trình',
                                     "Bạn có chắc muốn thoát và tắt chia sẻ?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.httpd:
                self.log("🛑 Đang tắt server...")
                def shutdown_server():
                    try:
                        self.httpd.shutdown()
                        self.httpd.server_close()
                        self.log("✅ Server đã được tắt.")
                    except Exception as e:
                        self.log(f"❌ Lỗi khi tắt server: {e}")
                shutdown_thread = threading.Thread(target=shutdown_server)
                shutdown_thread.start()
                try:
                    urllib.request.urlopen(f"http://localhost:{PORT}", timeout=1)
                except:
                    pass
                shutdown_thread.join()
            event.accept()
        else:
            event.ignore()

    def log(self, message):
        self.ui.listWidget_Log.addItem(message)
        self.ui.listWidget_Log.setCurrentRow(-1)
        QTimer.singleShot(0, self.ui.listWidget_Log.scrollToBottom)

    def toggle_destination_enabled(self):
        enabled = self.ui.checkBox_Convert.isChecked()
        self.ui.lineEdit_Destination.setEnabled(enabled)
        self.ui.pushButton_2.setEnabled(enabled)

    def select_source_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục nguồn")
        if folder:
            self.ui.lineEdit_SourceFolder.setText(folder)

    def select_destination_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục chia sẻ")
        if folder:
            self.ui.lineEdit_Destination.setText(folder)

    def convert_epub_to_kepub(self, source_folder, output_folder):
        if not os.path.exists(KEPUBIFY_PATH):
            QMessageBox.critical(self, "Thiếu file", f"Không tìm thấy kepubify-windows-64bit.exe trong thư mục:\n{SCRIPT_DIR}\nVui lòng tải và đặt vào đúng thư mục.")
            return False

        files = [f for f in os.listdir(source_folder) if f.endswith(".epub") and not f.endswith(".kepub.epub")]
        total = len(files)
        for i, filename in enumerate(files, start=1):
            epub_path = os.path.join(source_folder, filename)
            output_file = os.path.join(output_folder, filename.replace(".epub", ".kepub.epub"))
            self.log(f"🔄 Converting: {filename}")
            subprocess.run([KEPUBIFY_PATH, epub_path, "--output", output_file])
            self.ui.progressBar.setValue(int(i / total * 100))
        self.log("✅ Hoàn tất chuyển đổi.")
        return True

    def start_server(self, directory):
        os.chdir(directory)
        self.log(f"📁 Thư mục chia sẻ: {directory}")
        self.httpd = socketserver.TCPServer(("", PORT), CustomHTTPRequestHandler)
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()
        self.log(f"✅ Server running: http://{self.local_ip}:{PORT}")

    def run(self):
        self.show()

    def start_process(self):
        source_folder = self.ui.lineEdit_SourceFolder.text()
        destination_folder = self.ui.lineEdit_Destination.text()
        convert_enabled = self.ui.checkBox_Convert.isChecked()

        if not os.path.exists(source_folder):
            self.log("❌ Source folder không tồn tại.")
            return

        if convert_enabled and not os.path.exists(destination_folder):
            self.log("❌ Destination folder không tồn tại.")
            return

        server_folder = destination_folder if convert_enabled else source_folder

        def task():
            self.ui.progressBar.setValue(0)

            if convert_enabled:
                success = self.convert_epub_to_kepub(source_folder, destination_folder)
                if not success:
                    return

            self.ui.progressBar.setValue(100)
            self.log("✅ Sẵn sàng chia sẻ.")
            self.log(f"🚀 Truy cập: http://{self.local_ip}:{PORT}")
            self.start_server(server_folder)

        threading.Thread(target=task, daemon=True).start()

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    window = SendToKobo()
    window.run()
    sys.exit(app.exec())
