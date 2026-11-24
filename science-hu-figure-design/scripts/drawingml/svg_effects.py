"""Expand editable SVG effects into solid paths and positioned text runs."""
from __future__ import annotations

import math
import re
import shutil
import subprocess
from bisect import bisect_right
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

import cssselect2
import pathops
import tinycss2
from PIL import ImageColor, ImageFont
from fontTools.misc.transform import Identity, Transform
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.svgLib.path import parse_path

from prepare_geometry_cache import (
    ALLOWED_ATOMS, NUMBER_RE, element_path_data, local_name,
    opacity_value, parse_canvas, parse_style_attribute, parse_transform,
)

NS = "http://www.w3.org/2000/svg"
XLINK = "{http://www.w3.org/1999/xlink}href"
MARKERS = ("marker-start", "marker-mid", "marker-end")
INHERITED = set((
    "fill fill-rule fill-opacity stroke stroke-width stroke-opacity stroke-linecap "
    "stroke-linejoin stroke-miterlimit stroke-dasharray stroke-dashoffset clip-rule "
    "color visibility font-family font-size font-weight font-style text-anchor "
    "dominant-baseline letter-spacing paint-order marker marker-start marker-mid marker-end"
).split())
EFFECTS = {"clipPath", "linearGradient", "radialGradient", "marker", "tspan", "use", "style"}
LENGTH = re.compile(rf"({NUMBER_RE.pattern})(%|px|pt|pc|in|cm|mm|em|ex)?$")
LOCAL_URL = re.compile(r"""url\(\s*['"]?#([^'")\s]+)['"]?\s*\)""")


def style(node):
    values = {local_name(k): v for k, v in node.attrib.items()}
    values.update(parse_style_attribute(node.get("style")))
    return values



def declarations(tokens):
    return [item for item in tinycss2.parse_declaration_list(
        tokens, skip_comments=True, skip_whitespace=True
    ) if item.type == "declaration"]


def inline_styles(root):
    """Resolve embedded selectors and inline style with SVG presentation attributes as defaults."""
    matcher = cssselect2.Matcher()
    stylesheets = [node for node in root.iter() if local_name(node.tag) == "style"]
    for node in stylesheets:
        rules = tinycss2.parse_stylesheet(
            "".join(node.itertext()), skip_whitespace=True, skip_comments=True
        )
        for rule in rules:
            if rule.type != "qualified-rule":
                raise ValueError("SVG @rules and external stylesheets require preprocessing")
            selectors = cssselect2.compile_selector_list(rule.prelude)
            for selector in selectors:
                if selector.pseudo_element is None:
                    matcher.add_selector(selector, declarations(rule.content))
    for wrapper in cssselect2.ElementWrapper.from_xml_root(root).iter_subtree():
        node = wrapper.etree_element
        winners = {}

        def apply(items, specificity, order):
            for index, item in enumerate(items):
                key = (item.important, specificity, order, index)
                if item.lower_name not in winners or winners[item.lower_name][0] <= key:
                    winners[item.lower_name] = (key, tinycss2.serialize(item.value).strip())

        for specificity, order, _, items in matcher.match(wrapper):
            apply(items, (0,*specificity), order)
        apply(declarations(node.attrib.pop("style","")), (1,0,0,0), 0)
        for prop, (_, value) in winners.items():
            node.set(prop, value)

def length(value, extent=1.0, font=16.0):
    match = LENGTH.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f"Unsupported SVG length: {value}")
    number, unit = match.groups()
    factors = {"%": extent / 100, "pt": 4 / 3, "pc": 16, "in": 96,
               "cm": 96 / 2.54, "mm": 96 / 25.4, "em": font, "ex": font / 2}
    result = float(number) * factors.get(unit, 1)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite SVG length: {value}")
    return result


def box(x, y, width, height):
    path = pathops.Path()
    path.moveTo(x, y)
    path.lineTo(x + width, y)
    path.lineTo(x + width, y + height)
    path.lineTo(x, y + height)
    path.close()
    return path


def disk(x, y, radius):
    result = pathops.Path()
    if radius > 0:
        parse_path(f"M{x+radius} {y} A{radius} {radius} 0 1 1 {x-radius} {y} "
                   f"A{radius} {radius} 0 1 1 {x+radius} {y} Z", result.getPen())
    return result


def intersection(shape, clip):
    if clip is None:
        return shape
    if not len(clip) or not len(shape):
        return pathops.Path()
    return pathops.op(shape, clip, pathops.PathOp.INTERSECTION)


def filled(path, rule):
    source = pathops.Path(path)
    if rule == "evenodd":
        source.fillType = pathops.FillType.EVEN_ODD
    return pathops.simplify(source, fix_winding=True)


def color(value, current):
    if value.lower() == "currentcolor":
        value = current
    if value.lower() in {"none", "transparent"}:
        return (0, 0, 0, 0)
    value = re.sub(r",\s*", ",", value)
    if value.startswith("rgba("):
        parts = value[5:-1].split(",")
        if len(parts) == 4:
            return (*ImageColor.getrgb("rgb("+",".join(parts[:3])+")"),
                    round(255*opacity_value(parts[3])))
    return ImageColor.getcolor(value, "RGBA")


def viewport_matrix(view, width, height, align):
    x, y, w, h = view
    sx, sy = width / w, height / h
    modes = align.split()
    if modes and modes[0] == "defer":
        modes.pop(0)
    if modes and modes[0] == "none":
        return Identity.scale(sx, sy).translate(-x, -y)
    token = modes[0] if modes else "xMidYMid"
    if not re.fullmatch(r"x(Min|Mid|Max)Y(Min|Mid|Max)", token):
        raise ValueError(f"Unsupported preserveAspectRatio: {align}")
    scale = max(sx, sy) if "slice" in modes else min(sx, sy)
    factors = {"Min": 0, "Mid": .5, "Max": 1}
    ox = (width - w * scale) * factors[token[1:4]]
    oy = (height - h * scale) * factors[token[5:8]]
    return Identity.translate(ox, oy).scale(scale).translate(-x, -y)


def geometry_data(node, viewport):
    # Resolve SVG geometry lengths before reusing the existing path builder.
    _, _, width, height = viewport
    axes = dict.fromkeys(("x", "x1", "x2", "cx", "width", "rx"), width)
    axes.update(dict.fromkeys(("y", "y1", "y2", "cy", "height", "ry"), height))
    axes["r"] = math.hypot(width, height) / math.sqrt(2)
    normalized = ET.Element(node.tag, node.attrib)
    for key, extent in axes.items():
        if node.get(key) is not None:
            normalized.set(key, str(length(node.get(key), extent)))
    required_dimensions = {
        "rect": ("width", "height"), "circle": ("r",), "ellipse": ("rx", "ry"),
    }
    if any(float(normalized.get(key, 0)) == 0
           for key in required_dimensions.get(local_name(node.tag), ())):
        return ""
    return element_path_data(normalized)


def svg_path(data):
    path = pathops.Path()
    if data:
        parse_path(data, path.getPen())
    return path


def fmt(value):
    return f"{value:.7g}"


def num_list(value):
    values = re.split(r"[\s,]+", value.strip())
    return [part for part in values if part]


def path_segments(data):
    """Return each subpath's segment endpoints and endpoint tangents."""
    pen = RecordingPen()
    if data:
        parse_path(data, pen)
    groups = []
    segments = []
    first = current = (0, 0)
    for command, points in pen.value:
        if command == "moveTo":
            first = current = points[0]
            segments = []
            continue
        if command in {"closePath", "endPath"}:
            if command == "closePath" and first != current:
                segments.append((current, first, (first[0]-current[0], first[1]-current[1]),
                                 (first[0]-current[0], first[1]-current[1])))
            if segments:
                groups.append(segments)
            segments = []
            continue
        end = points[-1]
        start_control = next((p for p in points if p != current), current)
        end_control = next((p for p in reversed((current, *points[:-1])) if p != end), end)
        segments.append((current, end, (start_control[0]-current[0], start_control[1]-current[1]),
                         (end[0]-end_control[0], end[1]-end_control[1])))
        current = end
    if segments:
        groups.append(segments)
    return groups


def direction(vector):
    return math.atan2(vector[1], vector[0])


def bisect_angle(a, b):
    if not any(a):
        return direction(b)
    if not any(b):
        return direction(a)
    a, b = direction(a), direction(b)
    return a + ((b-a+math.pi) % (2*math.pi)-math.pi)/2


@lru_cache(maxsize=256)
def measure_font(family, bold, italic, size):
    names = [item.strip(" '\"") for item in family.split(",") if item.strip()]
    variant = " Bold Italic" if bold and italic else " Bold" if bold else " Italic" if italic else ""
    windows_fonts = Path.home().drive + "/Windows/Fonts"
    candidates = []
    for name in names:
        candidates.extend((
            f"/System/Library/Fonts/Supplemental/{name}{variant}.ttf",
            f"/System/Library/Fonts/Supplemental/{name}.ttf",
            f"{windows_fonts}/{name}{variant}.ttf", f"{name}{variant}.ttf", name,
        ))
    if any(name.lower() in {"arial", "sans-serif"} for name in names):
        suffix = "bi" if bold and italic else "bd" if bold else "i" if italic else ""
        candidates.append(f"{windows_fonts}/arial{suffix}.ttf")
    fc_match = shutil.which("fc-match")
    if fc_match:
        pattern = (names[0] if names else "sans-serif") + ":style=" + (variant.strip() or "Regular")
        result = subprocess.run([fc_match, "--format=%{file}", pattern], capture_output=True, text=True)
        if result.stdout.strip():
            candidates.append(result.stdout.strip())
    candidates.extend(("/System/Library/Fonts/Supplemental/Arial.ttf", "DejaVuSans.ttf"))
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


class Normalizer:
    def __init__(self, root):
        self.root = root
        view = parse_canvas(root)
        widths = [root.get(key, fmt(view[index+2])) for index,key in enumerate(("width","height"))]
        if root.get("viewBox") and any(value.strip().endswith("%") for value in widths):
            widths = [fmt(n) for n in view[2:]]
        width,height = map(length,widths)
        if width <= 0 or height <= 0:
            raise ValueError("SVG canvas dimensions must be positive")
        self.viewport = view if root.get("viewBox") else (0,0,width,height)
        self.frame = (0,0,width,height)
        self.matrix = viewport_matrix(self.viewport,width,height,root.get("preserveAspectRatio",""))
        self.ids = {}
        self.output = ET.Element(f"{{{NS}}}svg", viewBox=" ".join(map(fmt, self.frame)))
        self.stats = dict(gradient_bands=0, clipped_shapes=0, outlined_dashes=0,
                          expanded_markers=0, positioned_text_runs=0)
        for node in root.iter():
            tag = local_name(node.tag)
            if tag in {"script", "foreignObject", "image", "filter", "mask", "pattern", "textPath"}:
                raise ValueError(f"Unsupported SVG element <{tag}> in editable conversion")
            if any(local_name(key).lower().startswith("on") for key in node.attrib):
                raise ValueError("SVG event handlers are unsupported")
            href = node.get("href") or node.get(XLINK)
            if href and not href.startswith("#"):
                raise ValueError("External SVG references are unsupported")
            if node_id := node.get("id"):
                if node_id in self.ids:
                    raise ValueError(f"Duplicate SVG id: {node_id}")
                self.ids[node_id] = node

    def reference(self, value, kind):
        match = LOCAL_URL.fullmatch(value.strip())
        target = self.ids.get(match[1]) if match else None
        if target is None or local_name(target.tag) not in kind:
            raise ValueError(f"Unresolved or unsupported SVG reference: {value}")
        return target

    def linked(self, node, chain):
        key = (node.get("href") or node.get(XLINK) or "")[1:]
        if key in chain or key not in self.ids:
            raise ValueError(f"Circular or unresolved SVG link: #{key}")
        return self.ids[key]

    def emit(self, path, rgba):
        if not len(path) or not rgba[3]:
            return
        path.convertConicsToQuads(.05)
        if not path.area:
            return
        pen = SVGPathPen(None, ntos=fmt)
        path.draw(pen)
        ET.SubElement(self.output, f"{{{NS}}}path", {
            "d": pen.getCommands(), "fill": "#%02x%02x%02x" % rgba[:3],
            "fill-opacity": fmt(rgba[3]/255),
        })

    def bounds(self, node, viewport, chain=()):
        tag = local_name(node.tag)
        if tag in ALLOWED_ATOMS - {"text"}:
            path = svg_path(geometry_data(node, viewport))
            return [path] if len(path) else []
        if tag == "use":
            target = self.linked(node, chain)
            shift = Identity.translate(length(node.get("x", "0"), viewport[2]),
                                       length(node.get("y", "0"), viewport[3]))
            transform = shift.transform(parse_transform(target.get("transform")))
            return [p.transform(*transform) for p in self.bounds(target, viewport, (*chain, target.get("id")))]
        if tag not in {"g", "svg", "clipPath", "symbol", "a"}:
            return []
        paths = []
        for child in node:
            matrix = parse_transform(child.get("transform"))
            paths.extend(p.transform(*matrix) for p in self.bounds(child, viewport, chain))
        return paths

    def clip_geometry(self, node, matrix, viewport, rule, chain):
        spec = style(node)
        if spec.get("display") == "none" or spec.get("visibility") in {"hidden", "collapse"}:
            return pathops.Path()
        matrix = matrix.transform(parse_transform(node.get("transform")))
        tag = local_name(node.tag)
        rule = spec.get("clip-rule", rule)
        if tag in ALLOWED_ATOMS - {"text"}:
            path = filled(svg_path(geometry_data(node, viewport)), rule).transform(*matrix)
        elif tag in {"g", "clipPath"}:
            path = pathops.Path()
            for child in node:
                part = self.clip_geometry(child, matrix, viewport, rule, chain)
                if len(part):
                    path = pathops.op(path, part, pathops.PathOp.UNION) if len(path) else part
        elif tag == "use":
            target = self.linked(node, chain)
            shift = matrix.translate(length(node.get("x","0"), viewport[2]),
                                     length(node.get("y","0"), viewport[3]))
            path = self.clip_geometry(target, shift, viewport, rule, (*chain, target.get("id")))
        elif tag in {"title", "desc", "metadata"}:
            return pathops.Path()
        else:
            raise ValueError(f"Unsupported element inside clipping path: <{tag}>")
        return self.clipped(node, spec, matrix, viewport, path, chain)

    def clipped(self, node, spec, matrix, viewport, previous, chain):
        reference = spec.get("clip-path", "none")
        if reference == "none":
            return previous
        target = self.reference(reference, {"clipPath"})
        key = target.get("id")
        if key in chain:
            raise ValueError(f"Circular SVG clipping reference: #{key}")
        units = target.get("clipPathUnits", "userSpaceOnUse")
        if units == "objectBoundingBox":
            items = self.bounds(node, viewport)
            if not items:
                return pathops.Path()
            bounds = [p.bounds for p in items]
            x, y = (min(v[axis] for v in bounds) for axis in (0, 1))
            right, bottom = (max(v[axis] for v in bounds) for axis in (2, 3))
            if right <= x or bottom <= y:
                return pathops.Path()
            matrix = matrix.translate(x, y).scale(right-x,bottom-y)
            viewport = (0,0,1,1)
        elif units != "userSpaceOnUse":
            raise ValueError(f"Unsupported clipPathUnits: {units}")
        clip = self.clip_geometry(target, matrix, viewport, "nonzero", (*chain, key))
        return intersection(clip, previous)

    def gradient_spec(self, node, chain=()):
        values = {}
        stops = []
        if node.get("href") or node.get(XLINK):
            target = self.linked(node, chain)
            if local_name(target.tag) not in {"linearGradient", "radialGradient"}:
                raise ValueError("Gradient href must reference a gradient")
            values, stops = self.gradient_spec(target, (*chain, target.get("id")))
        values.update(style(node))
        own_stops = [style(child) for child in node if local_name(child.tag) == "stop"]
        return values, own_stops or stops

    @staticmethod
    def interpolate(stops, t):
        index = bisect_right([offset for offset, _ in stops], t)
        if index == 0:
            return stops[0][1]
        if index == len(stops):
            return stops[-1][1]
        (a, left), (b, right) = stops[index-1:index+1]
        fraction = (t-a)/(b-a)
        return tuple(round(x+(y-x)*fraction) for x,y in zip(left,right))

    def gradient(self, target, paint, local_bounds, matrix, viewport, alpha, current):
        node = self.reference(paint, {"linearGradient", "radialGradient"})
        spec, stop_nodes = self.gradient_spec(node, (node.get("id"),))
        if not stop_nodes:
            return
        stops = []
        for item in stop_nodes:
            offset = max(stops[-1][0] if stops else 0, min(1, length(item.get("offset","0"))))
            rgba = color(item.get("stop-color","black"), item.get("color",spec.get("color", current)))
            stops.append((offset, (*rgba[:3], round(rgba[3]*alpha*opacity_value(item.get("stop-opacity"))))))
        units = spec.get("gradientUnits", "objectBoundingBox")
        if units == "objectBoundingBox":
            x, y, right, bottom = local_bounds
            if right <= x or bottom <= y:
                return
            matrix = matrix.translate(x,y).scale(right-x,bottom-y)
            viewport = (0,0,1,1)
        elif units != "userSpaceOnUse":
            raise ValueError(f"Unsupported gradientUnits: {units}")
        matrix = matrix.transform(parse_transform(spec.get("gradientTransform")))
        if abs(matrix.xx*matrix.yy-matrix.xy*matrix.yx) < 1e-12:
            return
        spread = spec.get("spreadMethod", "pad")
        if spread not in {"pad", "repeat", "reflect"}:
            raise ValueError(f"Unsupported spreadMethod: {spread}")
        radial = local_name(node.tag) == "radialGradient"

        def position(key, default, axis):
            raw = spec.get(key, default)
            return length(raw, viewport[axis+2]) + (viewport[axis] if raw.strip().endswith("%") else 0)

        if radial:
            x, y = position("cx","50%",0), position("cy","50%",1)
            radius_extent = math.hypot(*viewport[2:])/math.sqrt(2)
            radius = length(spec.get("r","50%"), radius_extent)
            inner = length(spec.get("fr","0"), radius_extent)
            fx = position("fx",spec.get("cx","50%"),0)
            fy = position("fy",spec.get("cy","50%"),1)
            if radius <= 0:
                self.emit(target, stops[-1][1])
                return
            if not 0 <= inner < radius:
                raise ValueError("Radial gradient requires 0 ≤ fr < r")
            distance = math.hypot(fx-x,fy-y)
            if distance >= radius-inner:
                proportion = .999*(radius-inner)/distance
                fx,fy=x+(fx-x)*proportion,y+(fy-y)*proportion
            local = target.transform(*matrix.inverse())
            left, top, right, bottom = local.bounds
            reach = max(math.hypot(px-fx,py-fy) for px in (left,right) for py in (top,bottom))
            reach /= radius-inner-math.hypot(x-fx,y-fy)
            low, high = 0, max(1, math.ceil(reach))
        else:
            x, y = position("x1","0%",0), position("y1","0%",1)
            dx, dy = position("x2","100%",0)-x, position("y2","0%",1)-y
            if not math.hypot(dx,dy):
                self.emit(target, stops[-1][1])
                return
            matrix = matrix.transform(Transform(dx,dy,-dy,dx,x,y))
            left, top, right, bottom = target.transform(*matrix.inverse()).bounds
            low, high = math.floor(left), math.ceil(right)

        steps = sorted({i/64 for i in range(65)} | {offset for offset,_ in stops})
        intervals = []
        if spread == "pad":
            intervals = [(lo,hi,(lo+hi)/2) for lo,hi in zip(steps,steps[1:])]
            if low < 0:
                intervals.insert(0,(low,0,-1))
            if high > 1:
                intervals.append((1,high,2))
        else:
            if high-low > 64:
                raise ValueError("SVG repeats its gradient more than 64 times; simplify the gradient")
            for index in range(low,high):
                phase = sorted(1-u for u in steps) if spread == "reflect" and index%2 else steps
                for lo,hi in zip(phase,phase[1:]):
                    t=(lo+hi)/2
                    intervals.append((index+lo,index+hi,1-t if spread == "reflect" and index%2 else t))

        opaque = all(rgba[3] == 255 for _,rgba in stops)
        pixels_per_unit = min(math.hypot(matrix.xx,matrix.xy),math.hypot(matrix.yx,matrix.yy))
        if radial:
            pixels_per_unit *= radius-inner
        seam = .30 / pixels_per_unit if opaque and pixels_per_unit else 0
        if radial and inner:
            core = intersection(target, disk(fx,fy,inner+(radius-inner)*seam).transform(*matrix))
            if len(core):
                self.emit(core, stops[0][1])
                self.stats["gradient_bands"] += 1
        for lo,hi,t in intervals:
            if radial:
                if spread == "pad" and lo >= 1:
                    outer = target
                else:
                    outer_edge = hi + min(seam,(hi-lo)/2)
                    outer = disk(fx+(x-fx)*outer_edge,fy+(y-fy)*outer_edge,
                                 inner+(radius-inner)*outer_edge).transform(*matrix)
                if lo > 0 or inner > 0:
                    hole = disk(fx+(x-fx)*lo,fy+(y-fy)*lo,inner+(radius-inner)*lo).transform(*matrix)
                    outer = pathops.op(outer,hole,pathops.PathOp.DIFFERENCE)
                band = outer
            else:
                band = box(lo,top-1,hi-lo+min(seam,(hi-lo)/2),bottom-top+2).transform(*matrix)
            piece = intersection(target, band)
            if len(piece):
                self.emit(piece,self.interpolate(stops,t))
                self.stats["gradient_bands"] += 1

    def paint(self, path, value, bounds, matrix, viewport, clip, opacity, current):
        if not len(path) or value == "none" or opacity <= 0:
            return
        target = intersection(path, clip)
        if not len(target):
            return
        if value.strip().startswith("url("):
            self.gradient(target,value,bounds,matrix,viewport,opacity,current)
        else:
            rgba = color(value,current)
            self.emit(target,(*rgba[:3],round(rgba[3]*opacity)))

    def markers(self, data, spec, matrix, viewport, clip, alpha, stroke_width, chain):
        if not any(spec.get(key,spec.get("marker","none")) != "none" for key in MARKERS):
            return
        for segments in path_segments(data):
            first, last = segments[0], segments[-1]
            placements = [(0,first[0],direction(first[2]))]
            placements.extend((1,a[1],bisect_angle(a[3],b[2])) for a,b in zip(segments,segments[1:]))
            placements.append((2,last[1],direction(last[3])))
            for index, (x,y), theta in placements:
                value = spec.get(MARKERS[index],spec.get("marker","none"))
                if value == "none":
                    continue
                marker = self.reference(value,{"marker"})
                key = marker.get("id")
                if key in chain:
                    raise ValueError(f"Circular SVG marker: #{key}")
                orient = marker.get("orient","0")
                if orient == "auto-start-reverse" and index == 0:
                    theta += math.pi
                elif orient not in {"auto","auto-start-reverse"}:
                    angle = re.fullmatch(rf"({NUMBER_RE.pattern})(deg|rad|grad|turn)?",orient)
                    if not angle:
                        raise ValueError(f"Unsupported marker orientation: {orient}")
                    value,unit=angle.groups()
                    theta=float(value)*{"deg":math.pi/180,"rad":1,"grad":math.pi/200,"turn":2*math.pi,None:math.pi/180}[unit]
                width = length(marker.get("markerWidth","3"), viewport[2])
                height = length(marker.get("markerHeight","3"), viewport[3])
                if width <= 0 or height <= 0:
                    continue
                units = marker.get("markerUnits","strokeWidth")
                if units not in {"strokeWidth","userSpaceOnUse"}:
                    raise ValueError(f"Unsupported markerUnits: {units}")
                scale = stroke_width if units == "strokeWidth" else 1
                if scale <= 0:
                    continue
                view = parse_canvas(marker) if marker.get("viewBox") else (0,0,width,height)
                content = viewport_matrix(view,width,height,marker.get("preserveAspectRatio",""))
                ref = content.transformPoint((
                    length(marker.get("refX","0"),view[2]),length(marker.get("refY","0"),view[3])
                ))
                frame = matrix.translate(x,y).rotate(theta).scale(scale).translate(-ref[0],-ref[1])
                if style(marker).get("overflow") != "visible":
                    marker_clip = intersection(box(0,0,width,height).transform(*frame),clip)
                else:
                    marker_clip = clip
                marker_style = {k:v for k,v in style(marker).items() if k in INHERITED}
                for child in marker:
                    self.walk(child,marker_style,frame.transform(content),view,marker_clip,alpha,
                              (*chain,key),context=spec)
                self.stats["expanded_markers"] += 1

    def shape(self,node,spec,matrix,viewport,clip,alpha,chain,context):
        data = geometry_data(node,viewport)
        profile = svg_path(data)
        if not len(profile):
            return
        bounds = profile.bounds
        current = spec.get("color","black")
        context = context or {}
        fill = spec.get("fill","black")
        stroke = spec.get("stroke","none")
        fill = context.get(fill[8:], "none") if fill in {"context-fill","context-stroke"} else fill
        stroke = context.get(stroke[8:], "none") if stroke in {"context-fill","context-stroke"} else stroke
        extent = math.hypot(*viewport[2:])/math.sqrt(2)
        width = length(spec.get("stroke-width","1"),extent)
        order = [k for k in spec.get("paint-order","").split() if k in {"fill","stroke","markers"}]
        order += [k for k in ("fill","stroke","markers") if k not in order]
        for part in order:
            if part == "fill" and fill != "none":
                path = filled(profile,spec.get("fill-rule","nonzero")).transform(*matrix)
                self.paint(path,fill,bounds,matrix,viewport,clip,
                           alpha*opacity_value(spec.get("fill-opacity")),current)
            elif part == "stroke" and stroke != "none" and width > 0:
                caps = {"butt":pathops.LineCap.BUTT_CAP,"round":pathops.LineCap.ROUND_CAP,
                        "square":pathops.LineCap.SQUARE_CAP}
                joins = {"miter":pathops.LineJoin.MITER_JOIN,"round":pathops.LineJoin.ROUND_JOIN,
                         "bevel":pathops.LineJoin.BEVEL_JOIN}
                dash = spec.get("stroke-dasharray","none")
                dashes = [] if dash == "none" else [length(part,extent) for part in num_list(dash)]
                if any(size < 0 for size in dashes):
                    raise ValueError("SVG dash intervals must be nonnegative")
                if len(dashes)%2:
                    dashes *= 2
                if not sum(dashes):
                    dashes = []
                phase = length(spec.get("stroke-dashoffset","0"),extent)
                outline = pathops.Path(profile)
                # Non-scaling strokes are applied after mapping to the output viewport.
                non_scaling = spec.get("vector-effect") == "non-scaling-stroke"
                if non_scaling:
                    outline = outline.transform(*matrix)
                outline.stroke(width,caps[spec.get("stroke-linecap","butt")],
                               joins[spec.get("stroke-linejoin","miter")],
                               float(spec.get("stroke-miterlimit",4)),dashes or None,phase)
                outline.convertConicsToQuads(.05)
                outline = filled(outline,"nonzero")
                if not non_scaling:
                    outline = outline.transform(*matrix)
                self.paint(outline,stroke,bounds,matrix,viewport,clip,
                           alpha*opacity_value(spec.get("stroke-opacity")),current)
                self.stats["outlined_dashes"] += bool(dashes)
            elif part == "markers":
                self.markers(data,spec,matrix,viewport,clip,alpha,width,chain)

    def text(self,node,spec,matrix,viewport,clip,opacity):
        if abs(matrix.xx*matrix.yy-matrix.xy*matrix.yx) < 1e-12:
            return
        xs,ys = math.hypot(matrix.xx,matrix.xy),math.hypot(matrix.yx,matrix.yy)
        if abs(xs-ys) > max(xs,ys)*.001 or abs(matrix.xx*matrix.yx+matrix.xy*matrix.yy) > xs*ys*.001:
            raise ValueError("Editable SVG text with skew or nonuniform scaling requires manual layout")
        if matrix.xx*matrix.yy-matrix.xy*matrix.yx < 0:
            raise ValueError("Reflected SVG text requires manual layout")

        chunks = []
        cursor = [0.0,0.0]
        pending = []
        preserve = node.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"

        def flush():
            if pending:
                chunks.append(pending[:])
                pending.clear()

        def enter(element, props, parent_size, shift, alpha, start=False):
            local = style(element)
            if local.get("display") == "none":
                return
            if not start and (element.get("transform") or local.get("clip-path")):
                raise ValueError("Transform or clipping on tspan requires a separate text element")
            if any(element.get(key) for key in ("rotate","textLength","lengthAdjust")):
                raise ValueError("Per-character rotation and textLength require positioned SVG text runs")
            raw_size = local.get("font-size", str(parent_size))
            fontsize = parent_size if raw_size == "inherit" else length(raw_size,parent_size,parent_size)
            if fontsize <= 0:
                return
            if local.get("x") is not None or local.get("y") is not None:
                flush()
            for index,(key,relative) in enumerate((("x","dx"),("y","dy"))):
                extent = viewport[index+2]
                if key in local:
                    cursor[index]=length(local[key],extent,fontsize)
                if relative in local:
                    cursor[index]+=length(local[relative],extent,fontsize)
            baseline = local.get("baseline-shift","baseline")
            if baseline == "sub":
                shift -= parent_size*.25
            elif baseline == "super":
                shift += parent_size*.36
            elif baseline != "baseline":
                shift += length(baseline,fontsize,fontsize)
            parent_props = dict(props)
            parent_props.update({k:v for k,v in local.items() if k in INHERITED and v != "inherit"})
            if not start:
                alpha *= opacity_value(local.get("opacity"))

            def append(value):
                if not value:
                    return
                if not preserve:
                    value = re.sub(r"[ \t\r\n]+"," ",value)
                    if not pending or pending[-1]["text"].endswith(" "):
                        value = value.lstrip(" ")
                if not value:
                    return
                weight = parent_props.get("font-weight","normal")
                bold = weight in {"bold","bolder"} or (weight.isdigit() and int(weight)>=600)
                italic = parent_props.get("font-style","normal") in {"italic","oblique"}
                family = parent_props.get("font-family","Arial")
                resolution = max(1,round(fontsize*8))
                font = measure_font(family,bold,italic,resolution)
                letter_space = length(parent_props.get("letter-spacing","0").replace("normal","0"),fontsize,fontsize)
                advance = font.getlength(value)/8 + letter_space*len(value)
                baseline_adjustment = {
                    "middle": .26, "central": .32, "hanging": .65,
                    "text-before-edge": .82, "text-after-edge": -.20,
                }.get(parent_props.get("dominant-baseline"),0) * fontsize
                visible = parent_props.get("visibility","visible") not in {"hidden","collapse"}
                pending.append(dict(text=value,x=cursor[0],y=cursor[1]-shift+baseline_adjustment,width=advance,
                                    size=fontsize,anchor=parent_props.get("text-anchor","start"),
                                    family=family,bold=bold,italic=italic,visible=visible,
                                    props=parent_props,opacity=alpha,letter_spacing=letter_space))
                cursor[0]+=advance

            append(element.text)
            for child in element:
                child_tag = local_name(child.tag)
                if child_tag == "tspan":
                    enter(child,parent_props,fontsize,shift,alpha)
                elif child_tag not in {"title","desc","metadata"}:
                    raise ValueError(f"Unsupported SVG text child <{child_tag}>")
                append(child.tail)

        default_size = length(spec.get("font-size","16"),16,16) if "font-size" not in style(node) else (
            float(spec.get("_parent_font_size","16"))
        )
        enter(node,spec,default_size,0.0,opacity,start=True)
        flush()
        for chunk in chunks:
            tail = chunk[-1]
            if not preserve and tail["text"].endswith(" "):
                tail["text"] = tail["text"].rstrip(" ")
                font = measure_font(tail["family"],tail["bold"],tail["italic"],max(1,round(tail["size"]*8)))
                tail["width"] -= font.getlength(" ")/8
            advance = max(item["x"]+item["width"] for item in chunk)-chunk[0]["x"]
            fraction = {"start":0,"middle":.5,"end":1}.get(chunk[0]["anchor"],0)
            for item in chunk:
                if not item["text"] or not item["visible"]:
                    continue
                x,y,size = item["x"]-fraction*advance,item["y"],item["size"]
                if clip is not None:
                    envelope = box(x,y-size*.88,max(.01,item["width"]),size*1.10).transform(*matrix)
                    portion = intersection(envelope,clip)
                    if not len(portion):
                        continue
                    if abs(envelope.area-portion.area) > max(.03,envelope.area*.015):
                        raise ValueError("Partially clipped text cannot remain editable; reposition its SVG text runs")
                props=item["props"]
                rgba = color(props.get("fill","black"),props.get("color","black"))
                opacity = rgba[3]/255*item["opacity"]*opacity_value(props.get("fill-opacity"))
                if not opacity:
                    continue
                if props.get("stroke","none") != "none":
                    raise ValueError("Stroked text requires manual editable layout")
                element = ET.SubElement(self.output,f"{{{NS}}}text",{
                    "x":fmt(x),"y":fmt(y),"font-size":fmt(size),
                    "font-family":item["family"],"font-weight":"bold" if item["bold"] else "normal",
                    "font-style":"italic" if item["italic"] else "normal","fill":"#%02x%02x%02x" % rgba[:3],
                    "fill-opacity":fmt(opacity),"letter-spacing":fmt(item["letter_spacing"]),
                    "transform":"matrix("+" ".join(map(fmt,matrix))+")",
                })
                element.text=item["text"]
                self.stats["positioned_text_runs"] += 1

    def walk(self,node,inherited,matrix,viewport,clip,opacity,chain=(),context=None):
        tag = local_name(node.tag)
        if tag in {"title","desc","metadata","style","defs","linearGradient","radialGradient","clipPath","marker","symbol"}:
            return
        spec = style(node)
        if spec.get("display") == "none":
            return
        matrix = matrix.transform(parse_transform(node.get("transform")))
        alpha = opacity*opacity_value(spec.get("opacity"))
        if alpha <= 0:
            return
        parent_size = length(inherited.get("font-size","16"),16,16)
        props = dict(inherited)
        props.update({k:v for k,v in spec.items() if v != "inherit"})
        props["_parent_font_size"]=parent_size
        font_size = props.get("font-size",str(parent_size))
        props["font-size"] = fmt(length(font_size,parent_size,parent_size))
        if tag != "text" and props.get("visibility") in {"hidden","collapse"} and tag in ALLOWED_ATOMS:
            return
        previous = clip
        clip = self.clipped(node,spec,matrix,viewport,clip,chain)
        if clip is not previous:
            self.stats["clipped_shapes"] += 1
        if clip is not None and not len(clip):
            return
        if tag == "text":
            self.text(node,props,matrix,viewport,clip,alpha)
        elif tag in ALLOWED_ATOMS:
            self.shape(node,props,matrix,viewport,clip,alpha,chain,context)
        elif tag == "use":
            target = self.linked(node,chain)
            if local_name(target.tag) == "symbol":
                target = ET.Element(f"{{{NS}}}svg",target.attrib)
                target.extend(self.linked(node,chain))
                for key in ("width","height"):
                    if key in spec:
                        target.set(key,spec[key])
            shift = matrix.translate(length(spec.get("x","0"),viewport[2]),
                                     length(spec.get("y","0"),viewport[3]))
            self.walk(target,{k:v for k,v in props.items() if k in INHERITED},shift,viewport,clip,alpha,
                      (*chain,target.get("id")),context)
        elif tag in {"svg","g","a"}:
            if tag == "svg" and node is not self.root:
                width = length(spec.get("width","100%"),viewport[2])
                height = length(spec.get("height","100%"),viewport[3])
                if width <= 0 or height <= 0:
                    return
                x = length(spec.get("x","0"),viewport[2])
                y = length(spec.get("y","0"),viewport[3])
                viewport = parse_canvas(node) if node.get("viewBox") else (0,0,width,height)
                matrix = matrix.translate(x,y)
                if spec.get("overflow") != "visible":
                    clip = intersection(box(0,0,width,height).transform(*matrix),clip)
                matrix = matrix.transform(viewport_matrix(viewport,width,height,spec.get("preserveAspectRatio","")))
            for child in node:
                self.walk(child,{k:v for k,v in props.items() if k in INHERITED},matrix,viewport,clip,alpha,chain,context)
        else:
            raise ValueError(f"Unsupported SVG element <{tag}> in editable conversion")


def requires_expansion(root):
    for node in root.iter():
        if local_name(node.tag) in EFFECTS or node.get("class"):
            return True
        spec = style(node)
        if any(spec.get(key,"none")!="none" for key in (*MARKERS,"marker","stroke-dasharray","clip-path")):
            return True
        if spec.get("fill-rule") == "evenodd":
            return True
        if local_name(node.tag) == "svg" and node is not root:
            return True
        if local_name(node.tag) == "text" and any(key in spec for key in ("dx","dy","baseline-shift","dominant-baseline")):
            return True
    return False


def expand_svg(source: Path, destination: Path):
    """Return None for ordinary SVGs or a count of expanded effects."""
    data = source.read_bytes()
    if re.search(br"<!\s*(DOCTYPE|ENTITY)",data,re.I):
        raise ValueError("SVG document types and entities are unsupported")
    root = ET.fromstring(data)
    if not requires_expansion(root):
        return None
    try:
        inline_styles(root)
        normalizer = Normalizer(root)
        normalizer.walk(root,{},normalizer.matrix,normalizer.viewport,None,1.0)
    except (cssselect2.SelectorError,pathops.PathOpsError,KeyError) as error:
        raise ValueError(f"Cannot expand SVG effects: {error}") from error
    ET.register_namespace("",NS)
    ET.ElementTree(normalizer.output).write(destination,encoding="utf-8",xml_declaration=True)
    return normalizer.stats
