"""Render and measure a private copy with the installed Microsoft PowerPoint."""
from __future__ import annotations

import ctypes
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager

import pypdfium2 as pdfium
from pypdfium2 import raw
from resvg_py import svg_to_bytes
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pptx import Presentation

from drawingml.write_pptx import EMU_PER_PT, add_text, font_signature, slide_layout

SCRIPTS = Path(__file__).resolve().parent
PROBE_FONT_SIZE = 40
COLUMNS, ROWS = 4, 5
CELL_WIDTH, CELL_HEIGHT = 180, 104
PAGE_WIDTH, PAGE_HEIGHT = COLUMNS * CELL_WIDTH, ROWS * CELL_HEIGHT


@contextmanager
def powerpoint_pdf(deck: Path):
    """Use the native document API, and only close the uniquely named copy."""
    if sys.platform == "darwin":
        sandbox = Path.home() / "Library/Containers/com.microsoft.Powerpoint/Data/tmp"
        if not sandbox.is_dir():
            raise RuntimeError("PowerPoint's local Mac container is unavailable. Open desktop PowerPoint once.")
        command = ["/usr/bin/osascript", str(SCRIPTS / "powerpoint_export.applescript")]
        parent = sandbox
    elif sys.platform == "win32":
        shell = shutil.which("powershell.exe")
        if not shell:
            raise RuntimeError("Windows PowerShell is unavailable.")
        command = [shell, "-NoProfile", "-NonInteractive", "-File", str(SCRIPTS / "powerpoint_export.ps1")]
        parent = None
    else:
        raise RuntimeError("Actual PowerPoint rendering requires desktop PowerPoint on macOS or Windows.")

    with tempfile.TemporaryDirectory(prefix="science-hu-render-", dir=parent) as temporary:
        directory = Path(temporary).resolve()
        snapshot = directory / f"science-hu-{uuid.uuid4().hex}.pptx"
        pdf = directory / "rendered.pdf"
        shutil.copyfile(deck, snapshot)
        args = [*command, str(snapshot), str(pdf)]
        if sys.platform == "darwin":
            args.append(snapshot.name)
        try:
            response = subprocess.run(args, capture_output=True, text=True, timeout=58)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("PowerPoint timed out while rendering the temporary copy.") from error
        if response.returncode or not pdf.is_file() or pdf.stat().st_size == 0:
            detail = response.stderr.strip() or response.stdout.strip() or "PDF output was not created."
            raise RuntimeError(f"PowerPoint render failed: {detail[:1200]}")
        yield pdf, response.stdout.strip()


def render_reference(source, dimensions):
    # Read from memory. Conversion has already validated external references.
    data = svg_to_bytes(
        svg_string=source.read_text(encoding="utf-8-sig"), width=dimensions[0],
        background="#ffffff", dpi=96,
    )
    with Image.open(BytesIO(bytes(data))) as image:
        return ImageOps.contain(image.convert("RGB"), dimensions, Image.Resampling.LANCZOS)


def render_comparison(svg, pptx, slide, geometry, job, existing):
    with powerpoint_pdf(pptx) as (pdf, version), pdfium.PdfDocument(pdf) as document:
        slides = Presentation(str(pptx)).slides
        visible = [index for index,item in enumerate(slides,1) if item.element.get("show","1") not in {"0","false"}]
        if len(document) == len(slides):
            pdf_index = slide-1
        elif len(document) == len(visible) and slide in visible:
            pdf_index = visible.index(slide)
        else:
            raise RuntimeError(f"Could not match slide {slide} to PowerPoint's PDF export.")
        page = document[pdf_index]
        scale = 1440 / max(page.get_size())
        bitmap = page.render(scale=scale)
        powerpoint = bitmap.to_pil().convert("RGB")
        bitmap.close()
        page.close()

    existing_deck = Presentation(str(existing)) if existing else None
    (slide_width, slide_height), (art_scale, _, _, _, _) = slide_layout(geometry["view_box"], existing_deck)
    _, _, width, height = map(float, geometry["view_box"])
    fit = (
        max(1, round(width * art_scale / slide_width * powerpoint.width)),
        max(1, round(height * art_scale / slide_height * powerpoint.height)),
    )
    reference = render_reference(svg, fit)
    canvas = Image.new("RGB", powerpoint.size, "white")
    canvas.paste(reference, ((canvas.width-reference.width)//2, (canvas.height-reference.height)//2))
    label_height, gap, border = 38, 16, 12
    side_by_side = Image.new("RGB", (
        2*powerpoint.width + gap + 2*border, powerpoint.height + label_height + 2*border
    ), "#e9edf1")
    draw = ImageDraw.Draw(side_by_side)
    font = ImageFont.load_default(size=19)
    for x, image, label in (
        (border, canvas, "SVG reference (artwork only)"),
        (border + powerpoint.width + gap, powerpoint, f"Microsoft PowerPoint (slide {slide})"),
    ):
        draw.text((x, border), label, fill="#203041", font=font)
        side_by_side.paste(image, (x, border+label_height))
    powerpoint.save(job / "powerpoint-preview.png")
    canvas.save(job / "svg-preview.png")
    side_by_side.save(job / "svg-powerpoint-comparison.png")
    return {
        "status": "rendered",
        "renderer": "Microsoft PowerPoint PDF export",
        "powerpoint_version": version,
        "slide": slide,
        "powerpoint_preview": "powerpoint-preview.png",
        "svg_preview": "svg-preview.png",
        "comparison": "svg-powerpoint-comparison.png",
    }


def make_probe(styles, target):
    deck = Presentation()
    deck.slide_width = int(PAGE_WIDTH * EMU_PER_PT)
    deck.slide_height = int(PAGE_HEIGHT * EMU_PER_PT)
    slots = COLUMNS*ROWS
    for offset in range(0, len(styles), slots):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        for index,(family,bold,italic) in enumerate(styles[offset:offset+slots]):
            row,col = divmod(index,COLUMNS)
            probe = {
                "objectName": f"Baseline probe {offset+index+1}",
                "text": {
                    "contents": "H", "position": [col*CELL_WIDTH+32, row*CELL_HEIGHT+67],
                    "fontSize": PROBE_FONT_SIZE, "fontFamily": family,
                    "fontWeight": "bold" if bold else "normal",
                    "fontStyle": "italic" if italic else "normal",
                },
            }
            add_text(slide, probe, (1,0,0,0,0))
    deck.save(target)


def measure_probes(pdf, styles):
    measurements = {}
    with pdfium.PdfDocument(pdf) as document:
        for page_index,page in enumerate(document):
            width,height = page.get_size()
            textpage = page.get_textpage()
            for index in range(textpage.count_chars()):
                if raw.FPDFText_GetUnicode(textpage, index) != ord("H"):
                    continue
                x,y = ctypes.c_double(),ctypes.c_double()
                if not raw.FPDFText_GetCharOrigin(textpage,index,ctypes.byref(x),ctypes.byref(y)):
                    continue
                px = x.value * PAGE_WIDTH/width
                py = (height-y.value) * PAGE_HEIGHT/height
                row,col = int(py // CELL_HEIGHT),int(px // CELL_WIDTH)
                if not (0 <= row < ROWS and 0 <= col < COLUMNS):
                    continue
                slot = page_index * ROWS*COLUMNS + row*COLUMNS + col
                if slot >= len(styles) or slot in measurements:
                    continue
                intended = row*CELL_HEIGHT+67
                offset = intended-py
                if abs(offset) > PROBE_FONT_SIZE*.75:
                    continue
                # The PDF font name also exposes substitutions made by Office.
                size = raw.FPDFText_GetFontInfo(textpage,index,None,0,None)
                font_name = ctypes.create_string_buffer(size) if size else None
                if font_name is not None:
                    raw.FPDFText_GetFontInfo(textpage,index,font_name,size,None)
                measurements[slot] = {
                    "style": styles[slot],
                    "rendered_font": font_name.value.decode("utf-8",errors="replace") if font_name else None,
                    "measured_baseline_pt": round(py,4),
                    "target_baseline_pt": intended,
                    "offset_per_point": round(offset/PROBE_FONT_SIZE,7),
                }
            textpage.close()
            page.close()
    return [measurements[k] for k in sorted(measurements)]


def measure_baselines(atoms, work):
    styles = sorted({font_signature(atom["text"]) for atom in atoms if atom["kind"]=="text"})
    if not styles:
        return {"status":"no_text","fonts":[],"unmeasured":[]}
    probe = work / "baseline-probes.pptx"
    make_probe(styles, probe)
    with powerpoint_pdf(probe) as (pdf, version):
        records = measure_probes(pdf,styles)
    measured = {record["style"] for record in records}
    missing = [style for style in styles if style not in measured]
    return {
        "status":"measured" if not missing else ("partial" if records else "unavailable"),
        "powerpoint_version":version, "probe_font_size_pt":PROBE_FONT_SIZE,
        "fonts":records, "unmeasured":missing,
    }
