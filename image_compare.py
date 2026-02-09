#!/usr/bin/env python3
"""
图片对比工具 - 交替显示两张图片并支持导出 GIF (Imageio版)
"""

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QSpinBox, QDoubleSpinBox,
    QGroupBox, QSizePolicy, QMessageBox
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer
from PIL import Image


class ImageCompare(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("图片对比工具 (Imageio优化版)")
        self.setMinimumSize(900, 700)

        # 状态变量
        self.image1_path = None
        self.image2_path = None
        self.pixmap1 = None
        self.pixmap2 = None
        self.current_showing = 1
        self.remaining_toggles = 0
        self.is_running = False
        self.output_dir = None

        # 定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self._toggle_image)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(10)

        # ── 图片选择区域 ──
        select_group = QGroupBox("选择图片")
        select_layout = QHBoxLayout(select_group)

        self.btn_img1 = QPushButton("选择图片 A")
        self.btn_img1.setFixedHeight(36)
        self.btn_img1.clicked.connect(lambda: self._pick_image(1))
        self.label_img1 = QLabel("未选择")
        self.label_img1.setStyleSheet("color: gray;")

        self.btn_img2 = QPushButton("选择图片 B")
        self.btn_img2.setFixedHeight(36)
        self.btn_img2.clicked.connect(lambda: self._pick_image(2))
        self.label_img2 = QLabel("未选择")
        self.label_img2.setStyleSheet("color: gray;")

        select_layout.addWidget(self.btn_img1)
        select_layout.addWidget(self.label_img1, 1)
        select_layout.addSpacing(20)
        select_layout.addWidget(self.btn_img2)
        select_layout.addWidget(self.label_img2, 1)

        root_layout.addWidget(select_group)

        # ── 参数设置区域 ──
        param_group = QGroupBox("参数设置")
        param_layout = QHBoxLayout(param_group)

        param_layout.addWidget(QLabel("交替频率 (秒):"))
        self.spin_freq = QDoubleSpinBox()
        self.spin_freq.setRange(0.1, 10.0)
        self.spin_freq.setValue(0.5)
        self.spin_freq.setSingleStep(0.1)
        self.spin_freq.setDecimals(1)
        self.spin_freq.setFixedWidth(80)
        param_layout.addWidget(self.spin_freq)

        param_layout.addSpacing(30)

        param_layout.addWidget(QLabel("交替次数:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 999)
        self.spin_count.setValue(10)
        self.spin_count.setFixedWidth(80)
        param_layout.addWidget(self.spin_count)

        param_layout.addStretch()
        root_layout.addWidget(param_group)

        # ── 控制按钮区域 ──
        ctrl_layout = QHBoxLayout()

        self.btn_start = QPushButton("▶  开始对比")
        self.btn_start.setFixedHeight(40)
        self.btn_start.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 6px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        self.btn_start.clicked.connect(self._start_compare)

        self.btn_stop = QPushButton("⏹  停止")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; font-weight: bold; border-radius: 6px; }"
            "QPushButton:hover { background-color: #da190b; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        self.btn_stop.clicked.connect(self._stop_compare)

        self.btn_save = QPushButton("💾  保存 GIF")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; border-radius: 6px; }"
            "QPushButton:hover { background-color: #1976D2; }"
            "QPushButton:disabled { background-color: #ccc; color: #666; }"
        )
        self.btn_save.clicked.connect(self._save_gif)

        ctrl_layout.addWidget(self.btn_start)
        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_save)
        root_layout.addLayout(ctrl_layout)

        # ── 图片预览区域 ──
        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout(preview_group)

        self.label_which = QLabel("当前显示: 无")
        self.label_which.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_which.setStyleSheet("font-size: 13px; font-weight: bold; color: #333;")
        preview_layout.addWidget(self.label_which)

        self.preview = QLabel("请选择两张图片后开始对比")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setStyleSheet(
            "QLabel { background-color: #f5f5f5; border: 2px dashed #ccc; border-radius: 8px; "
            "color: #999; font-size: 16px; }"
        )
        preview_layout.addWidget(self.preview, 1)

        root_layout.addWidget(preview_group, 1)

        # ── 状态栏 ──
        self.status = QLabel("就绪")
        self.status.setStyleSheet("color: #666; font-size: 12px; padding: 4px;")
        root_layout.addWidget(self.status)

    # ────────────────── 选择图片 ──────────────────
    def _pick_image(self, which):
        path, _ = QFileDialog.getOpenFileName(
            self, f"选择图片 {'A' if which == 1 else 'B'}",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp);;所有文件 (*)"
        )
        if not path:
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "错误", f"无法加载图片:\n{path}")
            return

        if which == 1:
            self.image1_path = path
            self.pixmap1 = pixmap
            self.label_img1.setText(Path(path).name)
            self.label_img1.setStyleSheet("color: #333;")
        else:
            self.image2_path = path
            self.pixmap2 = pixmap
            self.label_img2.setText(Path(path).name)
            self.label_img2.setStyleSheet("color: #333;")

        if not self.is_running:
            self._show_pixmap(pixmap, which)

        self.status.setText(f"已加载图片 {'A' if which == 1 else 'B'}: {path}")

    # ────────────────── 显示图片 ──────────────────
    def _show_pixmap(self, pixmap, which):
        if pixmap is None:
            return
        preview_size = self.preview.size()
        scaled = pixmap.scaled(
            preview_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)
        tag = "A" if which == 1 else "B"
        color = "#4CAF50" if which == 1 else "#2196F3"
        self.label_which.setText(f'当前显示: <span style="color:{color};">图片 {tag}</span>')

    # ────────────────── 开始对比 ──────────────────
    def _start_compare(self):
        if self.pixmap1 is None or self.pixmap2 is None:
            QMessageBox.warning(self, "提示", "请先选择两张图片！")
            return

        self.is_running = True
        self.remaining_toggles = self.spin_count.value() * 2
        self.current_showing = 1
        self._show_pixmap(self.pixmap1, 1)

        interval_ms = int(self.spin_freq.value() * 1000)
        self.timer.start(interval_ms)

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status.setText(f"对比中... 剩余 {self.remaining_toggles // 2} 次交替")

    # ────────────────── 切换图片 ──────────────────
    def _toggle_image(self):
        if self.remaining_toggles <= 0:
            self._stop_compare()
            return

        if self.current_showing == 1:
            self.current_showing = 2
            self._show_pixmap(self.pixmap2, 2)
        else:
            self.current_showing = 1
            self._show_pixmap(self.pixmap1, 1)

        self.remaining_toggles -= 1
        self.status.setText(f"对比中... 剩余 {max(0, self.remaining_toggles // 2)} 次交替")

    # ────────────────── 停止对比 ──────────────────
    def _stop_compare(self):
        self.timer.stop()
        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status.setText("对比已停止")

    # ────────────────── 保存 GIF (Imageio版) ──────────────────
    def _save_gif(self):
        if self.image1_path is None or self.image2_path is None:
            QMessageBox.warning(self, "提示", "请先选择两张图片！")
            return

        # 路径选择逻辑
        if self.output_dir and os.path.isdir(self.output_dir):
            ret = QMessageBox.question(
                self, "保存路径",
                f"继续保存到:\n{self.output_dir}\n\n点击「Yes」直接保存，「No」重新选择目录",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.No:
                out_dir = QFileDialog.getExistingDirectory(self, "选择 GIF 保存目录", self.output_dir)
                if not out_dir: return
                self.output_dir = out_dir
        else:
            out_dir = QFileDialog.getExistingDirectory(self, "选择 GIF 保存目录", "")
            if not out_dir: return
            self.output_dir = out_dir

        # 获取参数
        freq = self.spin_freq.value()
        count = self.spin_count.value()
        
        try:
            # 1. 使用 PIL 读取并预处理图片（尺寸统一、白色背景）
            # 转为 RGBA 以处理透明度，防止粘贴黑底
            img1 = Image.open(self.image1_path).convert("RGBA")
            img2 = Image.open(self.image2_path).convert("RGBA")

            # 计算最大画布尺寸
            max_w = max(img1.width, img2.width)
            max_h = max(img1.height, img2.height)

            def resize_pad(img, w, h):
                """缩放并居中贴在白底上，防止透明图变黑"""
                # 创建缩略图
                img_copy = img.copy()
                img_copy.thumbnail((w, h), Image.Resampling.LANCZOS)
                
                # 创建白色底板 (GIF不支持半透明，RGB模式比较安全)
                canvas = Image.new("RGB", (w, h), (255, 255, 255))
                
                # 计算居中位置
                x = (w - img_copy.width) // 2
                y = (h - img_copy.height) // 2
                
                # 粘贴（使用 alpha 通道作为 mask）
                canvas.paste(img_copy, (x, y), mask=img_copy)
                return canvas

            img1_processed = resize_pad(img1, max_w, max_h)
            img2_processed = resize_pad(img2, max_w, max_h)

            # 2. 合并两张图片生成共享最优调色板 (GIF 只支持 256 色)
            combined = Image.new("RGB", (max_w, max_h * 2))
            combined.paste(img1_processed, (0, 0))
            combined.paste(img2_processed, (0, max_h))
            palette_img = combined.quantize(colors=256, method=Image.Quantize.MEDIANCUT)

            # 3. 用共享调色板量化每帧，启用 Floyd-Steinberg 抖动减少色带
            img1_q = img1_processed.quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG)
            img2_q = img2_processed.quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG)

            # 4. 构建帧列表
            frames_pil = []
            for _ in range(count):
                frames_pil.append(img1_q.copy())
                frames_pil.append(img2_q.copy())

            # 5. 使用 PIL 保存 GIF (颜色保留效果优于 imageio)
            out_path = os.path.join(self.output_dir, "compare.gif")
            duration_ms = int(freq * 1000)
            frames_pil[0].save(
                out_path,
                save_all=True,
                append_images=frames_pil[1:],
                duration=duration_ms,
                loop=0,
            )

            QMessageBox.information(self, "成功", f"GIF 已保存到:\n{out_path}")
            self.status.setText(f"GIF 已保存: {out_path}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存 GIF 时出错:\n{e}")

    # ────────────────── 窗口缩放事件 ──────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.is_running:
            return
        if self.current_showing == 1 and self.pixmap1:
            self._show_pixmap(self.pixmap1, 1)
        elif self.current_showing == 2 and self.pixmap2:
            self._show_pixmap(self.pixmap2, 2)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ImageCompare()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()