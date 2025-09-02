# 注意修改自己的关键点数量、类别标签配置

标注-关键点数据集标注v4.py 配置举例（3个类别、9个关键点）：
self.class_names = ["standing", "sidelying", "prone"]
self.keypoint_names = [f"关键点{i + 1}" for i in range(9)]

标注--分割数据集标注3-中文-3.py 配置举例：
在 def create_tag_buttons(self)中定义类别；
在self.setFixedSize(int(1724), int(2500))中设置窗口大小；
