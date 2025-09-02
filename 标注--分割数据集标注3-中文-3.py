import sys
import cv2
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
                             QSlider, QFileDialog, QWidget, QSizePolicy, QScrollArea, QMessageBox, QButtonGroup)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap, QPainter

'''
根据自己显示屏的分辨率，在 setFixedSize 处调节合适的窗口大小
标注后在 实例分割可视化1.py 程序中输入地址运行，生成可视化结果图，看是否标注有误，
个别有误的图片挑选出来，重新放到一个文件夹，再次标注
'''

class ImageLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.setScaledContents(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.drawing = False
        self.brush_size = 1
        self.mask_color = (0, 0, 255)
        self.contour_points = []
        self.contour_id = 0
        self.img = None
        self.scaled_img = None
        self.txt_file_path = None
        self.overlay = None
        self.scale_factor = 1.0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(30)

    def set_image(self, img_path):
        img_path = img_path.replace('\\', '/')
        self.img_path = img_path
        if not os.path.exists(img_path):
            print(f"File does not exist: {img_path}")
            return
        self.img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if self.img is None:
            print(f"Error: Cannot read image from {img_path}")
            return
        self.overlay = self.img.copy()
        self.txt_file_path = os.path.splitext(img_path)[0] + '.txt'
        with open(self.txt_file_path, 'w') as f:
            pass
        self.update_image()

    def update_image(self):
        if self.img is not None:
            self.scaled_img = self.scale_image(self.img)
            self.update_display()

    def scale_image(self, image):
        label_width = self.width()
        label_height = self.height()
        img_height, img_width = image.shape[:2]
        self.scale_factor = min(label_width / img_width, label_height / img_height)
        new_width = int(img_width * self.scale_factor)
        new_height = int(img_height * self.scale_factor)
        scaled_img = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        return scaled_img

    def update_display(self):
        if self.scaled_img is not None:
            display_img = self.scaled_img.copy()
            overlay_scaled = self.scale_image(self.overlay)
            height, width, channel = display_img.shape
            bytes_per_line = 3 * width
            q_img = QImage(display_img.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            q_overlay = QImage(overlay_scaled.data, overlay_scaled.shape[1], overlay_scaled.shape[0],
                                bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            painter = QPainter()
            painter.begin(q_img)
            painter.drawImage(0, 0, q_overlay)
            painter.end()
            self.setPixmap(QPixmap.fromImage(q_img))
            self.setAlignment(Qt.AlignCenter)

    def save_contour_to_file(self):
        height, width = self.img.shape[:2]
        with open(self.txt_file_path, 'a') as f:
            f.write(f"{self.contour_id} " + " ".join(
                [f"{x / width:.6f} {y / height:.6f}" for x, y in self.contour_points]) + "\n")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.contour_points = [self.convert_to_original_coords(event.pos())]

    def mouseMoveEvent(self, event):
        if self.drawing:
            point = self.convert_to_original_coords(event.pos())
            self.contour_points.append(point)
            self.draw_points()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drawing = False
            self.save_contour_to_file()

    def convert_to_original_coords(self, point):
        if self.scaled_img is not None:
            scaled_height, scaled_width = self.scaled_img.shape[:2]
            scale_x = self.img.shape[1] / scaled_width
            scale_y = self.img.shape[0] / scaled_height
            offset_x = (self.width() - scaled_width) / 2
            offset_y = (self.height() - scaled_height) / 2
            orig_x = (point.x() - offset_x) * scale_x
            orig_y = (point.y() - offset_y) * scale_y
            return int(orig_x), int(orig_y)
        return point.x(), point.y()

    def draw_points(self):
        for point in self.contour_points:
            cv2.circle(self.overlay, point, int(self.brush_size / self.scale_factor), self.mask_color, -1)

    def resizeEvent(self, event):
        self.update_image()
        super().resizeEvent(event)

    def reset_annotation(self):
        if self.img is not None:
            self.overlay = self.img.copy()
            with open(self.txt_file_path, 'w') as f:
                pass
            self.update_image()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # self.setFixedSize(int(1920), int(1080))  # 窗口大小放大1.5倍
        # self.setFixedSize(int(1536 * 1.5), int(864 * 1.5))  # 窗口大小放大1.5倍
        self.setFixedSize(int(1724), int(2500))  # 窗口大小放大1.5倍

        self.image_label = ImageLabel()
        self.image_paths = []
        self.current_image_index = 0

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)

        self.image_name_label = QLabel("图片: ")
        self.image_name_label.setAlignment(Qt.AlignCenter)

        # 标签按钮布局
        self.tag_buttons_layout = QHBoxLayout()
        self.create_tag_buttons()

        open_folder_button = QPushButton("打开文件夹")
        open_folder_button.clicked.connect(self.open_folder)

        prev_button = QPushButton("上一张")
        prev_button.clicked.connect(self.show_previous_image)

        next_button = QPushButton("下一张")
        next_button.clicked.connect(self.show_next_image)

        reset_button = QPushButton("重置")
        reset_button.clicked.connect(self.reset_current_image)

        # 底部工具布局
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(open_folder_button)
        controls_layout.addWidget(prev_button)
        controls_layout.addWidget(next_button)
        controls_layout.addWidget(reset_button)

        layout = QVBoxLayout()
        layout.addWidget(self.image_name_label)
        layout.addLayout(self.tag_buttons_layout)
        layout.addWidget(scroll_area)
        layout.addLayout(controls_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def create_tag_buttons(self):
        # 标签定义
        # self.labels = [
        #     ("0.mole", (255, 0, 0)),
        #     ("1.spot", (0, 255, 0)),
        #     ("2.scars", (0, 0, 255)),
        #     ("3.fat", (255, 255, 0)),
        #     ("4.acne1", (0, 255, 255)),
        #     ("5.acne2", (255, 0, 255)),
        #     ("6.allergy", (128, 128, 0)),
        #     ("7.pores", (128, 0, 128)),
        #     ("8.oil", (0, 128, 128)),
        # ]

        self.labels = [
            ("0.脸部", (128, 0, 0)),
            ("1.鼻子", (255, 0, 0)),
            ("2.眼袋", (0, 255, 0)),
            ("3.痣", (0, 0, 255)),
            ("4.斑点", (255, 255, 0)),
            ("5.浅痘", (0, 255, 255)),
            ("6.红痘", (255, 0, 255)),
            ("7.过敏", (128, 128, 0)),
            ("8.粗糙", (128, 0, 128)),
            ("9.油", (0, 128, 128)),
        ]

        # 按钮组
        self.button_group = QButtonGroup()
        for idx, (label_text, color) in enumerate(self.labels):
            button = QPushButton(label_text)
            button.setCheckable(True)
            button.clicked.connect(lambda _, index=idx, col=color: self.set_tag(index, col))  # 改为 col=color
            self.button_group.addButton(button, idx)
            self.tag_buttons_layout.addWidget(button)

        # 默认选择第一个标签
        self.button_group.buttons()[0].setChecked(True)
        self.set_tag(0, self.labels[0][1])

    def set_tag(self, index, color):
        self.image_label.contour_id = index
        self.image_label.mask_color = color

    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "打开图片文件夹", "")
        if folder_path:
            folder_path = folder_path.replace('\\', '/')
            self.image_paths = sorted(
                [os.path.join(folder_path, f).replace('\\', '/') for f in os.listdir(folder_path)
                 if f.lower().endswith(('.png', '.jpg', '.bmp'))]
            )
            self.current_image_index = 0
            if self.image_paths:
                self.show_image()

    def show_image(self):
        if self.image_paths:
            img_path = self.image_paths[self.current_image_index]
            self.image_label.set_image(img_path)
            self.image_name_label.setText(f"图片: {os.path.basename(img_path)}")

    def show_previous_image(self):
        if self.image_paths:
            self.current_image_index = (self.current_image_index - 1) % len(self.image_paths)
            self.show_image()

    def show_next_image(self):
        if self.image_paths:
            if self.current_image_index == len(self.image_paths) - 1:
                user_choice = self.show_completion_message()
                if user_choice == QMessageBox.No:
                    self.close()
                    return
                else:
                    self.current_image_index = 0  # 重置为第一张图片
            else:
                self.current_image_index += 1
            self.show_image()

    def show_completion_message(self):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setText("标注已完成！")
        msg_box.setWindowTitle("提示")
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        no_button = msg_box.button(QMessageBox.No)
        no_button.setText("退出")
        return msg_box.exec_()

    def reset_current_image(self):
        self.image_label.reset_annotation()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
