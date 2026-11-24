# SVG 与可编辑 PowerPoint 导出

- 兼容 SVG 使用 `viewBox`、基本路径、圆、矩形和原生 `text`。显式绘制箭头头部，以便曲线、箭头和标签各自可编辑。复杂 SVG 可保留线性和径向渐变、嵌套裁剪、虚线、箭头标记及常见的 `tspan` 上下标与混合字号。PPTX 用可编辑色带近似渐变，并将裁剪、虚线和箭头展开成矢量路径。混排文字可能分成多个可编辑文本框。输入 SVG 按原样保存，`verification.json` 会记录展开的效果。 滤镜、蒙版、图案填充、沿路径排字、逐字绝对定位、斜切文字和被裁去一部分的文字需要先整理为兼容的路径或文本。不同机器的字体会影响文本位置，透明渐变和组透明度可能有轻微显示差异。
- 位图由模块、连线和标签构成时优先按对象重绘。复杂彩色插画可以局部描摹。SVG 组可组织相关部件，写入器导出为单独的可编辑 PPT 对象。
- 清晰位图也可直接描摹。对照原图和[校正说明](correction.md)修正标签与位置。如果 OCR 把箭头认成文字，从清单中删掉该项，再从原图导出。

```bash
python3 /path/to/science-hu-figure-design/scripts/run.py --input-svg approved.svg --output-dir new-export
```

Windows 可用 `py -3.12` 或 `python`。位图使用 `--input-image approved.png`，无字图加 `--no-text`。已有文本清单使用 `--text-manifest labels.json`。本命令会自动准备所需的本地依赖。输出目录使用新路径。

用 SVG 渲染或图形编辑器检查分区、标签、箭头方向及层叠顺序。macOS 可用 `sips -s format png artwork.svg --out preview.png`。检查 `verification.json` 的新增原生对象和图片数量。只有实际在 PowerPoint 打开过，才报告已在 PowerPoint 核对。

## 可选的 PowerPoint 实际检查

向转换命令加 `--preview`，使用本机 PowerPoint 渲染临时副本并生成 `svg-powerpoint-comparison.png`。要校准公式或密集标签的文字位置，再加 `--calibrate-fonts`，查看 `font-baselines.json`。实际渲染不可用时照常保留 SVG 和 PPTX，并在核验中记录原因。
