"""Draw explainer diagrams from declarative specs as inline SVG.

The author names nodes, messages, entities and steps; this module owns geometry,
wrapping, colours and arrows. Each drawn element carries its cited source as
hover text and a marker for every finding that points at it. Output uses only
static drawing primitives, with every author string escaped.
"""

from collections import Counter
from html import escape
import re
import textwrap


FONT = 'sans-serif'
INK, MUTED, WIRE = '#243044', '#53657d', '#596980'
TONES = {
    'normal': ('#f0f5fc', '#a9bfd9', 1.5, None),
    'new': ('#e8f6ee', '#2f8a57', 2, None),
    'changed': ('#f0edff', '#7960b3', 2, None),
    'removed': ('#fbeeee', '#b54a4a', 2, '6 4'),
    'affected': ('#fff3dd', '#b97820', 2, None),
    'context': ('#ffffff', '#748399', 1.5, '6 5'),
}
TONE_NAMES = {'new': 'New in this stack', 'changed': 'Changed', 'removed': 'Removed',
              'affected': 'Where a finding bites', 'normal': 'Unchanged', 'context': 'Context'}
STATUS_TONES = {'new': 'new', 'changed': 'changed', 'removed': 'removed', 'untouched': 'normal'}
CHANGE_TONES = {'new', 'changed', 'removed', 'affected'}
MARKERS = {'wire': WIRE, 'new': '#2f8a57', 'changed': '#7960b3', 'removed': '#b54a4a', 'affected': '#b97820'}
SEVERITY_COLOURS = {'Critical': '#a61b1b', 'High': '#c2410c', 'Medium': '#a16207', 'Low': '#53657d'}
FIELD_MARKS = {'added': ('+', '#2f8a57'), 'changed': ('~', '#a16207'), 'removed': ('−', '#b54a4a'), 'same': ('', MUTED)}
SHAPES = ('box', 'store', 'queue', 'external', 'actor')
SHAPE_KICKERS = {'store': 'DATA STORE', 'queue': 'QUEUE', 'external': 'EXTERNAL'}
MIN_WIDTH = 1000
MARGIN = 24
CHAR = 0.56  # average glyph width as a fraction of font size, sans-serif
IDENTIFIER_BREAKS = re.compile(r'(?<=[ ._/:,(-])|(?<=[a-z0-9])(?=[A-Z])')


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Plain:
    """Annotations for a drawing outside a record: no sources, no markers, nothing flagged."""
    strict = False

    def tip(self, item):
        return None

    def marks(self, *keys):
        return []


PLAIN = Plain()


def split_long(line, chars):
    """Break an over-long identifier at its own boundaries (dots, slashes, camelCase) before cutting mid-word."""
    pieces = []
    while len(line) > chars:
        cuts = [match.start() for match in IDENTIFIER_BREAKS.finditer(line) if 0 < match.start() <= chars]
        cut = cuts[-1] if cuts else chars
        pieces.append(line[:cut].rstrip())
        line = line[cut:].lstrip()
    return pieces + [line]


def wrap(text, width, size, max_lines=None):
    """Split text into lines that fit `width` at `size`; SVG text never wraps by itself."""
    chars = max(4, int(width / (size * CHAR)))
    lines = [piece for line in textwrap.wrap(str(text), chars, break_long_words=False, break_on_hyphens=False)
             for piece in split_long(line, chars)] or ['']
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:max(1, chars - 1)].rstrip() + '…'
    return lines


def plate_size(lines, size):
    return max(len(line) for line in lines) * size * CHAR + 12, size * 1.3 * len(lines) + 6


def tone_of(item, default='normal'):
    tone = item.get('tone', default) if isinstance(item, dict) else default
    require(tone in TONES, f'Unknown tone: {tone}')
    return tone


def node_tone(item):
    """An explicit tone wins; otherwise the element's change status picks the colour."""
    if 'tone' in item:
        return tone_of(item)
    status = item.get('status', 'untouched')
    require(status in STATUS_TONES, f"Unknown status: {status} (use {', '.join(STATUS_TONES)})")
    return STATUS_TONES[status]


def marker_for(tone):
    return tone if tone in MARKERS else 'wire'


def source_required(role, item):
    """Elements that claim a change or a behaviour must cite a source; unchanged context may not."""
    if not isinstance(item, dict) or item.get('shape') == 'actor':
        return False
    if role == 'field':
        return item.get('status', 'same') != 'same'
    if role in ('node', 'edge'):
        return item.get('status') in ('new', 'changed', 'removed') or item.get('tone') in CHANGE_TONES
    return item.get('tone') != 'context'


def tip_text(ann, item, role):
    tip = ann.tip(item)
    if tip:
        return tip
    return 'No source cited' if ann.strict and source_required(role, item) else None


class Canvas:
    def __init__(self, width, prefix='d'):
        self.width = width
        self.prefix = prefix
        self.parts = []
        self.tones = set()

    def open(self, tooltip=None):
        self.parts.append('<g>' + (f'<title>{escape(tooltip, quote=True)}</title>' if tooltip else ''))

    def close(self):
        self.parts.append('</g>')

    def rect(self, x, y, w, h, tone='normal', rx=10, dash=None):
        fill, stroke, width, default_dash = TONES[tone]
        self.tones.add(tone)
        dash = dash or default_dash
        dash = f' stroke-dasharray="{dash}"' if dash else ''
        self.parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx:.0f}" '
                          f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash}/>')

    def shape(self, kind, x, y, w, h, tone):
        if kind == 'store':
            fill, stroke, width, dash = TONES[tone]
            self.tones.add(tone)
            e = 9
            dash = f' stroke-dasharray="{dash}"' if dash else ''
            self.parts.append(f'<path d="M{x:.0f} {y + e:.0f} A{w / 2:.0f} {e} 0 0 1 {x + w:.0f} {y + e:.0f} '
                              f'V{y + h - e:.0f} A{w / 2:.0f} {e} 0 0 1 {x:.0f} {y + h - e:.0f} Z" fill="{fill}" '
                              f'stroke="{stroke}" stroke-width="{width}"{dash}/>')
            self.parts.append(f'<path d="M{x:.0f} {y + e:.0f} A{w / 2:.0f} {e} 0 0 0 {x + w:.0f} {y + e:.0f}" '
                              f'fill="none" stroke="{stroke}" stroke-width="{width}"/>')
        elif kind == 'actor':
            self.rect(x, y, w, h, tone, rx=min(h / 2, 26))
        elif kind == 'external':
            self.rect(x, y, w, h, tone, dash='3 4')
        else:
            self.rect(x, y, w, h, tone)
            if kind == 'queue':
                stroke = TONES[tone][1]
                for offset in (16, 10):
                    self.parts.append(f'<path d="M{x + w - offset:.0f} {y + 6:.0f} V{y + h - 6:.0f}" '
                                      f'stroke="{stroke}" stroke-width="1.5"/>')

    def frame(self, x, y, w, h, fill='#f7f9fc', dash='6 5'):
        dash = f' stroke-dasharray="{dash}"' if dash else ''
        self.parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="12" '
                          f'fill="{fill}" stroke="#c9d6e6"{dash}/>')

    def lines(self, x, y, lines, size=16, weight='400', fill=INK, anchor='start'):
        leading = round(size * 1.3)
        spans = ''.join(f'<tspan x="{x:.0f}" dy="{0 if i == 0 else leading}">{escape(line, quote=True)}</tspan>'
                        for i, line in enumerate(lines))
        self.parts.append(f'<text x="{x:.0f}" y="{y:.0f}" font-family="{FONT}" font-size="{size}" '
                          f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{spans}</text>')
        return y + leading * (len(lines) - 1)

    def plate(self, x, y, lines, size=12, fill=MUTED, anchor='middle', weight='400'):
        """Text on a white plate so wires never strike through the words. `y` is the first baseline."""
        width, height = plate_size(lines, size)
        if anchor == 'middle':
            x = min(max(x, MARGIN + width / 2), self.width - MARGIN - width / 2)
            left = x - width / 2
        elif anchor == 'end':
            left = x - width + 6
        else:
            left = x - 6
        self.parts.append(f'<rect x="{left:.0f}" y="{y - size - 3:.0f}" width="{width:.0f}" height="{height:.0f}" '
                          f'rx="4" fill="#ffffff" fill-opacity="0.94"/>')
        self.lines(x, y, lines, size=size, fill=fill, anchor=anchor, weight=weight)
        return left, width

    def label(self, x, y, text, size=12, fill=MUTED, max_width=None):
        """A label whose last baseline sits at `y`, so extra lines grow upward, away from the wire below."""
        lines = wrap(text, max_width or self.width, size, max_lines=3)
        return self.plate(x, y - (len(lines) - 1) * round(size * 1.3), lines, size=size, fill=fill)

    def label_above(self, x, bottom, text, size=12, max_width=None):
        """A label plate whose bottom edge sits at `bottom` (just above a row of boxes)."""
        lines = wrap(text, max_width or self.width, size, max_lines=2)
        _, height = plate_size(lines, size)
        return self.plate(x, bottom - height + size + 3, lines, size=size)

    def pill(self, x, y, text, colour, filled=True, anchor='start'):
        """A small tag; `y` is its vertical centre. Returns its width."""
        width = max(22, len(text) * 7 + 12)
        left = x - width if anchor == 'end' else x
        fill, ink, dash = (colour, '#ffffff', '') if filled else ('#ffffff', colour, ' stroke-dasharray="3 2"')
        self.parts.append(f'<rect x="{left:.0f}" y="{y - 10:.0f}" width="{width:.0f}" height="20" rx="10" '
                          f'fill="{fill}" stroke="{colour}" stroke-width="1.5"{dash}/>')
        self.lines(left + width / 2, y + 4, [text], size=11, weight='700', fill=ink, anchor='middle')
        return width

    def badges(self, x, y, marks, unverified=False, anchor='end'):
        """Finding markers (and an unverified flag) starting at x, centred on y."""
        entries = [(label, SEVERITY_COLOURS.get(severity, MUTED), title) for label, severity, title in marks]
        if unverified:
            entries.append(('?', None, 'No source cited for this element'))
        for label, colour, title in entries:
            self.open(title)
            width = self.pill(x, y, label, colour or '#8796a8', filled=bool(colour), anchor=anchor)
            self.close()
            x = x - width - 4 if anchor == 'end' else x + width + 4
        return x

    def wire(self, points, tone='wire', dash=False):
        path = ' '.join(f'{x:.0f},{y:.0f}' for x, y in points)
        dashes = ' stroke-dasharray="6 5"' if dash else ''
        self.parts.append(f'<polyline points="{path}" fill="none" stroke="{MARKERS[tone]}" stroke-width="2" '
                          f'stroke-linejoin="round"{dashes} marker-end="url(#{self.prefix}-m-{tone})"/>')

    def divider(self, y):
        self.parts.append(f'<path d="M{MARGIN} {y:.0f} H{self.width - MARGIN}" stroke="#d7dfe9" stroke-dasharray="4 6"/>')

    def legend(self, y):
        """Swatches for the colours this drawing used, when more than one meaning is on screen."""
        used = [tone for tone in TONE_NAMES if tone in self.tones]
        if len(used) < 2:
            return y
        x = MARGIN
        for tone in used:
            fill, stroke, width, dash = TONES[tone]
            dash = f' stroke-dasharray="{dash}"' if dash else ''
            self.parts.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="22" height="14" rx="3" fill="{fill}" '
                              f'stroke="{stroke}" stroke-width="{width}"{dash}/>')
            self.lines(x + 30, y + 12, [TONE_NAMES[tone]], size=12, fill=MUTED)
            x += 44 + len(TONE_NAMES[tone]) * 12 * CHAR + 18
        return y + 34

    def svg(self, height):
        defs = ''.join(f'<marker id="{self.prefix}-m-{name}" markerWidth="10" markerHeight="10" refX="9" refY="5" '
                       f'orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L10 5 L0 10 Z" fill="{colour}"/></marker>'
                       for name, colour in MARKERS.items())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width:.0f} {height:.0f}">'
                f'<rect width="{self.width:.0f}" height="{height:.0f}" fill="#ffffff"/><defs>{defs}</defs>'
                + ''.join(self.parts) + '</svg>')


def box_text(item, box_width, kicker=None, shape='box'):
    """Wrapped title and detail lines plus the box height they need."""
    require(isinstance(item, dict) and isinstance(item.get('title'), str) and item['title'].strip(),
            'Each step needs a title')
    title = wrap(item['title'], box_width - 24, 15)
    detail = wrap(item['detail'], box_width - 24, 13) if item.get('detail') else []
    height = 34 + len(title) * 20 + (len(detail) * 17 + 8 if detail else 0) + (16 if kicker else 0)
    return title, detail, height + (12 if shape == 'store' else 0)


def draw_box(canvas, x, y, width, height, tone, title, detail, shape='box', kicker=None):
    canvas.shape(shape, x, y, width, height, tone)
    top = y + (12 if shape == 'store' else 0)
    text_y = top + 28
    if kicker:
        canvas.lines(x + 12, top + 22, [kicker], size=10, weight='700', fill=MUTED)
        text_y += 16
    text_y = canvas.lines(x + 12, text_y, title, size=15, weight='700')
    if detail:
        canvas.lines(x + 12, text_y + 24, detail, size=13, fill=MUTED)


def annotate(canvas, ann, item, role, keys, x, y):
    """Markers for findings that point at this element, plus a flag when its source is missing."""
    marks = ann.marks(*keys)
    unverified = ann.strict and source_required(role, item) and not ann.tip(item)
    if marks or unverified:
        canvas.badges(x, y, marks, unverified)


def check_shape(item):
    shape = item.get('shape', 'box')
    require(shape in SHAPES, f"Unknown shape: {shape} (use {', '.join(SHAPES)})")
    return shape


def flow(spec, ann=PLAIN, prefix='d'):
    """Lanes of left-to-right steps; before/after flows are two lanes with aligned actors."""
    lanes = spec.get('lanes')
    require(isinstance(lanes, list) and lanes, 'A flow needs at least one lane')
    for lane in lanes:
        require(isinstance(lane, dict) and isinstance(lane.get('steps'), list) and lane['steps'],
                'Each lane needs a non-empty steps array')
    columns = max(len(lane['steps']) for lane in lanes)
    gap = 48
    width = max(MIN_WIDTH, MARGIN * 2 + columns * 176 + (columns - 1) * gap)
    box_width = (width - MARGIN * 2 - (columns - 1) * gap) / columns
    canvas = Canvas(width, prefix)
    y = MARGIN
    for index, lane in enumerate(lanes):
        if index:
            canvas.divider(y - 14)
        if lane.get('label'):
            y = canvas.lines(MARGIN, y + 14, wrap(lane['label'], width - MARGIN * 2, 15, max_lines=1),
                             size=15, weight='700', fill=MUTED) + 20
        texts = [box_text(step, box_width) for step in lane['steps']]
        y += 40 if any(step.get('arrow') for step in lane['steps']) else 12
        box_height = max(height for _, _, height in texts)
        for column, (step, (title, detail, _)) in enumerate(zip(lane['steps'], texts)):
            x = MARGIN + column * (box_width + gap)
            tone = tone_of(step)
            canvas.open(tip_text(ann, step, 'step'))
            draw_box(canvas, x, y, box_width, box_height, tone, title, detail)
            canvas.close()
            annotate(canvas, ann, step, 'step', (step.get('id'),), x + box_width - 8, y)
            if column:
                canvas.wire([(x - gap + 2, y + box_height / 2), (x - 2, y + box_height / 2)], marker_for(tone))
                if step.get('arrow'):
                    canvas.label_above(x - gap / 2, y - 6, step['arrow'], max_width=box_width)
        y += box_height + 40
    y = canvas.legend(y - 14) + 14
    if spec.get('note'):
        y = canvas.lines(MARGIN, y - 4, wrap(spec['note'], width - MARGIN * 2, 15), size=15) + 30
    return canvas.svg(y - 10)


def layer_nodes(nodes, edges):
    """Longest-path layering over the forward edges; back edges found by DFS are drawn as return arcs."""
    order = [node['id'] for node in nodes]
    outgoing = {key: [] for key in order}
    for edge in edges:
        outgoing[edge['from']].append(edge['to'])
    state, back = {}, set()

    def visit(node):
        state[node] = 'open'
        for target in outgoing[node]:
            if state.get(target) == 'open':
                back.add((node, target))
            elif target not in state:
                visit(target)
        state[node] = 'done'

    for key in order:
        if key not in state:
            visit(key)
    forward = [(edge['from'], edge['to']) for edge in edges if (edge['from'], edge['to']) not in back]
    incoming = Counter(target for _, target in forward)
    sources = [key for key in order if not incoming[key]]
    layer = {key: 0 for key in order}
    ready = list(sources)
    while ready:
        node = ready.pop(0)
        for source, target in forward:
            if source == node:
                layer[target] = max(layer[target], layer[node] + 1)
                incoming[target] -= 1
                if not incoming[target]:
                    ready.append(target)
    # A caller with no callers sits just before its nearest target, so a hook into the middle of the
    # system draws one short wire instead of a channel over every column.
    for key in sources:
        targets = [layer[target] for source, target in forward if source == key]
        if targets:
            layer[key] = min(targets) - 1
    return layer, back


def check_graph(nodes, edges, noun='node'):
    require(isinstance(nodes, list) and nodes and isinstance(edges, list), f'A diagram needs {noun}s and an edges array')
    ids = set()
    for node in nodes:
        require(isinstance(node, dict) and isinstance(node.get('id'), str) and isinstance(node.get('label'), str),
                f'Each {noun} needs an id and a label')
        require(node['id'] not in ids, f"Duplicate {noun} id: {node['id']}")
        ids.add(node['id'])
    for edge in edges:
        require(isinstance(edge, dict) and edge.get('from') in ids and edge.get('to') in ids,
                f'Each edge needs from/to {noun} ids that exist')


def layered(nodes, edges, heights, draw, ann, prefix, box_width=210):
    """Place boxes in dependency layers and route labelled wires so none crosses a box.

    `draw(canvas, node, x, y, width, height)` paints one box. Returns (canvas, bottom).
    """
    layer, back = layer_nodes(nodes, edges)
    row_gap = 30
    kinds = {}
    for edge in edges:
        key = (edge['from'], edge['to'])
        span = layer[edge['to']] - layer[edge['from']]
        kinds[key] = 'back' if key in back else 'skip' if span > 1 else 'next'
    # Labels up to ~30 characters stay on one line, so fanned-out labels don't stack into each other.
    next_labels = [wrap(edge['label'], 200, 12) for edge in edges
                   if edge.get('label') and kinds[(edge['from'], edge['to'])] == 'next']
    column_gap = max(110, *(plate_size(lines, 12)[0] + 16 for lines in next_labels)) if next_labels else 110
    skips = [edge for edge in edges if kinds[(edge['from'], edge['to'])] == 'skip']
    backs = [edge for edge in edges if kinds[(edge['from'], edge['to'])] == 'back']
    columns = {}
    for node in nodes:
        columns.setdefault(layer[node['id']], []).append(node)
    column_heights = {c: sum(heights[n['id']] for n in col) + row_gap * (len(col) - 1) for c, col in columns.items()}
    tallest = max(column_heights.values())
    count = max(columns) + 1
    content_width = count * box_width + (count - 1) * column_gap
    width = max(MIN_WIDTH, content_width + MARGIN * 2)
    left = (width - content_width) / 2
    top = MARGIN + (30 + 26 * len(skips) if skips else 14)
    canvas = Canvas(width, prefix)
    boxes = {}
    for column, members in sorted(columns.items()):
        x = left + column * (box_width + column_gap)
        y = top + (tallest - column_heights[column]) / 2
        for node in members:
            boxes[node['id']] = (x, y, box_width, heights[node['id']])
            draw(canvas, node, x, y, box_width, heights[node['id']])
            y += heights[node['id']] + row_gap
    half = column_gap / 2
    incoming = Counter(edge['to'] for edge in edges if kinds[(edge['from'], edge['to'])] == 'next')
    for edge in edges:
        sx, sy, sw, sh = boxes[edge['from']]
        tx, ty, tw, th = boxes[edge['to']]
        tone = tone_of(edge)
        marker = marker_for(tone)
        kind = kinds[(edge['from'], edge['to'])]
        canvas.open(tip_text(ann, edge, 'edge'))
        if kind == 'skip':
            # Channels run a quarter-gap from the boxes so they never share the vertical of a next-column wire.
            channel = top - 22 - 26 * skips.index(edge)
            out_x, in_x = sx + sw + half / 2, tx - half / 2
            canvas.wire([(sx + sw, sy + sh / 2), (out_x, sy + sh / 2), (out_x, channel), (in_x, channel),
                         (in_x, ty + th / 2), (tx - 2, ty + th / 2)], marker, edge.get('dashed', False))
            anchor = ((out_x + in_x) / 2, channel - 6, 360)
        elif kind == 'back':
            channel = top + tallest + 24 + 26 * backs.index(edge)
            out_x, in_x = max(12, sx - half / 2), tx + tw + half / 2
            canvas.wire([(sx, sy + sh / 2), (out_x, sy + sh / 2), (out_x, channel), (in_x, channel),
                         (in_x, ty + th / 2), (tx + tw + 2, ty + th / 2)], marker, edge.get('dashed', False))
            anchor = ((out_x + in_x) / 2, channel - 6, 360)
        else:
            start, end = (sx + sw, sy + sh / 2), (tx - 2, ty + th / 2)
            middle = (start[0] + end[0]) / 2
            canvas.wire([start, (middle, start[1]), (middle, end[1]), end], marker, edge.get('dashed', False))
            # Wires fanning out of one box share its exit height, so label each at its target instead,
            # unless several wires fan into that target.
            label_y = (start[1] if incoming[edge['to']] > 1 else end[1]) - 10
            anchor = (middle, label_y, column_gap - 12)
        plate = canvas.label(anchor[0], anchor[1], edge['label'], max_width=anchor[2]) if edge.get('label') else None
        canvas.close()
        marks = ann.marks(edge.get('id'))
        unverified = ann.strict and source_required('edge', edge) and not ann.tip(edge)
        if marks or unverified:
            x = plate[0] + plate[1] + 4 if plate else anchor[0] + 6
            canvas.badges(x, anchor[1] - 4, marks, unverified, anchor='start')
    bottom = top + tallest + MARGIN + (30 + 26 * len(backs) if backs else 0)
    return canvas, bottom


def finish(canvas, bottom, spec):
    bottom = canvas.legend(bottom)
    if spec.get('note'):
        bottom = canvas.lines(MARGIN, bottom + 16, wrap(spec['note'], canvas.width - MARGIN * 2, 15), size=15) + 30
    return canvas.svg(bottom)


def graph(spec, ann=PLAIN, prefix='d'):
    """Architecture maps, state machines and call paths: boxes in dependency layers with labelled wires."""
    nodes, edges = spec.get('nodes'), spec.get('edges', [])
    check_graph(nodes, edges)
    texts = {}
    for node in nodes:
        shape = check_shape(node)
        node_tone(node)
        kicker = SHAPE_KICKERS.get(shape)
        texts[node['id']] = (shape, kicker, *box_text({'title': node['label'], 'detail': node.get('detail')},
                                                      210, kicker, shape))
    for edge in edges:
        tone_of(edge)

    def draw(canvas, node, x, y, width, height):
        shape, kicker, title, detail, _ = texts[node['id']]
        canvas.open(tip_text(ann, node, 'node'))
        draw_box(canvas, x, y, width, height, node_tone(node), title, detail, shape, kicker)
        canvas.close()
        annotate(canvas, ann, node, 'node', (node['id'],), x + width - 8, y)

    canvas, bottom = layered(nodes, edges, {key: value[4] for key, value in texts.items()}, draw, ann, prefix)
    return finish(canvas, bottom, spec)


def sequence(spec, ann=PLAIN, prefix='d'):
    """Who calls whom, in order: participants across the top, numbered messages down the page."""
    participants, messages = spec.get('participants'), spec.get('messages')
    require(isinstance(participants, list) and 2 <= len(participants) <= 8,
            'A sequence needs two to eight participants')
    require(isinstance(messages, list) and 1 <= len(messages) <= 24, 'A sequence needs one to 24 messages')
    position = {}
    for item in participants:
        require(isinstance(item, dict) and isinstance(item.get('id'), str) and isinstance(item.get('label'), str),
                'Each participant needs an id and a label')
        require(item['id'] not in position, f"Duplicate participant id: {item['id']}")
        check_shape(item)
        node_tone(item)
        position[item['id']] = len(position)
    for message in messages:
        require(isinstance(message, dict) and message.get('from') in position and message.get('to') in position,
                'Each message needs from/to participant ids that exist')
        require(isinstance(message.get('label'), str) and message['label'].strip(), 'Each message needs a label')
        tone_of(message)
    count = len(participants)
    width = max(MIN_WIDTH, MARGIN * 2 + count * 200)
    pitch = (width - MARGIN * 2) / count
    head_width = pitch - 24
    heads = []
    for item in participants:
        shape = item.get('shape', 'box')
        kicker = SHAPE_KICKERS.get(shape)
        heads.append((shape, kicker, *box_text({'title': item['label'], 'detail': item.get('detail')},
                                               head_width, kicker, shape)))
    head_height = max(head[4] for head in heads)
    centres = [MARGIN + index * pitch + pitch / 2 for index in range(count)]
    top = MARGIN + 6
    rows, y = [], top + head_height + 30
    for number, message in enumerate(messages, 1):
        a, b = position[message['from']], position[message['to']]
        span = abs(b - a) * pitch - 30 if a != b else pitch - 80
        label = wrap(f"{number}. {message['label']}", span, 13)
        detail = wrap(message['detail'], span, 12) if message.get('detail') else []
        arrow_y = y + len(label) * 17 + 6
        rows.append((message, number, a, b, label, detail, arrow_y))
        y = arrow_y + (len(detail) * 15 + 10 if detail else 0) + (36 if a == b else 24)
    bottom = y + 10
    canvas = Canvas(width, prefix)
    for centre in centres:
        canvas.parts.append(f'<path d="M{centre:.0f} {top + head_height:.0f} V{bottom - 10:.0f}" '
                            f'stroke="#b8c5d6" stroke-width="1.5" stroke-dasharray="5 5"/>')
    for item, centre, (shape, kicker, title, detail, _) in zip(participants, centres, heads):
        x = centre - head_width / 2
        canvas.open(tip_text(ann, item, 'node'))
        draw_box(canvas, x, top, head_width, head_height, node_tone(item), title, detail, shape, kicker)
        canvas.close()
        annotate(canvas, ann, item, 'node', (item['id'],), x + head_width - 8, top)
    for message, number, a, b, label, detail, arrow_y in rows:
        tone = marker_for(tone_of(message))
        reply = bool(message.get('reply'))
        canvas.open(tip_text(ann, message, 'message'))
        if a == b:
            x = centres[a]
            label_width = plate_size(label, 13)[0]
            leftward = x + 54 + label_width > width - MARGIN
            canvas.wire([(x - 2, arrow_y - 8), (x - 44, arrow_y - 8), (x - 44, arrow_y + 14), (x - 6, arrow_y + 14)]
                        if leftward else
                        [(x + 2, arrow_y - 8), (x + 44, arrow_y - 8), (x + 44, arrow_y + 14), (x + 6, arrow_y + 14)],
                        tone, reply)
            label_x, detail_anchor = (x - 54, 'end') if leftward else (x + 54, 'start')
            left, plate_width = canvas.plate(label_x, arrow_y - 8 - (len(label) - 1) * 17 + 4, label, size=13,
                                             fill=INK, anchor=detail_anchor)
            label_right, detail_x = left + plate_width, label_x
        else:
            x1, x2 = centres[a], centres[b]
            direction = 1 if x2 > x1 else -1
            canvas.wire([(x1 + 3 * direction, arrow_y), (x2 - 4 * direction, arrow_y)], tone, reply)
            middle = (x1 + x2) / 2
            left, plate_width = canvas.plate(middle, arrow_y - 9 - (len(label) - 1) * 17, label, size=13, fill=INK)
            label_right, detail_x, detail_anchor = left + plate_width, middle, 'middle'
        if detail:
            canvas.plate(detail_x, arrow_y + 19, detail, size=12, anchor=detail_anchor)
        canvas.close()
        marks = ann.marks(message.get('id'), str(number))
        unverified = ann.strict and source_required('message', message) and not ann.tip(message)
        if marks or unverified:
            canvas.badges(label_right + 4, arrow_y - 14, marks, unverified, anchor='start')
    if spec.get('note'):
        bottom = canvas.lines(MARGIN, bottom + 10, wrap(spec['note'], width - MARGIN * 2, 15), size=15) + 30
    return canvas.svg(bottom)


def check_fields(entity):
    fields = entity.get('fields', [])
    require(isinstance(fields, list) and len(fields) <= 16, 'An entity takes at most 16 fields; show changed and key fields only')
    names = set()
    for field in fields:
        require(isinstance(field, dict) and isinstance(field.get('name'), str) and field['name'].strip(),
                'Each field needs a name')
        require(field['name'] not in names, f"Duplicate field {field['name']} in {entity['id']}")
        names.add(field['name'])
        require(field.get('status', 'same') in FIELD_MARKS,
                f"Unknown field status: {field.get('status')} (use {', '.join(FIELD_MARKS)})")
    return fields


def schema(spec, ann=PLAIN, prefix='d'):
    """Collections or tables with their fields, marked added, changed or removed, and their relations."""
    entities, relations = spec.get('entities'), spec.get('relations', [])
    check_graph(entities, relations, 'entity')
    require(len(entities) <= 10, 'A schema diagram takes at most 10 entities; split it')
    heights, widest = {}, 0
    for entity in entities:
        node_tone(entity)
        fields = check_fields(entity)
        heights[entity['id']] = 52 + 26 * len(fields) + (8 if fields else 0)
        for field in fields:
            widest = max(widest, len(field['name']) * 13 * CHAR + len(str(field.get('type', ''))) * 12 * CHAR)
    # Cards widen for long types up to a limit; the field table under the diagram carries the full text.
    card_width = min(440, max(280, widest + 70))
    for relation in relations:
        tone_of(relation)

    def draw(canvas, entity, x, y, width, height):
        status = entity.get('status', 'untouched')
        canvas.open(tip_text(ann, entity, 'node'))
        canvas.rect(x, y, width, height, node_tone(entity))
        canvas.lines(x + 14, y + 28, wrap(entity['label'], width - 110, 15, max_lines=1), size=15, weight='700')
        if status != 'untouched':
            canvas.lines(x + width - 14, y + 27, [status.upper()], size=10, weight='700', fill=MUTED, anchor='end')
        if entity.get('fields'):
            canvas.parts.append(f'<path d="M{x:.0f} {y + 42:.0f} H{x + width:.0f}" stroke="{TONES[node_tone(entity)][1]}" '
                                f'stroke-width="1"/>')
        canvas.close()
        annotate(canvas, ann, entity, 'node', (entity['id'],), x + width - 8, y)
        row_y = y + 64
        for field in entity.get('fields', []):
            field_status = field.get('status', 'same')
            symbol, colour = FIELD_MARKS[field_status]
            marks = ann.marks(f"{entity['id']}.{field['name']}")
            unverified = ann.strict and source_required('field', field) and not ann.tip(field)
            canvas.open(tip_text(ann, field, 'field'))
            if symbol:
                canvas.lines(x + 14, row_y, [symbol], size=15, weight='700', fill=colour)
            name_colour = MUTED if field_status == 'removed' else INK
            name = wrap(field['name'], width * 0.6, 13, max_lines=1)
            name_width = len(name[0]) * 13 * CHAR
            canvas.lines(x + 30, row_y, name, size=13, weight='600' if field_status != 'same' else '400',
                         fill=name_colour)
            if field_status == 'removed':
                canvas.parts.append(f'<path d="M{x + 30:.0f} {row_y - 4:.0f} h{name_width:.0f}" stroke="{MUTED}" stroke-width="1.2"/>')
            right = x + width - 12
            if marks or unverified:
                right = canvas.badges(right, row_y - 4, marks, unverified)
            if field.get('type'):
                room = right - (x + 30 + name_width + 16)
                canvas.lines(right, row_y, wrap(field['type'], max(room, 40), 12, max_lines=1), size=12, fill=MUTED,
                             anchor='end')
            canvas.close()
            row_y += 26

    canvas, bottom = layered(entities, relations, heights, draw, ann, prefix, box_width=card_width)
    return finish(canvas, bottom, spec)


def schema_changes(spec):
    """(cells, field, key) for every added, changed or removed field, for the table under a schema diagram."""
    rows = []
    for entity in spec.get('entities', []):
        for field in entity.get('fields', []):
            status = field.get('status', 'same')
            if status != 'same':
                rows.append(([entity['label'], field['name'], status] + [str(field.get(name, ''))
                                                                        for name in ('type', 'default', 'index', 'note')],
                             field, f"{entity['id']}.{field['name']}"))
    return rows


def timeline(spec, ann=PLAIN, prefix='d'):
    """Rollout order: numbered steps left to right, one row per repository or environment."""
    steps, lanes = spec.get('steps'), spec.get('lanes', [])
    require(isinstance(steps, list) and 1 <= len(steps) <= 12, 'A timeline needs one to 12 steps')
    require(isinstance(lanes, list), 'Timeline lanes must be an array')
    lane_ids = []
    for lane in lanes:
        require(isinstance(lane, dict) and isinstance(lane.get('id'), str) and isinstance(lane.get('label'), str),
                'Each timeline lane needs an id and a label')
        lane_ids.append(lane['id'])
    for step in steps:
        require(isinstance(step, dict), 'Each step must be an object')
        require(step.get('lane') in lane_ids if lanes else 'lane' not in step,
                'Each step needs a lane id from lanes' if lanes else 'Steps take a lane only when lanes are given')
        require(step.get('reversible') in (None, True, False), 'reversible must be true or false')
        tone_of(step)
    rows = lanes or [{'id': None, 'label': ''}]
    left = MARGIN + (150 if lanes else 0)
    count = len(steps)
    pitch = max(230, (MIN_WIDTH - left - MARGIN) / count)
    width = left + count * pitch + MARGIN
    box_width = pitch - 40
    texts = []
    for number, step in enumerate(steps, 1):
        kicker = f"{number}. {step['kind'].upper()}" if step.get('kind') else f'STEP {number}'
        title, detail, height = box_text(step, box_width, kicker)
        texts.append((kicker, title, detail, height + (28 if 'reversible' in step else 0)))
    lane_tops, y = {}, MARGIN
    for row in rows:
        members = [texts[i][3] for i, step in enumerate(steps) if step.get('lane') == row['id']]
        lane_tops[row['id']] = (y, max(members, default=60) + 36)
        y += lane_tops[row['id']][1] + 10
    canvas = Canvas(width, prefix)
    for index, row in enumerate(rows):
        top, height = lane_tops[row['id']]
        if lanes:
            canvas.frame(MARGIN, top, width - MARGIN * 2, height, fill='#f7f9fc' if index % 2 == 0 else '#ffffff', dash=None)
            canvas.lines(MARGIN + 14, top + 28, wrap(row['label'], 130, 14, max_lines=3), size=14, weight='700', fill=MUTED)
    bottom, boxes = y, []
    for index, (step, (kicker, title, detail, _)) in enumerate(zip(steps, texts)):
        top, lane_height = lane_tops[step.get('lane')]
        x, y, height = left + index * pitch + 20, top + 18, lane_height - 36
        canvas.open(tip_text(ann, step, 'step'))
        draw_box(canvas, x, y, box_width, height, tone_of(step), title, detail, kicker=kicker)
        if step.get('reversible') is False:
            canvas.pill(x + 12, y + height - 20, 'ONE-WAY', '#b54a4a')
        elif step.get('reversible') is True:
            canvas.pill(x + 12, y + height - 20, 'REVERSIBLE', '#2f8a57', filled=False)
        canvas.close()
        annotate(canvas, ann, step, 'step', (step.get('id'), str(index + 1)), x + box_width - 8, y)
        boxes.append((x, y, box_width, height))
    for (sx, sy, sw, sh), (tx, ty, tw, th) in zip(boxes, boxes[1:]):
        start, end = (sx + sw + 2, sy + sh / 2), (tx - 3, ty + th / 2)
        middle = (start[0] + end[0]) / 2
        canvas.wire([start, (middle, start[1]), (middle, end[1]), end])
    return finish(canvas, bottom + 6, spec)


def stack_map(prs, dependencies, prefix='stack'):
    """Verified stack map: PR nodes grouped by repository, edges only where the record cites a dependency."""
    groups = {}
    for pr in prs:
        groups.setdefault(pr['repo'], []).append(pr)
    edges = [(dep['from'], dep['to'], dep['label']) for dep in dependencies]
    by_id = {pr['id']: pr for pr in prs}
    node_width, node_height, gap, row_gap, pad = 150, 88, 40, 44, 18
    width = MIN_WIDTH
    per_row = max(1, int((width - MARGIN * 2 - pad * 2 + gap) // (node_width + gap)))
    canvas = Canvas(width, prefix)
    boxes, legend = {}, {}
    parallel = Counter((a, b) for a, b, _ in edges if by_id[a]['repo'] != by_id[b]['repo'])
    lane_pitch = 50  # room for a two-line label plate above each parallel wire
    group_gap = 40 + lane_pitch * max(parallel.values(), default=0)
    y = MARGIN
    for repo, members in groups.items():
        local = [(a, b) for a, b, _ in edges if by_id[a]['repo'] == repo and by_id[b]['repo'] == repo]
        layer, _ = layer_nodes([{'id': pr['id']} for pr in members], [{'from': a, 'to': b} for a, b in local])
        members.sort(key=lambda pr: (layer[pr['id']], pr['number']))
        repeated = {label for label, n in Counter(lbl for a, b, lbl in edges if (a, b) in local).items() if n > 1}
        legend.update({(a, b): lbl for a, b, lbl in edges if (a, b) in local and lbl in repeated})
        rows = [members[i:i + per_row] for i in range(0, len(members), per_row)]
        group_height = 46 + len(rows) * node_height + (len(rows) - 1) * row_gap + pad
        canvas.frame(MARGIN, y, width - MARGIN * 2, group_height)
        canvas.lines(MARGIN + pad, y + 26, [repo], size=15, weight='700', fill=MUTED)
        if repeated:
            canvas.lines(width - MARGIN - pad, y + 26, ['arrows: ' + ' · '.join(sorted(repeated))], size=12,
                         fill=MUTED, anchor='end')
        row_y = y + 46
        for row in rows:
            for column, pr in enumerate(row):
                x = MARGIN + pad + column * (node_width + gap)
                reviewed = pr['scope'] == 'reviewed'
                ink = '#584081' if reviewed else MUTED
                canvas.rect(x, row_y, node_width, node_height, 'changed' if reviewed else 'context')
                canvas.lines(x + 12, row_y + 24, [f"#{pr['number']}"], size=15, weight='700', fill=ink)
                canvas.lines(x + node_width - 12, row_y + 24, ['REVIEWED' if reviewed else 'context'], size=11,
                             weight='700', fill=ink, anchor='end')
                canvas.lines(x + 12, row_y + 47, wrap(pr['title'], node_width - 24, 12, max_lines=3), size=12)
                boxes[pr['id']] = (x, row_y, node_width, node_height)
            row_y += node_height + row_gap
        y += group_height + group_gap
    lane = Counter()
    for source, target, label in edges:
        sx, sy, sw, sh = boxes[source]
        tx, ty, tw, th = boxes[target]
        shown = None if (source, target) in legend else label
        if abs(sy - ty) < 1 and tx > sx:
            canvas.wire([(sx + sw + 2, sy + sh / 2), (tx - 2, ty + th / 2)])
            if shown:
                canvas.label_above((sx + sw + tx) / 2, sy - 4, shown, size=11, max_width=node_width + gap)
        else:
            k = lane[(source, target)]
            lane[(source, target)] += 1
            offset = k - (max(1, parallel[(source, target)]) - 1) / 2
            downward = ty > sy
            mid_y = ((sy + sh + ty) / 2 if downward else (ty + th + sy) / 2) + offset * lane_pitch
            start_y, end_y = (sy + sh + 2, ty - 2) if downward else (sy - 2, ty + th + 2)
            shift = offset * 16
            canvas.wire([(sx + sw / 2 + shift, start_y), (sx + sw / 2 + shift, mid_y),
                         (tx + tw / 2 + shift, mid_y), (tx + tw / 2 + shift, end_y)])
            if shown:
                canvas.label_above((sx + sw / 2 + tx + tw / 2) / 2, mid_y - 4, shown, size=11, max_width=420)
    return canvas.svg(y - group_gap + 24)


def table_rows(spec):
    """Validate a table visual and return (columns, [(cells, tone, row)])."""
    columns, rows = spec.get('columns'), spec.get('rows')
    require(isinstance(columns, list) and columns and all(isinstance(c, str) for c in columns),
            'A table needs a columns array of text')
    require(isinstance(rows, list) and rows, 'A table needs at least one row')
    result = []
    for row in rows:
        cells = row.get('cells') if isinstance(row, dict) else row
        require(isinstance(cells, list) and len(cells) == len(columns) and all(isinstance(c, str) for c in cells),
                'Each table row needs one text cell per column')
        result.append((cells, tone_of(row) if isinstance(row, dict) else 'normal', row if isinstance(row, dict) else {}))
    return columns, result


def elements(visual):
    """(keys, item, role) for every drawn element that can carry a source or a finding marker."""
    def dicts(items):
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    kind = visual.get('kind')
    found = []
    if kind == 'graph':
        found += [((n.get('id'),), n, 'node') for n in dicts(visual.get('nodes'))]
        found += [((e.get('id'),), e, 'edge') for e in dicts(visual.get('edges'))]
    elif kind == 'sequence':
        found += [((p.get('id'),), p, 'node') for p in dicts(visual.get('participants'))]
        found += [((m.get('id'), str(n)), m, 'message') for n, m in enumerate(dicts(visual.get('messages')), 1)]
    elif kind == 'schema':
        for entity in dicts(visual.get('entities')):
            found.append(((entity.get('id'),), entity, 'node'))
            found += [((f"{entity.get('id')}.{f.get('name')}",), f, 'field') for f in dicts(entity.get('fields'))]
        found += [((r.get('id'),), r, 'edge') for r in dicts(visual.get('relations'))]
    elif kind == 'timeline':
        found += [((s.get('id'), str(n)), s, 'step') for n, s in enumerate(dicts(visual.get('steps')), 1)]
    elif kind == 'flow':
        for lane in dicts(visual.get('lanes')):
            found += [((s.get('id'),), s, 'step') for s in dicts(lane.get('steps'))]
    elif kind == 'table':
        found += [((r.get('id'),), r, 'row') for r in dicts(visual.get('rows'))]
    return [(tuple(k for k in keys if isinstance(k, str)), item, role) for keys, item, role in found]


BUILDERS = {'flow': flow, 'graph': graph, 'sequence': sequence, 'schema': schema, 'timeline': timeline}
