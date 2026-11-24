# science_hu 科研图设计

[English](README.md)

## 1. 这个 Skill 做什么，怎么用？

把论文摘要、实验结果或几句研究主线变成一张有明确阅读顺序的科研图。从提炼亮点、选构图和写绘图提示词开始，在你确认草图后，输出可以继续调整的矢量文件。

**适合的任务**

- 机制示意图或图文摘要，需要用一张图说明研究对象、关键过程和结果。
- 两组或两种状态的对照图，需要让读者一眼看到差异。
- 综述总览图，需要把多个主题或阶段组织成上下、左右或圆圈布局。
- 已有一版草图，需要核对科学表述、调整构图或导出可编辑稿。

**怎么调用**

把文章主线用自己的话发给 AI，可以附上摘要、结果要点或构图参考。用下面这条指令从提示词开始，也可以带着已认可的草图直接要求导出。

> 用 `science-hu-figure-design` 根据这段研究描述和参考图写绘图提示词。请先提炼文章亮点和机制关系，选一个合适的布局。等我确认草图后，再导出 SVG 和可编辑 PPTX。

## 2. 最终交付什么？

| 阶段 | 交付物 |
| --- | --- |
| 设计 | 一句话研究主线、布局说明和可直接使用的绘图提示词，通常在对话中提供。 |
| 审稿 | 供核对的草图或预览。可由生图模型生成，也可由工作台直接绘制简洁的 SVG 草图。 |
| 导出 | `artwork.svg` 和 `artwork.pptx`。SVG 用于继续编辑矢量图，PPTX 中的路径和文本框可单独调整。 |
| 核验 | `verification.json` 记录新增路径、可编辑文字及图片对象数量。需要时可附预览图。 |

如果只需要提示词或草图，可以在对应阶段结束。

## 3. 使用这个 Skill 的工作流程

1. **写提示词。** 从文章主线提炼亮点和机制关系，有参考时借鉴顶刊综述图的阅读顺序与分区，选择上下、左右或综述圆圈布局。完整提示词可以交给 GPT-6 测试。
2. **确认草图。** 可以让 Codex 本地绘制草图，也可以把其他图像模型生成的版本带回来。当前工作台已启用生图功能时，也可以在同一对话先写提示词再出草图。确认构图、标签和箭头后再做最终矢量化。
3. **导出和打磨。** 本地生成 SVG 和 PPTX。PPTX 的图形使用原生路径，标签使用可编辑文本框，便于继续调整配色、线条和文字。

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

下载[本技能的 ZIP](https://github.com/huhu-Garfield/science-hu-skills/raw/refs/heads/main/science-hu-figure-design.zip)。包内有一个顶层目录，包含 `SKILL.md` 和全部转换脚本。

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
