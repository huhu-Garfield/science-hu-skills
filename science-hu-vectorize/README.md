# science_hu Vectorize

[简体中文](README.zh-CN.md)

## 1. What is this skill for, and how do I use it?

Rebuild an approved scientific figure, screenshot, or draft as editable vector artwork. In the PowerPoint export, you can change shapes, colors, and labels individually.

**Good fits**

- You have a PNG, JPEG, WebP, or screenshot that you need to edit for a paper, lab meeting, or defense.
- You have an approved draft and want its shapes and labels to remain separately editable.
- You have a compatible SVG and want to edit it in PowerPoint or place it in a copy of an existing deck.

**How to invoke it**

Attach the image and specify SVG, PPTX, or both. Include any exact labels or intentional whitespace you want to preserve.

> Use `science-hu-vectorize` to convert the attached image into SVG and editable PPTX. Crop the screenshot to the scientific figure, keep labels as text boxes, and preserve the arrows and legend.

## 2. What does it deliver?

| File | Purpose |
| --- | --- |
| `artwork.svg` | Scalable vector artwork that you can edit in a vector graphics editor. |
| `artwork.pptx` | A PowerPoint file with individually selectable paths and text boxes. |
| `verification.json` | A record of added paths, editable text, and picture object counts. |

For raster inputs, the conversion also saves `cleaned.png`, `paths.svg`, and `text-manifest.json` so you can inspect tracing issues or correct labels. You can request just the formats you need.

## 3. Workflow

1. **Identify the figure area.** Crop a screenshot to the artwork while preserving the legend and important edges.
2. **Prepare paths and labels.** Trace the raster shapes and check the labels. Correct the label manifest or rebuild important shapes and arrows if needed. A compatible SVG can go directly to export.
3. **Export SVG and PPTX.** Write vector shapes and restore labels as editable text boxes.
4. **Compare with the source.** Check layer order, arrows, holes, and label placement. Fine textures and small text in low-resolution screenshots may need manual adjustment.

### Complex SVG export

Complex SVG conversion supports linear and radial gradients, nested clips, dashed strokes, marker arrows, and common `tspan` formatting such as subscripts, superscripts, and mixed sizes. PowerPoint approximates gradients with editable vector bands and expands clips, dashes, and markers into paths. Styled text may be split into multiple editable text boxes. The input SVG is preserved, and `verification.json` records the expanded effects.

Filters, masks, pattern fills, text on a path, per-character absolute positioning, skewed text, and partially clipped text need compatible paths or text runs first. Available fonts can change text placement. Transparent gradients and group opacity can show minor differences.

### Actual PowerPoint preview and font baseline calibration (optional)

- `--preview` renders a temporary copy with desktop PowerPoint and saves `powerpoint-preview.png`, `svg-preview.png`, and `svg-powerpoint-comparison.png`. Review gradients, clipping, arrows, and text side by side. When adding artwork to an existing deck, the left image shows the new SVG artwork and the right image shows the full target slide.
- `--calibrate-fonts` measures the baseline for each family and bold/italic combination used in the figure, adjusts the editable text boxes, and saves `font-baselines.json`. It is useful for formulas, subscripts, superscripts, and dense labels. Measurements use a 40 pt probe and are scaled to the actual text size. You can enable calibration with or without the preview.

```bash
python3 scripts/run.py --input-svg figure.svg --output-dir checked-export --preview --calibrate-fonts
```

Both checks require working desktop PowerPoint on macOS or Windows. On macOS, the terminal or workbench may need Automation permission to control PowerPoint. Extra dependencies are prepared on first use, or you can prepare them with `python3 scripts/run.py --setup-preview`. If native rendering is unavailable, conversion still saves the SVG and PPTX and records the check status in `verification.json`. Calibration reflects the local Office installation and fonts, so measure again on a different machine.

## Install

Download [this skill's ZIP](https://github.com/huhu-Garfield/science-hu-skills/raw/refs/heads/main/science-hu-vectorize.zip). It contains one top-level folder with `SKILL.md` and all conversion scripts.

| Workbench | Installation |
| --- | --- |
| Codex | Extract the folder into `~/.agents/skills/`, or into `.agents/skills/` in a project. Start a new session. |
| Claude Code | Extract the folder into `~/.claude/skills/`, or into `.claude/skills/` in a project. Start a new session. |
| Claude / Claude Desktop | Enable code execution, then open **Customize → Skills → + → Upload a skill** and select this ZIP. |
| Tencent WorkBuddy | Open **Skills → Add skill → Upload skill** and select one skill ZIP. |
| Doubao Work desktop | Choose **Work mode → Local computer**. Try the individual ZIP if the client offers skill upload. You can also follow the official guide to copy the extracted skill folder into the active profile's local skills directory. |
| Other Agent Skills workbenches | Import the folder or ZIP using the workbench's instructions. File conversion requires Python and permission to run scripts. |

[Official Codex installation instructions](https://developers.openai.com/api/reference/cli) · [Claude Code skills](https://code.claude.com/docs/en/skills) · [Upload a skill in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

[WorkBuddy skill import](https://www.tencentcloud.com/zh/document/product/1316/84503) · [Doubao Work local skill installation](https://docs.volcengine.com/docs/agent-toolkit/agent-auto-install-guide?lang=zh)

These steps come from platform documentation. Neither client has been tested with these packages. Check that the workbench can run Python scripts after import. The optional preview and font calibration also require access to desktop PowerPoint on the same computer.

## First run

Python 3.12 is recommended. If the required packages are missing, the first conversion downloads them into an isolated environment automatically. A restricted execution environment may require packages to be preinstalled. Once set up, the converter processes files offline. No additional skill or PowerPoint installation is required. In a hosted workbench, processing takes place in that workbench's execution environment.

Automatic raster text recognition uses Apple Vision on macOS with Swift command-line tools, or Tesseract if available. For other setups, supply a [label manifest](references/correction.md) or use `--no-text` for unlabeled artwork. SVG with editable text goes directly to export.

Run the bundled converter from the extracted skill folder:

```bash
python3 scripts/run.py --input-image reference.png --output-dir my-export
```

On Windows, use `py -3.12` or `python` in place of `python3`. Use `--input-svg` for compatible SVG. The output folder must be a new path. See [SKILL.md](SKILL.md) for the workbench workflow.

## Author

**science_hu** is a personal project created and maintained by **huhu-Garfield**. Use GitHub Issues to share feedback, report bugs, or discuss collaboration. License notices for bundled components accompany those files.
