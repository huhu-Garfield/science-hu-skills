# science_hu Figure Design

[简体中文](README.zh-CN.md)

## 1. What is this skill for, and how do I use it?

Turn an abstract, a set of findings, or a short research storyline into a scientific figure with a clear reading order. Develop the main message, layout, and drawing prompt, then export an editable figure after you approve the draft.

**Good fits**

- A mechanism diagram or graphical abstract that explains the study context, a key process, and the outcome.
- A side-by-side comparison that makes the difference between two groups or states easy to see.
- A review overview that organizes several themes or stages in a vertical, side-by-side, or circular layout.
- An existing draft that needs a scientific accuracy review, a clearer layout, or an editable export.

**How to invoke it**

Describe your research in your own words and attach an abstract, a summary of your findings, or a layout reference if available. Use the example below to start with a prompt. You can also bring an approved draft and ask for export directly.

> Use `science-hu-figure-design` to turn this research description and reference into a drawing prompt. Identify the main finding and mechanism, then choose a layout. Wait for me to approve the draft before exporting editable SVG and PPTX.

## 2. What does it deliver?

| Stage | Deliverable |
| --- | --- |
| Design | A one-sentence storyline, a layout description, and a ready-to-use drawing prompt, typically delivered in chat. |
| Review | A draft or preview to review. Generate it with an image model, draw a simple SVG sketch in the workbench, or supply an existing draft. |
| Export | `artwork.svg` and `artwork.pptx`. Edit the vector artwork in the SVG, or adjust individual shapes and text boxes in PowerPoint. |
| Verification | `verification.json` records the added paths, editable text, and picture object counts. A preview can be included when needed. |

You can stop at the prompt or draft stage if that is all you need.

## 3. Workflow

1. **Write the prompt.** Identify the main finding and mechanism. When references are available, adapt the reading order and panel organization from review figures. Choose a vertical, side-by-side, or circular layout. You can test the prompt with GPT-6.
2. **Approve the draft.** Have Codex draw a local sketch or bring back a draft from an image model. Workbenches with image generation enabled can write the prompt and generate a draft in the same chat. Confirm the layout, labels, and arrows before vectorizing.
3. **Export and polish.** Generate the SVG and PPTX locally. PowerPoint uses native paths and editable text boxes so you can refine colors, lines, and labels.

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

Download [this skill's ZIP](https://github.com/huhu-Garfield/science-hu-skills/raw/refs/heads/main/science-hu-figure-design.zip). It contains one top-level folder with `SKILL.md` and all conversion scripts.

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
