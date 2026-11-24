---
name: science-hu-vectorize
description: Convert an existing scientific diagram, screenshot, PNG, JPEG, WebP, or SVG into editable SVG and native PowerPoint shapes and text. Use when the source artwork is already decided.
---

# science_hu 图像矢量化

从用户选定的图开始。截图先裁去工具栏、黑边和选中控件，保留原图的图例和边缘内容。用本技能内的 [运行脚本](scripts/run.py) 处理。使用现有 Python 环境或自动准备所需依赖，图片、文字和导出文件在当前执行环境中处理。

```bash
python3 /path/to/science-hu-vectorize/scripts/run.py --input-image reference.png --output-dir new-export
```

在 Windows 可将 `python3` 换成 `py -3.12` 或 `python`。输出目录使用新路径。

- 已有兼容 SVG 时用 `--input-svg`。无字图用 `--no-text`。有字图优先使用本机 Apple Vision 或已安装的 Tesseract。
- OCR 不可用或质量不足时，对照参考图转录标签，按[校正说明](references/correction.md)编写或修正文字清单。细线图、机制图或密集标注可将轮廓、箭头和文字按语义重绘为 SVG，再用同一个入口导出。
- 需要修改既有 PPTX 时传入 `--input-pptx` 以输出副本，默认追加新页。指定 `--slide-index 3` 可放进第 3 页。
- 检查图层、箭头、镂空、标签与 `verification.json`。交付 `artwork.svg` 和 `artwork.pptx`，或用户指定的格式。图形和文字分别保持可编辑。

复杂 SVG 的渐变、裁剪、虚线、箭头和常见内联文字由导出工具展开为原生对象。核验时检查 `expanded_svg_effects`，兼容细节见[校正说明](references/correction.md)。

按用户要求可加 `--preview`，用桌面 PowerPoint 生成目标页与 SVG 的并排对照。公式或密集标注可另开 `--calibrate-fonts` 实测调整字体基线。两项默认关闭，检查以 `verification.json` 的结果为准。
