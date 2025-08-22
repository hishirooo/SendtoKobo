import os
import subprocess
import threading
import socket
import http.server
import socketserver
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox
from ui_SendFile import Ui_Form

PORT = 8080
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEPUBIFY_PATH = os.path.join(SCRIPT_DIR, "kepubify-windows-64bit.exe")

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

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
        self.log(f"🚀 Gợi ý: Nhập địa chỉ IP trên Kobo/thiết bị: http://{self.local_ip}:{PORT}")

    def closeEvent(self, event):
        if self.httpd:
            self.httpd.shutdown()
            self.log("🛑 Đã tắt server.")
        event.accept()

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
        handler = http.server.SimpleHTTPRequestHandler
        self.httpd = socketserver.TCPServer(("", PORT), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.log(f"✅ Server running: http://{self.local_ip}:{PORT}")
        self.log(f"📁 Thư mục chia sẻ: {directory}")

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
