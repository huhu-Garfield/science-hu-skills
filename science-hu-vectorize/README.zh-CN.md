# science_hu 图像矢量化

[English](README.md)

## 1. 这个 Skill 做什么，怎么用？

把已经确定的科研图、截图或草图重建成可编辑的矢量图。导出到 PowerPoint 后，可以分别调整形状、颜色和标签。

**适合的任务**

- 只有 PNG、JPG、WebP 或截图，需要放进论文、组会或答辩材料继续编辑。
- 已有满意的绘图草稿，需要把图形和文字分别保留为可编辑对象。
- 已有兼容的 SVG，需要在 PowerPoint 中继续修改，或把图添加到现有演示文稿的副本。

**怎么调用**

上传图片，说明要 SVG、PPTX 还是两者。有必须保留的术语或有意保留的空白时，可以一并说明。

> 用 `science-hu-vectorize` 把附件转成 SVG 和可编辑 PPTX。只保留截图里的科研图，标签用文本框，保留原有箭头和图例。

## 2. 最终交付什么？

| 文件 | 用途 |
| --- | --- |
| `artwork.svg` | 可缩放的矢量图，可在矢量编辑器中修改。 |
| `artwork.pptx` | 可继续修改的 PowerPoint 文件，路径和文本框可单独选中。 |
| `verification.json` | 记录新增路径、可编辑文字及图片对象数量，便于核验。 |

处理位图时还会保留 `cleaned.png`、`paths.svg` 和 `text-manifest.json`，便于定位描摹问题或校正文字。可以只交付你指定的格式。

## 3. 使用这个 Skill 的工作流程

1. **确认图的范围。** 从截图裁出目标图，保留图例和有效边缘。
2. **处理路径和文字。** 位图会描摹轮廓并核对标签。需要时校正文字清单，或按图形、箭头和标签重绘。兼容 SVG 可直接导出。
3. **导出 SVG 和 PPTX。** 图形写成矢量路径，标签恢复为可编辑文本框。
4. **对照检查。** 核对层叠、箭头、镂空和标签位置。低清截图中的细纹和小字可能需要手动修正。

### 复杂 SVG 导出

复杂 SVG 可保留线性和径向渐变、嵌套裁剪、虚线、箭头标记及常见的 `tspan` 上下标与混合字号。PPTX 用可编辑色带近似渐变，并将裁剪、虚线和箭头展开成矢量路径。混排文字可能分成多个可编辑文本框。输入 SVG 按原样保存，`verification.json` 会记录展开的效果。

滤镜、蒙版、图案填充、沿路径排字、逐字绝对定位、斜切文字和被裁去一部分的文字需要先整理为兼容的路径或文本。不同机器的字体会影响文本位置，透明渐变和组透明度可能有轻微显示差异。

### PowerPoint 实际预览与字体基线校准（可选）

- `--preview` 让桌面 PowerPoint 渲染输出文件的临时副本，生成 `powerpoint-preview.png`、`svg-preview.png` 和 `svg-powerpoint-comparison.png`。并排图便于核对渐变、裁剪、箭头和文字。添加到既有演示文稿时，左侧是新加的 SVG 图，右侧是目标整页。
- `--calibrate-fonts` 实测图中每种字体的常规、粗体或斜体组合，在写入文本框时调整基线，并记录到 `font-baselines.json`。适合公式、上下标或密集标签。校准以 40 pt 探针测量，每个字号按比例应用。可单独使用，也可和预览一起使用。

```bash
python3 scripts/run.py --input-svg figure.svg --output-dir checked-export --preview --calibrate-fonts
```

两项检查均需要本机安装可运行的桌面 PowerPoint，支持 macOS 和 Windows。Mac 可能需要允许当前终端或工作台控制 PowerPoint。首次启用可自动准备额外依赖，也可用 `python3 scripts/run.py --setup-preview` 提前准备。若实际渲染不可用，转换仍会保留 SVG 和 PPTX，`verification.json` 会报告检查状态。基线校准反映当前 PowerPoint 和安装的字体，换机器后应重新测量。

## 安装

下载[本技能的 ZIP](https://github.com/huhu-Garfield/science-hu-skills/raw/refs/heads/main/science-hu-vectorize.zip)。包内有一个顶层目录，包含 `SKILL.md` 和全部转换脚本。

| 工作台 | 安装方式 |
| --- | --- |
| Codex | 将技能目录解压到 `~/.agents/skills/`，或放入项目的 `.agents/skills/`，再开新对话。 |
| Claude Code | 将技能目录解压到 `~/.claude/skills/`，或放入项目的 `.claude/skills/`，再开新会话。 |
| Claude / Claude Desktop | 启用代码执行，在 **Customize → Skills → + → Upload a skill** 上传本 ZIP。 |
| 腾讯 WorkBuddy | 在「技能 → 添加技能 → 上传技能」中选择单个 ZIP。 |
| 豆包工作电脑版 | 使用「工作模式 → 本地电脑」。如有「上传技能」入口，可试用单个 ZIP。也可按官方指南把解压后的技能目录放入当前账户的本地技能目录。 |
| 其他兼容 Agent Skills 的工作台 | 按工作台说明导入目录或 ZIP。文件转换需要 Python 和脚本执行权限。 |

[Codex 官方安装说明](https://developers.openai.com/api/reference/cli) · [Claude Code 技能说明](https://code.claude.com/docs/en/skills) · [Claude 技能上传说明](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

[WorkBuddy 技能导入说明](https://www.tencentcloud.com/zh/document/product/1316/84503) · [豆包工作本地技能安装说明](https://docs.volcengine.com/docs/agent-toolkit/agent-auto-install-guide?lang=zh)

安装步骤依据平台文档，两款客户端尚未实测这两个包。导入后需确认工作台能执行 Python 脚本。可选的实际预览和字体校准还需要工作台能调用本机桌面 PowerPoint。

## 首次使用

推荐 Python 3.12。首次转换时，若缺少依赖，启动脚本会自动下载并准备独立环境。若工作台禁止下载，可在执行环境中预装依赖。依赖就绪后，转换可离线执行。本包可独立使用，无需安装另一项技能或 PowerPoint。使用托管工作台时，文件在该工作台的执行环境中处理。

位图自动识字使用带 Swift 命令行工具的 macOS Vision，或本机已有的 Tesseract。其他环境可提交[文字清单](references/correction.md)，无字图使用 `--no-text`。带原生文字的 SVG 可以直接导出。

也可在解压后的技能目录中运行脚本：

```bash
python3 scripts/run.py --input-image reference.png --output-dir my-export
```

Windows 用 `py -3.12` 或 `python` 替代 `python3`。兼容 SVG 使用 `--input-svg`。输出目录请使用新路径。工作台内的流程见 [SKILL.md](SKILL.md)。

## 作者

**science_hu** 是 **huhu-Garfield** 个人创作与维护的项目。欢迎通过 GitHub Issues 交流建议、反馈问题或探讨合作。随附组件的许可声明与相应文件一同保留。
