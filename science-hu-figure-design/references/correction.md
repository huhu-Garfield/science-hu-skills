# 校正和技术边界

- `text-manifest.json` 记录经 EXIF 方向归一后的源图尺寸。图像中左上角为原点，像素坐标向右、向下增长。可以修正 `content`、`x`、`y`、`font_size`、`fill`，或新增 `rotation`、`font_family`、`font_weight`。
- 每个条目使用唯一 `id`，`coordinate_space` 为 `pixels`。其中 `x`、`y` 为文本基线锚点，`bbox` 为需要去字的 `[左, 上, 宽, 高]`。编辑清单后使用 `--text-manifest /path/text-manifest.json` 重新转换原图。文字边缘靠近图形时可提供独立去字图 `--clean-image /path/cleaned.png`，尺寸须与原图一致。
- `--speckle 0` 可以保留小细节，通常会增加路径数。渐变、照片、细小字体和重叠文字难以精确重建，源图中遮挡的内容也无法从像素恢复。用实际渲染检查图形细节，尤其是透明边缘、复杂纹理和密集标注。
- 复杂 SVG 可保留线性和径向渐变、嵌套裁剪、虚线、箭头标记及常见的 `tspan` 上下标与混合字号。PPTX 用可编辑色带近似渐变，并将裁剪、虚线和箭头展开成矢量路径。混排文字可能分成多个可编辑文本框。输入 SVG 按原样保存，`verification.json` 会记录展开的效果。 滤镜、蒙版、图案填充、沿路径排字、逐字绝对定位、斜切文字和被裁去一部分的文字需要先整理为兼容的路径或文本。不同机器的字体会影响文本位置，透明渐变和组透明度可能有轻微显示差异。

## 清单示例

如果运行环境没有 OCR，可让工作台根据参考图手动记录标签。这里的坐标以 840 × 400 像素源图为例。

```json
{
  "schema_version": "1.0",
  "source_canvas": {"width": 840, "height": 400},
  "text_elements": [
    {
      "id": "label-1",
      "content": "Input",
      "coordinate_space": "pixels",
      "bbox": [151, 193, 91, 42],
      "x": 151, "y": 225,
      "font_size": 40,
      "font_family": "Arial",
      "fill": "#222222"
    }
  ]
}
```
