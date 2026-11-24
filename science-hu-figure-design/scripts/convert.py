#!/usr/bin/env python3
"""Trace raster figures locally and export editable DrawingML shapes."""
from __future__ import annotations

import argparse
import csv
import json
from io import StringIO
import math
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import vtracer
from PIL import Image, ImageFilter, ImageOps
from pptx import Presentation

SCRIPTS = Path(__file__).resolve().parent
BACKEND = SCRIPTS / "drawingml"
SVG_NS = "http://www.w3.org/2000/svg"


def run_backend(script: str, *arguments: object) -> None:
    result = subprocess.run(
        [sys.executable, str(BACKEND / script), *map(str, arguments)],
        stdout=subprocess.PIPE, text=True,
    )
    if result.returncode:
        raise ValueError(result.stdout.strip() or f"{script} exited with status {result.returncode}")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bounds(box, width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = map(float, box)
    if not all(map(math.isfinite, (x, y, w, h))) or w <= 0 or h <= 0:
        raise ValueError(f"Invalid text bbox: {box}")
    return (
        max(0, math.floor(x)), max(0, math.floor(y)),
        min(width, math.ceil(x + w)), min(height, math.ceil(y + h)),
    )


def label_mask(rgba: np.ndarray, box) -> tuple[tuple[int, int, int, int], np.ndarray]:
    height, width = rgba.shape[:2]
    left, top, right, bottom = bounds(box, width, height)
    if right <= left or bottom <= top:
        raise ValueError(f"Text bbox falls outside the image: {box}")

    outer_left, outer_top = max(left - 3, 0), max(top - 3, 0)
    outer_right, outer_bottom = min(right + 3, width), min(bottom + 3, height)
    surroundings = rgba[outer_top:outer_bottom, outer_left:outer_right]
    ring = np.ones(surroundings.shape[:2], dtype=bool)
    ring[top - outer_top:bottom - outer_top, left - outer_left:right - outer_left] = False
    region = rgba[top:bottom, left:right]
    if not ring.any():
        return (left, top, right, bottom), np.ones(region.shape[:2], dtype=bool)
    background = np.median(surroundings[ring], axis=0)
    distance = np.linalg.norm(region.astype(np.float32) - background, axis=2)
    return (left, top, right, bottom), distance > 18


def tesseract_records(command: str, path: Path, size, languages: str | None) -> list[dict]:
    language_map = {"en-US": "eng", "en": "eng", "zh-Hans": "chi_sim", "zh-Hant": "chi_tra"}
    requested = [language_map.get(code.strip(), code.strip())
                 for code in languages.replace("+", ",").split(",")] if languages else ["eng"]
    if not languages:
        installed = subprocess.check_output([command, "--list-langs"], encoding="utf-8").splitlines()
        requested.extend(code for code in ("chi_sim", "chi_tra") if code in installed)
    output = subprocess.check_output(
        [command, str(path), "-l", "+".join(requested), "--psm", "11", "tsv"],
        encoding="utf-8",
    )
    groups = {}
    for row in csv.DictReader(StringIO(output), delimiter="\t"):
        if row["level"] != "5" or not row["text"].strip() or float(row["conf"]) < 0:
            continue
        key = tuple(row[field] for field in ("page_num", "block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append(row)

    width, height = size
    records = []
    for words in groups.values():
        left = min(int(row["left"]) for row in words)
        top = min(int(row["top"]) for row in words)
        right = max(int(row["left"]) + int(row["width"]) for row in words)
        bottom = max(int(row["top"]) + int(row["height"]) for row in words)
        records.append({
            "content": " ".join(row["text"].strip() for row in words),
            "confidence": sum(float(row["conf"]) for row in words) / (100 * len(words)),
            "bbox": [left / width, top / height, (right - left) / width, (bottom - top) / height],
        })
    return records


def ocr_records(path: Path, size, languages: str | None) -> list[dict]:
    swift = shutil.which("swift") if sys.platform == "darwin" else None
    if swift and subprocess.run(["xcode-select", "-p"], capture_output=True).returncode == 0:
        command = [swift, str(SCRIPTS / "recognize.swift"), str(path)]
        if languages:
            command.append(languages)
        result = subprocess.run(command, capture_output=True, encoding="utf-8")
        if result.returncode == 0:
            return json.loads(result.stdout)
        if languages:
            raise ValueError(result.stderr.strip() or "macOS text recognition failed.")
    tesseract = shutil.which("tesseract")
    if tesseract:
        return tesseract_records(tesseract, path, size, languages)
    raise ValueError(
        "No local OCR is available. Supply --text-manifest (see references/correction.md), "
        "or use --no-text for artwork without labels."
    )


def recognize(path: Path, rgba: np.ndarray, languages: str | None) -> list[dict]:
    height, width = rgba.shape[:2]
    records = ocr_records(path, (width, height), languages)
    elements = []
    for record in records:
        if record["confidence"] < 0.45 or not record["content"].strip():
            continue
        x, y, w, h = [v * span for v, span in zip(record["bbox"], (width, height, width, height))]
        box = [x, y, w, h]
        (left, top, right, bottom), mask = label_mask(rgba, box)
        pixels = rgba[top:bottom, left:right, :3][mask]
        color = np.median(pixels, axis=0).astype(int) if pixels.size else (0, 0, 0)
        elements.append({
            "id": f"local-ocr-{len(elements) + 1}",
            "content": record["content"], "confidence": record["confidence"],
            "coordinate_space": "pixels", "bbox": box,
            "x": x, "y": y + h * 0.97, "font_size": h * 1.16,
            "fill": "#" + "".join(f"{c:02x}" for c in color),
        })
    return elements


def fill_mask(region: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fill glyph pixels from neighbors, one layer inward at a time."""
    pixels = region.astype(np.float32)
    known = ~mask
    while not known.all():
        neighbors = np.pad(known, 1)
        padded = np.pad(pixels * known[:, :, None], ((1, 1), (1, 1), (0, 0)))
        count = (
            neighbors[:-2, 1:-1].astype(np.uint8) + neighbors[2:, 1:-1]
            + neighbors[1:-1, :-2] + neighbors[1:-1, 2:]
        )
        border = ~known & (count > 0)
        if not border.any():
            raise ValueError("Text mask has no surrounding pixels. Supply --clean-image.")
        total = padded[:-2, 1:-1] + padded[2:, 1:-1] + padded[1:-1, :-2] + padded[1:-1, 2:]
        pixels[border] = total[border] / count[border, None]
        known |= border
    return np.rint(pixels).astype(np.uint8)


def remove_text(rgba: np.ndarray, elements: list[dict]) -> Image.Image:
    cleaned = rgba.copy()
    height, width = rgba.shape[:2]
    for element in elements:
        if "bbox" not in element:
            raise ValueError("Each text element needs a pixel bbox [x, y, width, height], or supply --clean-image.")
        (left, top, right, bottom), glyphs = label_mask(rgba, element["bbox"])
        x1, y1 = max(0, left - 3), max(0, top - 3)
        x2, y2 = min(width, right + 3), min(height, bottom + 3)
        mask = np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        mask[top - y1:bottom - y1, left - x1:right - x1] = glyphs
        dilated = np.asarray(Image.fromarray(mask).filter(ImageFilter.MaxFilter(3))) > 0
        region = cleaned[y1:y2, x1:x2]
        region[:] = fill_mask(region, dilated)
    return Image.fromarray(cleaned)


def raster_to_svg(args, job: Path) -> tuple[Path, Path]:
    with Image.open(args.input_image) as source:
        original = ImageOps.exif_transpose(source).convert("RGBA")
    rgba = np.asarray(original).copy()
    # Ignore invisible RGB values so the OCR mask excludes transparent pixels.
    rgba[rgba[:, :, 3] == 0, :3] = 0
    manifest = {
        "schema_version": "1.0",
        "source_canvas": {"width": original.width, "height": original.height},
        "text_elements": [],
    }
    if args.text_manifest:
        manifest = json.loads(args.text_manifest.read_text(encoding="utf-8-sig"))
        canvas = manifest.get("source_canvas", {})
        if (canvas.get("width"), canvas.get("height")) != original.size:
            raise ValueError("The manifest's source canvas must match the original image.")
    elif not args.no_text:
        normalized = job / ".source.png"
        original.save(normalized)
        manifest["text_elements"] = recognize(normalized, rgba, args.languages)
        normalized.unlink()
    items = manifest["text_elements"]
    manifest_path = job / "text-manifest.json"
    write_json(manifest_path, manifest)

    if args.clean_image:
        with Image.open(args.clean_image) as source:
            cleaned = ImageOps.exif_transpose(source).convert("RGBA")
        if cleaned.size != original.size:
            raise ValueError("--clean-image must have the same size as the source.")
    else:
        cleaned = remove_text(rgba, items)
    clean_path = job / "cleaned.png"
    cleaned.save(clean_path)
    raw_svg = job / "paths.svg"
    vtracer.convert_image_to_svg_py(
        str(clean_path), str(raw_svg),
        colormode="color", hierarchical=args.layers, mode="spline",
        filter_speckle=args.speckle, color_precision=args.color_precision,
    )
    if not any(node.tag == f"{{{SVG_NS}}}path" for node in ET.parse(raw_svg).iter()) and not items:
        raise ValueError("Vectorization produced no visible paths or text.")
    return raw_svg, manifest_path


def verify_pptx(deck: Path, slide_index: int) -> dict:
    presentation = Presentation(str(deck))
    slide = presentation.slides[slide_index - 1]
    slide = ET.fromstring(slide.element.xml)
    ns = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    }
    return {
        "native_paths_on_slide": len(slide.findall(".//a:custGeom", ns)),
        "editable_text_on_slide": [node.text for node in slide.findall(".//p:sp/p:txBody//a:t", ns)],
        "picture_objects_on_slide": len(slide.findall(".//p:pic", ns)),
    }


def optional_check(label, operation):
    try:
        if sys.platform not in {"darwin", "win32"}:
            raise RuntimeError("This check requires desktop PowerPoint on macOS or Windows.")
        return operation()
    except (OSError, RuntimeError, ValueError, ImportError) as error:
        print(f"{label} unavailable: {error}", file=sys.stderr)
        return {"status": "unavailable", "reason": str(error)}


def convert(args, job: Path) -> None:
    master = job / "artwork.svg"
    if args.input_image:
        raw_svg, manifest = raster_to_svg(args, job)
        run_backend("merge_live_text.py", "--input-svg", raw_svg,
                    "--text-manifest", manifest, "--output-svg", master)
    else:
        shutil.copyfile(args.input_svg, master)

    if any(node.tag.split("}")[-1] in {"image", "foreignObject"} for node in ET.parse(master).iter()):
        raise ValueError("The source SVG contains an embedded image or foreignObject.")

    cache = job / ".cache"
    cache.mkdir()
    sys.path.insert(0,str(BACKEND))
    from svg_effects import expand_svg

    expanded = cache / "expanded.svg"
    effects = expand_svg(master,expanded)
    geometry_source = expanded if effects is not None else master
    run_backend("prepare_geometry_cache.py", "--input", geometry_source,
                "--output-dir", cache, "--job-id", "local")
    geometry = cache / "geometry-cache.json"
    geometry_data = json.loads(geometry.read_text(encoding="utf-8"))
    atoms = geometry_data["atoms"]
    expected_text = [atom["text"]["contents"] for atom in atoms if atom["kind"] == "text"]
    expected_paths = sum(len(atom["paintParts"]) for atom in atoms if atom["kind"] == "path")
    deck = job / "artwork.pptx"
    options = []
    if args.input_pptx:
        options = ["--input-pptx", args.input_pptx, "--slide-index", args.slide_index]
    calibration = None
    if args.calibrate_fonts:
        def calibration_check():
            from powerpoint_preview import measure_baselines
            return measure_baselines(atoms, cache)

        calibration = optional_check("Font baseline calibration", calibration_check)
        baseline_file = job / "font-baselines.json"
        write_json(baseline_file, calibration)
        if calibration.get("fonts"):
            options.extend(["--font-baselines", baseline_file])
    run_backend("write_pptx.py", "--geometry-cache", geometry,
                "--output-pptx", deck, *options)
    shutil.rmtree(cache)
    report = verify_pptx(deck, args.slide_index)
    before = verify_pptx(args.input_pptx, args.slide_index) if args.slide_index else {
        "native_paths_on_slide": 0,
        "editable_text_on_slide": [],
        "picture_objects_on_slide": 0,
    }
    report["new_path_count"] = report["native_paths_on_slide"] - before["native_paths_on_slide"]
    new_text = report["editable_text_on_slide"][len(before["editable_text_on_slide"]):]
    report["new_text_count"] = len(new_text)
    if report["new_path_count"] != expected_paths or new_text != expected_text:
        raise ValueError("The exported slide does not match the editable path and text counts.")
    if report["picture_objects_on_slide"] != before["picture_objects_on_slide"]:
        raise ValueError("Unexpected picture objects in the output slide.")
    if effects is not None:
        report["expanded_svg_effects"] = effects
    if calibration is not None:
        report["font_calibration"] = {
            "status": calibration["status"],
            "measurements": "font-baselines.json",
            "applied_font_styles": len(calibration.get("fonts", [])),
        }
    if args.preview:
        slide_index = args.slide_index or len(Presentation(str(deck)).slides)

        def preview_check():
            from powerpoint_preview import render_comparison
            return render_comparison(master, deck, slide_index, geometry_data, job, args.input_pptx)

        report["powerpoint_render"] = optional_check("PowerPoint preview", preview_check)
    write_json(job / "verification.json", report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-image", type=Path)
    source.add_argument("--input-svg", type=Path)
    text = parser.add_mutually_exclusive_group()
    text.add_argument("--no-text", action="store_true")
    text.add_argument("--text-manifest", type=Path)
    parser.add_argument("--clean-image", type=Path, help="Pair a manually cleaned image with --text-manifest.")
    parser.add_argument("--languages", help="OCR language codes, comma-separated.")
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for this conversion.")
    parser.add_argument("--input-pptx", type=Path)
    parser.add_argument("--slide-index", type=int, default=0, help="Existing slide, 1-based. 0 appends.")
    parser.add_argument("--layers", choices=["stacked", "cutout"], default="stacked")
    parser.add_argument("--speckle", type=int, choices=range(17), default=2)
    parser.add_argument("--color-precision", type=int, choices=range(1, 9), default=6)
    parser.add_argument("--preview", action="store_true",
                        help="Render through desktop PowerPoint and create an SVG comparison PNG.")
    parser.add_argument("--calibrate-fonts", action="store_true",
                        help="Measure and apply per-font baseline offsets with desktop PowerPoint.")
    args = parser.parse_args()
    if args.slide_index < 0 or (args.slide_index and not args.input_pptx):
        parser.error("--slide-index must be positive and paired with --input-pptx, or zero")
    if args.input_svg and (args.no_text or args.text_manifest or args.clean_image or args.languages):
        parser.error("OCR options require --input-image")
    if args.clean_image and not args.text_manifest:
        parser.error("--clean-image requires --text-manifest")
    if args.languages and (args.no_text or args.text_manifest):
        parser.error("--languages applies to automatic OCR")
    output = args.output_dir.resolve()
    if output.exists():
        parser.error(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".science-hu-", dir=output.parent) as tmp:
            job = Path(tmp) / "result"
            job.mkdir()
            convert(args, job)
            job.rename(output)
    except (ValueError, OSError, ET.ParseError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Conversion failed: {error}\n")
    print(output / "artwork.pptx")


if __name__ == "__main__":
    main()
