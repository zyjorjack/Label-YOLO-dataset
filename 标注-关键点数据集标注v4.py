import os
import sys
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QComboBox, QCheckBox, QScrollArea,
                             QGroupBox, QFileDialog, QMessageBox, QInputDialog, QDialog,
                             QShortcut, QListWidget, QListWidgetItem, QLineEdit)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QCursor, QKeySequence, QFont


class ImageDisplayWidget(QLabel):
    mouseMoved = pyqtSignal(QPoint)
    mouseClicked = pyqtSignal(QPoint)
    bboxClicked = pyqtSignal(int)  # 新增：点击标注框信号
    rightClicked = pyqtSignal()  # 新增右键点击信号

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: black;")
        self.setMouseTracking(True)

        self.image = None
        self.scaled_pixmap = None
        self.annotations = []
        self.class_names = []
        self.keypoint_names = []
        self.drawing_mode = False
        self.bbox_start = None
        self.mouse_pos = None
        self.highlighted_bbox = -1  # 新增：高亮显示的标注框索引

    def set_image(self, pixmap):
        self.image = pixmap
        self.update_display()

    def set_annotations(self, annotations, class_names, keypoint_names):
        self.annotations = annotations
        self.class_names = class_names
        self.keypoint_names = keypoint_names
        self.update()

    def set_drawing_mode(self, enabled):
        self.drawing_mode = enabled
        if enabled:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def set_bbox_start(self, start):
        self.bbox_start = start
        self.update()

    def set_highlighted_bbox(self, index):
        """设置要高亮显示的标注框索引"""
        self.highlighted_bbox = index
        self.update()

    def get_image_position(self, pos):
        if not self.image or not self.scaled_pixmap:
            return None

        label_size = self.size()
        pixmap_size = self.scaled_pixmap.size()
        offset_x = (label_size.width() - pixmap_size.width()) // 2
        offset_y = (label_size.height() - pixmap_size.height()) // 2

        img_x = pos.x() - offset_x
        img_y = pos.y() - offset_y

        if 0 <= img_x < pixmap_size.width() and 0 <= img_y < pixmap_size.height():
            scale_x = self.image.width() / pixmap_size.width()
            scale_y = self.image.height() / pixmap_size.height()
            return (img_x * scale_x, img_y * scale_y)
        return None

    def update_display(self):
        if self.image:
            self.scaled_pixmap = self.image.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(self.scaled_pixmap)

    def resizeEvent(self, event):
        self.update_display()

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.pos()
        self.mouseMoved.emit(event.pos())
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.rightClicked.emit()  # 发射信号
            return

        if event.button() == Qt.RightButton and self.drawing_mode:
            return

        # 新增：检测是否点击了标注框
        if event.button() == Qt.LeftButton and not self.drawing_mode and self.scaled_pixmap:
            img_pos = self.get_image_position(event.pos())
            if img_pos:
                x, y = img_pos
                img_w, img_h = self.image.width(), self.image.height()

                # 检查是否点击了某个标注框
                for i, ann in enumerate(self.annotations):
                    x_center, y_center, width, height = ann["bbox"]
                    x1 = (x_center - width / 2) * img_w
                    y1 = (y_center - height / 2) * img_h
                    x2 = (x_center + width / 2) * img_w
                    y2 = (y_center + height / 2) * img_h

                    if x1 <= x <= x2 and y1 <= y <= y2:
                        self.bboxClicked.emit(i)  # 发射信号，传递标注框索引
                        return

        self.mouseClicked.emit(event.pos())

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.image:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制十字准线
        if self.drawing_mode and self.mouse_pos:
            pen = QPen(QColor(255, 255, 255, 150), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(0, self.mouse_pos.y(), self.width(), self.mouse_pos.y())
            painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.height())

            if self.bbox_start:
                img_pos = self.get_image_position(self.mouse_pos)
                if img_pos:
                    img_w, img_h = self.image.width(), self.image.height()
                    start_x = self.bbox_start[0] / img_w * self.scaled_pixmap.width()
                    start_y = self.bbox_start[1] / img_h * self.scaled_pixmap.height()

                    label_size = self.size()
                    pixmap_size = self.scaled_pixmap.size()
                    offset_x = (label_size.width() - pixmap_size.width()) // 2
                    offset_y = (label_size.height() - pixmap_size.height()) // 2

                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(
                        int(offset_x + start_x),
                        int(offset_y + start_y),
                        int(self.mouse_pos.x() - offset_x - start_x),
                        int(self.mouse_pos.y() - offset_y - start_y)
                    )

        # 绘制标注
        if self.scaled_pixmap and self.annotations:
            label_size = self.size()
            pixmap_size = self.scaled_pixmap.size()
            offset_x = (label_size.width() - pixmap_size.width()) // 2
            offset_y = (label_size.height() - pixmap_size.height()) // 2
            painter.translate(offset_x, offset_y)

            img_w, img_h = self.image.width(), self.image.height()
            scale_x = pixmap_size.width() / img_w
            scale_y = pixmap_size.height() / img_h

            for i, ann in enumerate(self.annotations):
                # 边界框
                x_center, y_center, width, height = ann["bbox"]
                x1 = (x_center - width / 2) * pixmap_size.width()
                y1 = (y_center - height / 2) * pixmap_size.height()
                x2 = (x_center + width / 2) * pixmap_size.width()
                y2 = (y_center + height / 2) * pixmap_size.height()

                color = QColor(0, 255, 0)
                if ann["class_id"] < len(self.class_names):
                    hue = (ann["class_id"] * 60) % 360
                    color.setHsv(hue, 255, 255)

                # 新增：如果是高亮的标注框，使用更粗的线条和不同颜色
                if i == self.highlighted_bbox:
                    pen = QPen(QColor(255, 255, 0), 4)  # 黄色粗边框
                    painter.setPen(pen)
                    painter.setBrush(QColor(255, 255, 0, 50))  # 半透明黄色填充
                else:
                    pen = QPen(color, 2)
                    painter.setPen(pen)
                    painter.setBrush(Qt.NoBrush)

                painter.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))

                # 绘制类别标签
                class_name = self.class_names[ann["class_id"]] if ann["class_id"] < len(self.class_names) else str(
                    ann["class_id"])
                painter.drawText(int(x1) + 5, int(y1) + 15, class_name)

                # 关键点
                for kp_idx, (x, y, v) in enumerate(ann["keypoints"]):
                    if v > 0:
                        px = x * pixmap_size.width()
                        py = y * pixmap_size.height()

                        # 安全获取关键点名称
                        kp_name = f"关键点{kp_idx + 1}"
                        if kp_idx < len(self.keypoint_names):
                            kp_name = self.keypoint_names[kp_idx]

                        if v == 2:  # 可见
                            painter.setBrush(QColor(255, 0, 0))
                        else:  # 遮挡
                            painter.setBrush(QColor(255, 165, 0))

                        painter.drawEllipse(int(px) - 5, int(py) - 5, 10, 10)

                        if kp_idx < len(self.keypoint_names):
                            painter.drawText(int(px) + 10, int(py) + 5, str(kp_idx + 1))  # 只显示数字

            painter.end()


class ImageListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                background-color: white;
            }
            QListWidget::item {
                padding: 2px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #d8e6f3;
                color: black;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
        """)

        # 预加载的项数
        self.preload_count = 50
        # 当前加载的范围
        self.loaded_start = 0
        self.loaded_end = 0

        # 连接滚动事件
        self.verticalScrollBar().valueChanged.connect(self.handle_scroll)

    def set_items(self, items):
        """设置所有项目，但不立即加载"""
        self.clear()
        self.items = items
        self.total_count = len(items)
        self.loaded_start = 0
        self.loaded_end = 0
        self.load_items(0, min(self.preload_count, self.total_count))

    def load_items(self, start, end):
        """加载指定范围内的项目"""
        if start >= end or start >= self.total_count:
            return

        # 确保范围有效
        start = max(0, start)
        end = min(self.total_count, end)

        # 添加新项目
        for i in range(start, end):
            item = QListWidgetItem(self.items[i])
            self.addItem(item)

        self.loaded_start = min(self.loaded_start, start) if self.loaded_start != 0 else start
        self.loaded_end = max(self.loaded_end, end)

    def handle_scroll(self, value):
        """处理滚动事件，动态加载项目"""
        scroll_bar = self.verticalScrollBar()
        max_value = scroll_bar.maximum()
        current_pos = value

        # 如果接近底部，加载更多项目
        if current_pos > max_value * 0.8 and self.loaded_end < self.total_count:
            new_end = min(self.loaded_end + self.preload_count, self.total_count)
            self.load_items(self.loaded_end, new_end)

        # 如果接近顶部，加载前面的项目
        elif current_pos < max_value * 0.2 and self.loaded_start > 0:
            new_start = max(0, self.loaded_start - self.preload_count)
            self.load_items(new_start, self.loaded_start)
            # 调整滚动位置以保持视觉连续性
            scroll_bar.setValue(value + (self.loaded_start - new_start) * self.sizeHintForRow(0))
            self.loaded_start = new_start

    def scroll_to_item(self, index):
        """滚动到指定索引的项目"""
        if index < 0 or index >= self.total_count:
            return

        # 如果项目在已加载范围内，直接滚动到它
        if self.loaded_start <= index < self.loaded_end:
            self.setCurrentRow(index - self.loaded_start)
            self.scrollToItem(self.item(index - self.loaded_start), QListWidget.PositionAtTop)
        else:
            # 否则加载包含该项目的区域
            start = max(0, index - self.preload_count // 2)
            end = min(self.total_count, index + self.preload_count // 2)
            self.load_items(start, end)
            self.setCurrentRow(index - start)
            self.scrollToItem(self.item(index - start), QListWidget.PositionAtTop)


class KeyPointLabeler(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("关键点标注工具")
        self.setGeometry(100, 100, 1400, 800)  # 增加窗口宽度以适应文件列表

        # 初始化变量
        self.image_dir = ""
        self.image_files = []
        self.current_image_index = -1
        self.current_image = None
        self.current_image_path = ""
        self.annotations = []
        self.drawing_bbox = False
        self.bbox_start = None
        self.bbox_end = None
        self.undo_stack = []
        self.adding_keypoints = False
        self.current_annotation_idx = -1
        self.temp_keypoints = []
        self.visible_annotations = set()
        self.highlighted_annotation = -1  # 新增：当前高亮的标注索引

        # 配置
        # self.class_names = ["people"]
        self.class_names = ["standing", "sidelying", "prone"]
        self.keypoint_names = [f"关键点{i + 1}" for i in range(9)]

        # 创建UI
        self.init_ui()
        self.setup_shortcuts()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 左侧面板 - 重新组织布局
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # 上部按钮区域
        top_buttons = QHBoxLayout()
        self.btn_open = QPushButton("打开文件夹")
        self.btn_open.clicked.connect(self.open_folder)
        top_buttons.addWidget(self.btn_open)

        self.btn_prev = QPushButton("上一张")
        self.btn_prev.clicked.connect(self.prev_image)
        top_buttons.addWidget(self.btn_prev)

        self.btn_next = QPushButton("下一张")
        self.btn_next.clicked.connect(self.next_image)
        top_buttons.addWidget(self.btn_next)
        left_layout.addLayout(top_buttons)

        # 图片信息
        self.lbl_image_info = QLabel("图片信息将显示在这里")
        left_layout.addWidget(self.lbl_image_info)

        # 删除按钮
        self.btn_delete_image = QPushButton("删除当前图片及标注(Ctrl+D)")
        self.btn_delete_image.clicked.connect(self.delete_current_image)
        left_layout.addWidget(self.btn_delete_image)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索图片...")
        self.search_box.textChanged.connect(self.filter_file_list)
        left_layout.addWidget(self.search_box)

        # 文件列表 - 现在放在下方，占据剩余空间
        self.file_list = ImageListWidget()
        self.file_list.itemClicked.connect(self.on_file_item_clicked)
        left_layout.addWidget(self.file_list, 1)  # 添加伸缩因子1使列表占据剩余空间

        main_layout.addWidget(left_panel, 2)  # 左侧区域占2份宽度

        # 中间图像显示区域
        center_panel = QVBoxLayout()
        self.image_display = ImageDisplayWidget()
        self.image_display.setMouseTracking(True)
        self.image_display.mouseMoved.connect(self.update_mouse_position)
        self.image_display.mouseClicked.connect(self.handle_image_click)
        self.image_display.bboxClicked.connect(self.highlight_annotation)
        center_panel.addWidget(self.image_display)
        main_layout.addLayout(center_panel, 5)  # 中间区域占5份宽度

        self.image_display.rightClicked.connect(self.cancel_current_action)

        # 右侧标注信息区域
        right_panel = QVBoxLayout()
        right_panel.setContentsMargins(5, 5, 5, 5)

        self.class_combo = QComboBox()
        self.class_combo.addItems(self.class_names)
        right_panel.addWidget(QLabel("当前类别:"))
        right_panel.addWidget(self.class_combo)

        self.btn_add_bbox = QPushButton("添加边界框 (快捷键1.2.3..)")
        self.btn_add_bbox.clicked.connect(self.start_bbox_drawing)
        right_panel.addWidget(self.btn_add_bbox)

        self.btn_undo = QPushButton("撤销 (Ctrl+Z)")
        self.btn_undo.clicked.connect(self.undo_action)
        right_panel.addWidget(self.btn_undo)

        self.btn_save = QPushButton("保存标注 (Ctrl+S)")
        self.btn_save.clicked.connect(self.save_annotations)
        right_panel.addWidget(self.btn_save)

        self.annotation_scroll = QScrollArea()
        self.annotation_scroll.setWidgetResizable(True)
        self.annotation_widget = QWidget()
        self.annotation_layout = QVBoxLayout()
        self.annotation_widget.setLayout(self.annotation_layout)
        self.annotation_scroll.setWidget(self.annotation_widget)
        right_panel.addWidget(self.annotation_scroll)
        main_layout.addLayout(right_panel, 3)  # 右侧区域占3份宽度

        self.status_bar = self.statusBar()
        self.lbl_mouse_pos = QLabel("鼠标位置: (0, 0)")
        self.status_bar.addPermanentWidget(self.lbl_mouse_pos)

    def filter_file_list(self):
        """根据搜索框内容过滤文件列表"""
        search_text = self.search_box.text().lower()
        if not search_text:
            # 如果没有搜索文本，显示所有文件
            self.file_list.set_items(self.image_files)
        else:
            # 过滤出包含搜索文本的文件名
            filtered_files = [f for f in self.image_files if search_text in f.lower()]
            self.file_list.set_items(filtered_files)

        # 如果当前图片在过滤后的列表中，高亮显示
        if self.current_image_index >= 0 and self.current_image_path:
            current_file = os.path.basename(self.current_image_path)
            try:
                idx = self.file_list.items.index(current_file)
                self.file_list.scroll_to_item(idx)
            except ValueError:
                pass

    def on_file_item_clicked(self, item):
        """点击文件列表中的项目时加载对应图片"""
        filename = item.text()
        try:
            idx = self.image_files.index(filename)
            if idx != self.current_image_index:
                self.save_annotations()
                self.current_image_index = idx
                self.load_image()
        except ValueError:
            pass

    def update_file_list_selection(self):
        """更新文件列表中的选中项以匹配当前图片"""
        if not self.image_files or self.current_image_index < 0:
            return

        # 确保文件列表已加载当前项目
        current_file = os.path.basename(self.current_image_path)
        try:
            idx = self.file_list.items.index(current_file)
            self.file_list.scroll_to_item(idx)

            # 清除之前的选择
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                item.setSelected(False)
                # 重置背景色
                item.setBackground(QColor(255, 255, 255))

            # 设置当前选中项的背景色
            current_item = self.file_list.item(idx - self.file_list.loaded_start)
            if current_item:
                current_item.setSelected(True)
                current_item.setBackground(QColor(200, 255, 200))  # 浅绿色背景
        except ValueError:
            pass

    def setup_shortcuts(self):
        # 类别选择快捷键
        for i in range(5):
            shortcut = QShortcut(Qt.Key_1 + i, self)
            shortcut.activated.connect(lambda idx=i: self.select_class_and_start_bbox(idx))

        # 新增：删除当前图片快捷键 (Ctrl+D)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.delete_current_image)

        # 新增：删除选中标注快捷键 (Delete键)
        QShortcut(QKeySequence(Qt.Key_Delete), self).activated.connect(self.delete_highlighted_annotation)

        # 原有快捷键
        QShortcut("Ctrl+Z", self).activated.connect(self.undo_action)
        QShortcut("Ctrl+S", self).activated.connect(self.save_annotations)

        # 新增：上一张/下一张图片快捷键 (左右方向键)
        QShortcut(Qt.Key_Left, self).activated.connect(self.prev_image)
        QShortcut(Qt.Key_Right, self).activated.connect(self.next_image)

        # 新增：跳转快捷键 (G键)
        QShortcut(Qt.Key_G, self).activated.connect(self.jump_to_image)

    def jump_to_image(self):
        """跳转到指定图片"""
        if not self.image_files:
            return

        current_num = self.current_image_index + 1
        total_num = len(self.image_files)

        num, ok = QInputDialog.getInt(
            self, "跳转到图片",
            f"输入图片序号 (1-{total_num}):",
            current_num, 1, total_num
        )

        if ok:
            idx = num - 1
            if idx != self.current_image_index:
                self.save_annotations()
                self.current_image_index = idx
                self.load_image()

    def highlight_annotation(self, ann_idx):
        """高亮显示指定的标注"""
        if 0 <= ann_idx < len(self.annotations):
            self.highlighted_annotation = ann_idx
            self.image_display.set_highlighted_bbox(ann_idx)

            # 滚动到对应的标注组
            scroll_widget = self.annotation_scroll.widget()
            if scroll_widget:
                target_widget = scroll_widget.layout().itemAt(len(self.annotations) - ann_idx - 1).widget()
                if target_widget:
                    # 设置高亮背景色
                    for i in range(self.annotation_layout.count()):
                        item = self.annotation_layout.itemAt(i)
                        if item.widget():
                            item.widget().setStyleSheet("")

                    target_widget.setStyleSheet("QGroupBox { background-color: #FFFFA0; }")

                    # 滚动到目标位置
                    scroll_bar = self.annotation_scroll.verticalScrollBar()
                    scroll_bar.setValue(target_widget.y())

    def delete_highlighted_annotation(self):
        """删除当前高亮的标注"""
        if self.highlighted_annotation != -1:
            self.delete_annotation(self.highlighted_annotation)
            self.highlighted_annotation = -1

    def delete_current_image(self):
        """删除当前图片及其标注文件"""
        if not self.current_image_path:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除当前图片及其标注文件吗？\n{os.path.basename(self.current_image_path)}",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 删除图片文件
                os.remove(self.current_image_path)

                # 删除对应的标注文件
                txt_path = os.path.splitext(self.current_image_path)[0] + ".txt"
                if os.path.exists(txt_path):
                    os.remove(txt_path)

                # 从文件列表中移除
                del self.image_files[self.current_image_index]
                self.file_list.set_items(self.image_files)  # 更新文件列表

                # 加载下一张或上一张图片
                if self.current_image_index >= len(self.image_files):
                    self.current_image_index = len(self.image_files) - 1

                if len(self.image_files) > 0:
                    self.load_image()
                else:
                    # 没有更多图片了
                    self.current_image = None
                    self.current_image_path = ""
                    self.image_display.set_image(None)
                    self.lbl_image_info.setText("没有图片")
                    self.annotations = []
                    self.update_annotation_display()
                    self.update_display()

            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除文件失败: {e}")

    def update_mouse_position(self, pos):
        if self.current_image:
            img_pos = self.image_display.get_image_position(pos)
            if img_pos:
                x, y = img_pos
                self.lbl_mouse_pos.setText(f"鼠标位置: ({int(x)}, {int(y)})")

    def select_class_and_start_bbox(self, class_idx):
        if 0 <= class_idx < len(self.class_names):
            self.class_combo.setCurrentIndex(class_idx)
            self.start_bbox_drawing()

    def cancel_current_action(self):

        # 取消边界框绘制
        if self.drawing_bbox:
            self.drawing_bbox = False
            self.bbox_start = None
            self.bbox_end = None
            self.status_bar.showMessage("已取消绘制边界框", 2000)
            print("Canceled bbox drawing")  # 调试输出

        # 取消关键点添加
        if self.adding_keypoints:
            self.adding_keypoints = False
            self.current_annotation_idx = -1
            self.temp_keypoints = []
            self.status_bar.showMessage("已取消添加关键点", 2000)
            print("Canceled keypoints adding")  # 调试输出

        # 强制重置显示模式
        self.image_display.set_drawing_mode(False)
        self.image_display.setCursor(Qt.ArrowCursor)
        self.update_display()

        # 如果没有正在进行的操作
        if not self.drawing_bbox and not self.adding_keypoints:
            self.status_bar.showMessage("当前没有可取消的操作", 2000)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if folder:
            self.image_dir = folder
            self.image_files = [f for f in os.listdir(folder)
                                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))]
            self.image_files.sort()

            if self.image_files:
                # 初始化文件列表
                self.file_list.set_items(self.image_files)

                self.current_image_index = 0
                self.load_image()
            else:
                QMessageBox.warning(self, "警告", "文件夹中没有图片文件")

    def load_image(self):
        if 0 <= self.current_image_index < len(self.image_files):
            # 重置标注状态
            self.drawing_bbox = False
            self.adding_keypoints = False
            self.current_annotation_idx = -1
            self.temp_keypoints = []
            self.bbox_start = None
            self.bbox_end = None
            self.image_display.set_drawing_mode(False)

            self.current_image_path = os.path.join(self.image_dir, self.image_files[self.current_image_index])
            pixmap = QPixmap(self.current_image_path)

            if pixmap.isNull():
                QMessageBox.warning(self, "错误", f"无法加载图片: {self.current_image_path}")
                return

            self.current_image = pixmap
            self.image_display.set_image(pixmap)
            self.load_annotations()
            self.update_ui_state()
            self.lbl_image_info.setText(
                f"图片 {self.current_image_index + 1}/{len(self.image_files)}: {self.image_files[self.current_image_index]}")

            # 更新文件列表选中状态
            self.update_file_list_selection()

    def update_ui_state(self):
        self.btn_prev.setEnabled(self.current_image_index > 0)
        self.btn_next.setEnabled(self.current_image_index < len(self.image_files) - 1)

    def load_annotations(self):
        self.annotations = []
        self.visible_annotations = set()
        txt_path = os.path.splitext(self.current_image_path)[0] + ".txt"

        if os.path.exists(txt_path):
            try:
                with open(txt_path, "r", encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:  # 跳过空行
                            continue

                        parts = line.split()
                        if len(parts) < 5:  # 至少需要类别ID和bbox
                            print(f"警告: 第{line_num}行格式不正确 - 需要至少5个参数，实际得到{len(parts)}个")
                            continue

                        try:
                            class_id = int(parts[0])
                            bbox = list(map(float, parts[1:5]))
                            # 验证bbox值是否在合理范围内
                            if not (0 <= bbox[0] <= 1 and 0 <= bbox[1] <= 1 and
                                    0 <= bbox[2] <= 1 and 0 <= bbox[3] <= 1):
                                print(f"警告: 第{line_num}行bbox值超出0-1范围 - {bbox}")
                                continue

                            # 解析关键点 (确保有9个关键点)
                            keypoints = []
                            for i in range(5, min(5 + 9 * 3, len(parts)), 3):
                                if i + 2 < len(parts):
                                    x = float(parts[i])
                                    y = float(parts[i + 1])
                                    v = int(parts[i + 2])
                                    # 验证关键点值
                                    if not (0 <= x <= 1 and 0 <= y <= 1 and v in (0, 1, 2)):
                                        print(f"警告: 第{line_num}行关键点值无效 - x:{x}, y:{y}, v:{v}")
                                        x, y, v = 0, 0, 0  # 设为无效
                                    keypoints.append((x, y, v))  # 直接添加，不要else分支
                                else:
                                    keypoints.append((0, 0, 0))  # 只有数据不足时才补0

                            # 补全到9个关键点
                            while len(keypoints) < 9:
                                keypoints.append((0, 0, 0))

                            self.annotations.append({
                                "class_id": class_id,
                                "bbox": bbox,
                                "keypoints": keypoints
                            })
                            self.visible_annotations.add(len(self.annotations) - 1)

                        except ValueError as e:
                            print(f"错误: 第{line_num}行解析失败 - {str(e)}")
                            continue

            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载标注文件失败: {str(e)}")
                return

        self.update_annotation_display()
        self.update_display()

    def set_keypoint_visibility(self, ann_idx, kp_idx, visibility):
        """设置关键点可见性状态"""
        if 0 <= ann_idx < len(self.annotations) and 0 <= kp_idx < len(self.annotations[ann_idx]["keypoints"]):
            x, y, _ = self.annotations[ann_idx]["keypoints"][kp_idx]
            self.annotations[ann_idx]["keypoints"][kp_idx] = (x, y, visibility)
            self.update_display()

    def delete_keypoint(self, ann_idx, kp_idx):
        """删除关键点(实际上是设置为不可见)"""
        if 0 <= ann_idx < len(self.annotations) and 0 <= kp_idx < len(self.annotations[ann_idx]["keypoints"]):
            # 保存到撤销栈
            self.undo_stack.append(("delete_keypoint", ann_idx, kp_idx, self.annotations[ann_idx]["keypoints"][kp_idx]))

            # 将关键点设置为不可见
            x, y, _ = self.annotations[ann_idx]["keypoints"][kp_idx]
            self.annotations[ann_idx]["keypoints"][kp_idx] = (x, y, 0)

            self.update_annotation_display()
            self.update_display()

    def create_visibility_handler(self, ann_idx, kp_idx, visibility, checkbox):
        """创建可见性状态变更处理器"""

        def handler(checked):
            if checked:
                # 只有当复选框被选中时才更新状态
                self.set_keypoint_visibility(ann_idx, kp_idx, visibility)
                # 确保UI状态同步
                checkbox.setChecked(True)

        return handler

    def update_annotation_display(self):
        # 清除现有布局
        while self.annotation_layout.count():
            child = self.annotation_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 正向遍历标注，但插入到最前面，这样最新的会显示在最上面
        for i in range(len(self.annotations)):
            ann = self.annotations[i]
            group_box = QGroupBox(f"{self.class_names[ann['class_id']]}")

            # 设置高亮背景色
            if i == self.highlighted_annotation:
                group_box.setStyleSheet("QGroupBox { background-color: #FFFFA0; }")

            group_layout = QVBoxLayout()

            bbox_label = QLabel(
                f"边界框: x={ann['bbox'][0]:.4f}, y={ann['bbox'][1]:.4f}, "
                f"w={ann['bbox'][2]:.4f}, h={ann['bbox'][3]:.4f}"
            )
            group_layout.addWidget(bbox_label)

            chk_show_bbox = QCheckBox("显示边界框和关键点")
            chk_show_bbox.setChecked(i in self.visible_annotations)
            chk_show_bbox.stateChanged.connect(lambda state, idx=i: self.toggle_annotation_visibility(idx, state))
            group_layout.addWidget(chk_show_bbox)

            btn_add_keypoints = QPushButton("添加/编辑关键点")
            btn_add_keypoints.clicked.connect(lambda _, idx=i: self.start_adding_keypoints(idx))
            group_layout.addWidget(btn_add_keypoints)

            for kp_idx, (x, y, v) in enumerate(ann["keypoints"]):
                if v == 0 and x == 0 and y == 0:
                    continue

                # 安全获取关键点名称
                kp_name = f"关键点{kp_idx + 1}"  # 默认名称
                if kp_idx < len(self.keypoint_names):
                    kp_name = self.keypoint_names[kp_idx]

                kp_widget = QWidget()
                kp_layout = QHBoxLayout()
                kp_layout.setContentsMargins(0, 0, 0, 0)

                # 关键点基本信息
                kp_label = QLabel(f"{kp_idx + 1}. {kp_name}: ({x:.2f}, {y:.2f})")
                kp_layout.addWidget(kp_label, 1)

                # 可见性状态选择
                visibility_widget = QWidget()
                visibility_layout = QHBoxLayout()
                visibility_layout.setContentsMargins(0, 0, 0, 0)

                # 可见(v=2)单选按钮
                btn_visible = QCheckBox("可见")
                btn_visible.setChecked(v == 2)
                btn_visible.toggled.connect(self.create_visibility_handler(i, kp_idx, 2, btn_visible))
                visibility_layout.addWidget(btn_visible)

                # 遮挡(v=1)单选按钮
                btn_occluded = QCheckBox("遮挡")
                btn_occluded.setChecked(v == 1)
                btn_occluded.toggled.connect(self.create_visibility_handler(i, kp_idx, 1, btn_occluded))
                visibility_layout.addWidget(btn_occluded)

                # 设置互斥逻辑 - 只影响当前关键点的两个复选框
                btn_visible.toggled.connect(lambda checked, btn=btn_occluded: btn.setChecked(not checked))
                btn_occluded.toggled.connect(lambda checked, btn=btn_visible: btn.setChecked(not checked))

                visibility_widget.setLayout(visibility_layout)
                kp_layout.addWidget(visibility_widget)

                # 删除按钮
                btn_delete = QPushButton("删除")
                btn_delete.clicked.connect(lambda _, idx=i, kp=kp_idx: self.delete_keypoint(idx, kp))
                kp_layout.addWidget(btn_delete)

                kp_widget.setLayout(kp_layout)
                group_layout.addWidget(kp_widget)

            btn_edit_bbox = QPushButton("编辑边界框属性")
            btn_edit_bbox.clicked.connect(lambda _, idx=i: self.edit_bbox(idx))
            group_layout.addWidget(btn_edit_bbox)

            btn_delete = QPushButton("删除整个标注")
            btn_delete.clicked.connect(lambda _, idx=i: self.delete_annotation(idx))
            group_layout.addWidget(btn_delete)

            group_box.setLayout(group_layout)
            self.annotation_layout.insertWidget(0, group_box)

        self.annotation_layout.addStretch()

    def toggle_annotation_visibility(self, ann_idx, state):
        if state:
            self.visible_annotations.add(ann_idx)
        else:
            self.visible_annotations.discard(ann_idx)
        self.update_display()

    def toggle_keypoint_visibility(self, ann_idx, kp_idx, state):
        if 0 <= ann_idx < len(self.annotations) and 0 <= kp_idx < len(self.annotations[ann_idx]["keypoints"]):
            x, y, v = self.annotations[ann_idx]["keypoints"][kp_idx]
            new_v = 2 if state else 0
            self.annotations[ann_idx]["keypoints"][kp_idx] = (x, y, new_v)
            self.update_display()

    def update_display(self):
        visible_anns = [ann for i, ann in enumerate(self.annotations) if i in self.visible_annotations]
        self.image_display.set_annotations(visible_anns, self.class_names, self.keypoint_names)

    def start_bbox_drawing(self):
        # 先取消任何正在进行的操作
        self.cancel_current_action()

        # 开始新的绘制
        self.drawing_bbox = True
        self.bbox_start = None
        self.bbox_end = None
        self.image_display.set_drawing_mode(True)
        self.status_bar.showMessage("请点击边界框的左上角，右键取消", 2000)

    def start_adding_keypoints(self, ann_idx):
        # 先取消任何正在进行的操作
        self.cancel_current_action()
        print(f"Starting keypoints for annotation {ann_idx}")  # 调试输出

        """开始添加关键点"""
        self.adding_keypoints = True
        self.current_annotation_idx = ann_idx

        # 找出第一个不可见的关键点索引
        first_invisible = next((i for i, kp in enumerate(self.annotations[ann_idx]["keypoints"])
                                if kp[2] == 0), None)

        # 如果没有不可见的点(所有点都可见)，则不允许添加
        if first_invisible is None:
            QMessageBox.warning(self, "提示", "所有关键点都已标注")
            self.adding_keypoints = False
            return

        # 初始化临时关键点列表，只包含已存在的可见关键点
        self.temp_keypoints = [kp for kp in self.annotations[ann_idx]["keypoints"] if kp[2] > 0]

        self.image_display.set_drawing_mode(True)
        self.status_bar.showMessage(f"请添加关键点 {first_invisible + 1}，右键结束", 2000)

    def finish_bbox_drawing(self):
        if not self.bbox_start or not self.bbox_end:
            return

        x1, y1 = self.bbox_start
        x2, y2 = self.bbox_end

        # 确保x1,y1是左上角，x2,y2是右下角
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)

        # 计算归一化坐标
        img_w, img_h = self.current_image.width(), self.current_image.height()
        x_center = ((x1 + x2) / 2) / img_w
        y_center = ((y1 + y2) / 2) / img_h
        width = (x2 - x1) / img_w
        height = (y2 - y1) / img_h

        # 添加新标注
        new_ann_idx = len(self.annotations)
        self.annotations.append({
            "class_id": self.class_combo.currentIndex(),
            "bbox": [x_center, y_center, width, height],
            "keypoints": [(0, 0, 0)] * 9  # 初始化9个不可见关键点
        })
        self.visible_annotations.add(new_ann_idx)

        # 重置状态
        self.drawing_bbox = False
        self.bbox_start = None
        self.bbox_end = None
        self.image_display.set_drawing_mode(False)  # 确保退出十字模式
        self.image_display.setCursor(Qt.ArrowCursor)  # 强制恢复箭头光标

        # 更新显示
        self.update_annotation_display()
        self.update_display()

        # 添加到撤销栈
        self.undo_stack.append(("add_bbox", new_ann_idx))

        # 自动进入关键点标注模式
        self.start_adding_keypoints(new_ann_idx)

    def start_adding_keypoints(self, ann_idx):
        """开始添加关键点"""
        self.current_annotation_idx = ann_idx
        self.adding_keypoints = True

        # 找出第一个不可见的关键点索引
        first_invisible = next((i for i, kp in enumerate(self.annotations[ann_idx]["keypoints"])
                                if kp[2] == 0), None)

        # 如果没有不可见的点(所有点都可见)，则不允许添加
        if first_invisible is None:
            QMessageBox.warning(self, "提示", "所有关键点都已标注")
            self.adding_keypoints = False
            return

        # 初始化临时关键点列表，只包含已存在的可见关键点
        self.temp_keypoints = [kp for kp in self.annotations[ann_idx]["keypoints"] if kp[2] > 0]

        self.image_display.set_drawing_mode(True)
        self.status_bar.showMessage(f"请添加关键点 {first_invisible + 1}，右键或ESC结束", 2000)

    def finish_adding_keypoints(self):
        if not self.adding_keypoints:
            return

        try:
            # 检查当前标注索引是否有效
            if self.current_annotation_idx < 0 or self.current_annotation_idx >= len(self.annotations):
                QMessageBox.warning(self, "警告", "无效的标注索引，无法完成关键点添加")
                self.adding_keypoints = False
                self.current_annotation_idx = -1
                self.temp_keypoints = []
                self.image_display.set_drawing_mode(False)
                self.image_display.setCursor(Qt.ArrowCursor)  # 强制恢复箭头光标
                return

            # 确保不超过9个关键点
            if len(self.temp_keypoints) > 9:
                self.temp_keypoints = self.temp_keypoints[:9]
                QMessageBox.warning(self, "提示", "已自动截断为前9个关键点")

            # 确保有9个关键点，不足的补0
            while len(self.temp_keypoints) < 9:
                self.temp_keypoints.append((0, 0, 0))

            # 更新标注
            self.annotations[self.current_annotation_idx]["keypoints"] = self.temp_keypoints.copy()

            # 重置状态
            self.adding_keypoints = False
            self.current_annotation_idx = -1
            self.temp_keypoints = []

            self.drawing_bbox = False
            self.image_display.set_drawing_mode(False)  # 确保退出十字模式
            self.image_display.setCursor(Qt.ArrowCursor)  # 强制恢复箭头光标

            # 更新显示
            self.update_annotation_display()
            self.update_display()
            self.status_bar.showMessage("关键点标注完成", 2000)

        except Exception as e:
            QMessageBox.warning(self, "警告", f"完成关键点添加时出错: {str(e)}")
            # 重置状态以防万一
            self.adding_keypoints = False
            self.current_annotation_idx = -1
            self.temp_keypoints = []
            self.image_display.set_drawing_mode(False)
            self.image_display.setCursor(Qt.ArrowCursor)  # 强制恢复箭头光标

    def handle_image_click(self, pos):
        if not self.current_image:
            return

        # 右键点击取消当前操作
        if QApplication.mouseButtons() == Qt.RightButton:
            self.cancel_current_action()
            return

        img_pos = self.image_display.get_image_position(pos)
        if img_pos is None:
            return

        x, y = img_pos

        if self.drawing_bbox:
            if self.bbox_start is None:
                self.bbox_start = (x, y)
                self.status_bar.showMessage("请点击边界框的右下角，ESC取消", 2000)
                self.image_display.set_bbox_start(self.bbox_start)
            else:
                self.bbox_end = (x, y)
                self.finish_bbox_drawing()
        elif self.adding_keypoints:
            try:
                # 检查当前标注索引是否有效
                if self.current_annotation_idx == -1 or self.current_annotation_idx >= len(self.annotations):
                    QMessageBox.warning(self, "警告", "没有可用的标注或标注索引无效！")
                    self.finish_adding_keypoints()
                    return

                # 获取当前标注和边界框信息
                ann = self.annotations[self.current_annotation_idx]
                x_center, y_center, width, height = ann["bbox"]
                img_w, img_h = self.current_image.width(), self.current_image.height()

                # 计算边界框的实际坐标范围
                bbox_x1 = (x_center - width / 2) * img_w
                bbox_y1 = (y_center - height / 2) * img_h
                bbox_x2 = (x_center + width / 2) * img_w
                bbox_y2 = (y_center + height / 2) * img_h

                # 检查关键点是否在边界框内
                if x < bbox_x1 or x > bbox_x2 or y < bbox_y1 or y > bbox_y2:
                    QMessageBox.warning(self, "警告",
                                        f"关键点超出边界框范围！\n"
                                        f"边界框范围: x({bbox_x1:.1f}-{bbox_x2:.1f}), y({bbox_y1:.1f}-{bbox_y2:.1f})\n"
                                        f"当前点坐标: x={x:.1f}, y={y:.1f}")
                    return

                # 找出第一个不可见的关键点索引
                first_invisible = next((i for i, kp in enumerate(ann["keypoints"]) if kp[2] == 0), None)

                if first_invisible is None:
                    QMessageBox.warning(self, "提示", "所有关键点都已标注")
                    self.finish_adding_keypoints()
                    return

                # 添加关键点
                nx = x / img_w
                ny = y / img_h

                # 更新对应位置的关键点
                ann["keypoints"][first_invisible] = (nx, ny, 2)  # 默认可见

                # 更新临时关键点列表
                self.temp_keypoints = [kp for kp in ann["keypoints"] if kp[2] > 0]

                # 更新显示
                self.update_annotation_display()
                self.update_display()

                # 检查是否还有未标注的点
                next_invisible = next((i for i, kp in enumerate(ann["keypoints"]) if kp[2] == 0), None)
                if next_invisible is not None:
                    self.status_bar.showMessage(
                        f"已添加关键点 {first_invisible + 1}，请添加关键点 {next_invisible + 1}，右键或ESC结束", 2000)
                else:
                    self.status_bar.showMessage("所有关键点已添加，右键或ESC结束", 2000)
            except Exception as e:
                QMessageBox.warning(self, "警告", f"添加关键点时出错: {str(e)}")
                self.finish_adding_keypoints()

    def edit_keypoint(self, ann_idx, kp_idx):
        if 0 <= ann_idx < len(self.annotations) and 0 <= kp_idx < len(self.annotations[ann_idx]["keypoints"]):
            x, y, v = self.annotations[ann_idx]["keypoints"][kp_idx]

            dialog = QDialog(self)
            dialog.setWindowTitle("编辑关键点")
            layout = QVBoxLayout()

            lbl_index = QLabel(f"关键点序号: {kp_idx + 1}")
            layout.addWidget(lbl_index)

            lbl_visibility = QLabel("可见性:")
            visibility_combo = QComboBox()
            visibility_combo.addItems(["可见 (v=2)", "遮挡 (v=1)", "不可见 (v=0)"])
            visibility_combo.setCurrentIndex(2 - v)
            layout.addWidget(lbl_visibility)
            layout.addWidget(visibility_combo)

            btn_box = QHBoxLayout()
            btn_ok = QPushButton("确定")
            btn_cancel = QPushButton("取消")
            btn_box.addWidget(btn_ok)
            btn_box.addWidget(btn_cancel)

            btn_ok.clicked.connect(dialog.accept)
            btn_cancel.clicked.connect(dialog.reject)

            layout.addLayout(btn_box)
            dialog.setLayout(layout)

            if dialog.exec_() == QDialog.Accepted:
                old_v = v
                new_v = 2 - visibility_combo.currentIndex()
                self.annotations[ann_idx]["keypoints"][kp_idx] = (x, y, new_v)
                self.update_annotation_display()
                self.update_display()

                # 添加到撤销栈
                self.undo_stack.append(("edit_keypoint", ann_idx, kp_idx, old_v))

    def edit_bbox(self, ann_idx):
        if 0 <= ann_idx < len(self.annotations):
            dialog = QDialog(self)
            dialog.setWindowTitle("编辑边界框属性")
            layout = QVBoxLayout()

            lbl_class = QLabel("类别:")
            class_combo = QComboBox()
            class_combo.addItems(self.class_names)
            class_combo.setCurrentIndex(self.annotations[ann_idx]["class_id"])
            layout.addWidget(lbl_class)
            layout.addWidget(class_combo)

            btn_box = QHBoxLayout()
            btn_ok = QPushButton("确定")
            btn_cancel = QPushButton("取消")
            btn_box.addWidget(btn_ok)
            btn_box.addWidget(btn_cancel)

            btn_ok.clicked.connect(dialog.accept)
            btn_cancel.clicked.connect(dialog.reject)

            layout.addLayout(btn_box)
            dialog.setLayout(layout)

            if dialog.exec_() == QDialog.Accepted:
                old_class = self.annotations[ann_idx]["class_id"]

                self.annotations[ann_idx]["class_id"] = class_combo.currentIndex()

                self.update_annotation_display()
                self.update_display()

                # 添加到撤销栈
                self.undo_stack.append(("edit_bbox", ann_idx, old_class))

    def delete_keypoint(self, ann_idx, kp_idx):
        if 0 <= ann_idx < len(self.annotations) and 0 <= kp_idx < len(self.annotations[ann_idx]["keypoints"]):
            # 保存到撤销栈
            self.undo_stack.append(("delete_keypoint", ann_idx, kp_idx, self.annotations[ann_idx]["keypoints"][kp_idx]))

            # 将关键点设置为不可见
            self.annotations[ann_idx]["keypoints"][kp_idx] = (0, 0, 0)

            self.update_annotation_display()
            self.update_display()

    def delete_annotation(self, ann_idx):
        if 0 <= ann_idx < len(self.annotations):
            # 保存到撤销栈
            self.undo_stack.append(("delete_annotation", ann_idx, self.annotations[ann_idx]))

            del self.annotations[ann_idx]
            # 更新可见标注索引
            self.visible_annotations = {i if i < ann_idx else i - 1 for i in self.visible_annotations if i != ann_idx}
            self.update_annotation_display()
            self.update_display()

    def undo_action(self):
        if self.undo_stack:
            action = self.undo_stack.pop()

            if action[0] == "add_bbox":
                ann_idx = action[1]
                if 0 <= ann_idx < len(self.annotations):
                    del self.annotations[ann_idx]
                    self.visible_annotations.discard(ann_idx)

            elif action[0] == "edit_keypoint":
                ann_idx, kp_idx, old_v = action[1], action[2], action[3]
                if (0 <= ann_idx < len(self.annotations) and
                        0 <= kp_idx < len(self.annotations[ann_idx]["keypoints"])):
                    x, y, _ = self.annotations[ann_idx]["keypoints"][kp_idx]
                    self.annotations[ann_idx]["keypoints"][kp_idx] = (x, y, old_v)

            elif action[0] == "edit_bbox":
                ann_idx, old_class = action[1], action[2]
                if 0 <= ann_idx < len(self.annotations):
                    self.annotations[ann_idx]["class_id"] = old_class

            elif action[0] == "delete_annotation":
                ann_idx, annotation = action[1], action[2]
                self.annotations.insert(ann_idx, annotation)
                # 更新可见标注索引
                self.visible_annotations = {i if i < ann_idx else i + 1 for i in self.visible_annotations}
                self.visible_annotations.add(ann_idx)

            elif action[0] == "delete_keypoint":
                ann_idx, kp_idx, old_kp = action[1], action[2], action[3]
                if 0 <= ann_idx < len(self.annotations) and kp_idx < len(self.annotations[ann_idx]["keypoints"]):
                    self.annotations[ann_idx]["keypoints"][kp_idx] = old_kp

            self.update_annotation_display()
            self.update_display()

    def save_annotations(self):
        if not self.current_image_path:
            return

        txt_path = os.path.splitext(self.current_image_path)[0] + ".txt"

        try:
            with open(txt_path, "w") as f:
                for ann in self.annotations:
                    line = [str(ann["class_id"])]
                    line.extend(map(str, ann["bbox"]))

                    # 写入关键点 (确保有9个关键点)
                    keypoints = ann["keypoints"]
                    for i in range(9):
                        if i < len(keypoints):
                            x, y, v = keypoints[i]
                        else:
                            x, y, v = 0, 0, 0
                        line.extend([str(x), str(y), str(v)])

                    f.write(" ".join(line) + "\n")

            self.status_bar.showMessage(f"标注已保存到 {txt_path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存标注失败: {e}")

    def prev_image(self):
        if self.current_image_index > 0:
            self.save_annotations()
            self.current_image_index -= 1
            self.load_image()

    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.save_annotations()
            self.current_image_index += 1
            self.load_image()

    def closeEvent(self, event):
        if self.annotations:
            reply = QMessageBox.question(
                self, "保存标注",
                "是否保存当前图片的标注?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )

            if reply == QMessageBox.Yes:
                self.save_annotations()
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KeyPointLabeler()
    window.show()
    sys.exit(app.exec_())