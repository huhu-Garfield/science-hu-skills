---
name: science-hu-figure-design
description: Turn a scientific storyline into a graphical abstract, mechanism figure, or review diagram. Develop the prompt, review the draft, then export editable SVG and PowerPoint.
---

# science_hu 科研图设计

从用户现有的材料接续。给文章主线时先写提示词，给待审的草图时先核对，给已认可的图片并明确要求导出时直接进入本地重绘。

## 1. 写提示词

从文章主线提炼要突出的发现、对象和机制关系，列清箭头方向、证据强度和准确标签。用不同线型或标注区分假说、相关性和已证实因果。标记会影响图意的未知细节。

有顶刊综述图等参考时，提取阅读顺序、分区、层级和图例位置。按[布局和提示词](references/layout-and-prompt.md)选上下、左右或综述圆圈布局，再交付可复制的提示词。可以把提示词交给 GPT-6 测试，或用用户指定的模型。

## 2. 确认草图

草图可由 Codex 在当前环境绘制并渲染简单 SVG，也可用工作台已启用的生图工具生成，或由用户把其他图像模型生成的 PNG、JPEG、WebP 或 SVG 带回。用户要求先看提示词时，得到确认后继续出图；要求直接出草图时，可以同轮写提示词和出图。

对照主线核查草图的构图、模块边界、图例、标签、箭头方向和连接端点。必要时记录要在重绘中修正的细节。用户认可草图后进入最终导出。

## 3. 导出和打磨

用随包附带的[本地导出工具](references/local-export.md)生成 SVG 和原生 PPTX。机制图优先按语义重绘矢量形状，纹理复杂的插图可描摹局部。文字尽量保留为可编辑文本。检查图层顺序、镂空、标注和可读性，按用户选定的格式交付。

复杂 SVG 的渐变、裁剪、虚线、箭头和常见内联文字由本地导出工具展开。对照 SVG 核查色带、裁剪边界和文本位置。

按用户要求可加 `--preview`，用桌面 PowerPoint 生成目标页与 SVG 的并排对照。公式或密集标注可另开 `--calibrate-fonts` 实测调整字体基线。两项默认关闭，检查以 `verification.json` 的结果为准。
