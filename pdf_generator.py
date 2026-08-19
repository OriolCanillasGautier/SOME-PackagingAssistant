"""
PackAssist - Multi-page "Pack Data Sheet" PDF generator (generic PDS style,
inspired by the ZF Packaging Data Sheet and Autoliv proposal sheet formats).

Page 1: doc header (part + metadata), part info, isometric render + metrics,
        small views, packing unit (box) table, shipping unit (pallet) table.
Page 2: packaging components & cost table, supplier block, approval
        signature table, additional comments.

Standalone: python pdf_generator.py [input.json] [output.pdf]
Requires:  fpdf2  (pip install fpdf2)
"""

import json
import os
import sys
from datetime import datetime

try:
    from fpdf import FPDF
except ImportError:  # pragma: no cover
    raise SystemExit("fpdf2 is required: pip install fpdf2")

VERSION = "v1.3.0"

# Accent / palette (Pack Studio style)
GREEN = (5, 150, 105)      # #059669
GREEN_LIGHT = (240, 253, 249)  # #f0fdf9
GREEN_PALE = (209, 250, 229)   # #d1fae5
GREEN_DARK = (6, 95, 70)       # #065f46
DARK = (17, 24, 39)        # #111827
GRAY = (107, 114, 128)     # #6b7280
LIGHT_GRAY = (156, 163, 175)   # #9ca3af
BORDER = (229, 231, 235)   # #e5e7eb
BG = (248, 250, 252)       # #f8fafc
WHITE = (255, 255, 255)
RED = (185, 28, 28)        # #b91c1c
RED_BG = (254, 242, 242)   # #fef2f2
RED_BORDER = (254, 202, 202)   # #fecaca
BLUE = (29, 78, 216)       # #1d4ed8
BLUE_BG = (239, 246, 255)  # #eff6ff
BLUE_BORDER = (191, 219, 254)  # #bfdbfe

STRINGS = {
    'ca': {
        'kicker': 'Fitxa Tècnica d\'Empaquetatge',
        'page': 'Pàgina',
        'revision': 'Rev',
        'partNumber': 'Nº de peça',
        'project': 'Projecte',
        'material': 'Material',
        'supplierName': 'Proveïdor',
        'supplierInfo': 'Informació del proveïdor',
        'supplierAddress': 'Adreça',
        'supplierContact': 'Contacte',
        'supplierPhone': 'Telèfon',
        'supplierEmail': 'Email',
        'supplierFunction': 'Funció',
        'dimensions': 'Dimensions',
        'weight': 'Pes',
        'weightPerPiece': 'Pes / peça',
        'pieceCount': 'Nombre de peces',
        'volumeUsage': 'Ocupació',
        'boxDims': 'Caixa (mm)',
        'maxWeight': 'Pes màxim (kg)',
        'totalWeight': 'Pes total (kg)',
        'modeUsed': 'Mode',
        'modeFast': 'Planar',
        'modeBulk': 'A granel',
        'modeGpu': 'GPU',
        'topView': 'Vista Superior',
        'frontView': 'Vista Frontal',
        'sideView': 'Vista Lateral',
        'isometricView': 'Vista Isomètrica',
        'boxInfo': 'Unitat de càrrega (caixa)',
        'palletInfo': 'Unitat d\'expedició (palet)',
        'palletDims': 'Dimensions externes (mm)',
        'palletWeight': 'Pes (kg)',
        'boxesPerPallet': 'Caixes / palet',
        'components': 'Components de l\'embalatge',
        'desc': 'Descripció',
        'matType': 'Material',
        'dimsCol': 'L×A×H (mm)',
        'qty': 'Quantitat',
        'priceUnit': 'Preu / unitat',
        'costCol': 'Cost',
        'noComponents': 'Cap component definit',
        'itemsTotal': 'Components / caixa',
        'costTitle': 'Resum de costos',
        'boxCost': 'Cost caixa',
        'packagingCost': 'Embalatge',
        'freightCost': 'Transport',
        'costPerPart': 'Cost per peça',
        'approvals': 'Aprovacions',
        'step': 'Fase',
        'function': 'Funció',
        'name': 'Nom',
        'signature': 'Signatura',
        'date': 'Data',
        'createdBy': 'Creat per',
        'additionalComments': 'Comentaris addicionals',
        'pieces': 'peces',
        'boxes': 'caixes',
        'traySummary': 'Empaquetatge multi-caixa',
        'interlockedWarning': 'Peces entrellaçades',
        'generatedBy': 'Generat per PackAssist'
    },
    'en': {
        'kicker': 'Pack Data Sheet',
        'page': 'Page',
        'revision': 'Rev',
        'partNumber': 'Part number',
        'project': 'Project',
        'material': 'Material',
        'supplierName': 'Supplier',
        'supplierInfo': 'Supplier information',
        'supplierAddress': 'Address',
        'supplierContact': 'Contact',
        'supplierPhone': 'Phone',
        'supplierEmail': 'Email',
        'supplierFunction': 'Function',
        'dimensions': 'Dimensions',
        'weight': 'Weight',
        'weightPerPiece': 'Weight / part',
        'pieceCount': 'Piece count',
        'volumeUsage': 'Fill rate',
        'boxDims': 'Box (mm)',
        'maxWeight': 'Max weight (kg)',
        'totalWeight': 'Total weight (kg)',
        'modeUsed': 'Mode',
        'modeFast': 'Planar',
        'modeBulk': 'Bulk',
        'modeGpu': 'GPU',
        'topView': 'Top View',
        'frontView': 'Front View',
        'sideView': 'Side View',
        'isometricView': 'Isometric View',
        'boxInfo': 'Packing unit (box)',
        'palletInfo': 'Shipping unit (pallet)',
        'palletDims': 'External size (mm)',
        'palletWeight': 'Weight (kg)',
        'boxesPerPallet': 'Boxes / pallet',
        'components': 'Packaging components',
        'desc': 'Description',
        'matType': 'Material',
        'dimsCol': 'L×W×H (mm)',
        'qty': 'Qty',
        'priceUnit': 'Price / unit',
        'costCol': 'Cost',
        'noComponents': 'No packaging components defined',
        'itemsTotal': 'Components / box',
        'costTitle': 'Cost summary',
        'boxCost': 'Box cost',
        'packagingCost': 'Packaging',
        'freightCost': 'Freight',
        'costPerPart': 'Cost per part',
        'approvals': 'Approvals',
        'step': 'Step',
        'function': 'Function',
        'name': 'Name',
        'signature': 'Signature',
        'date': 'Date',
        'createdBy': 'Created by',
        'additionalComments': 'Additional comments',
        'pieces': 'pieces',
        'boxes': 'boxes',
        'traySummary': 'Multi-box packing',
        'interlockedWarning': 'Interlocked pieces',
        'generatedBy': 'Generated by PackAssist'
    }
}


def _find_unicode_font():
    """Return paths to regular + bold Unicode TTFs, or (None, None)."""
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ("C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\arialbd.ttf"),
    ]
    for regular, bold in candidates:
        if os.path.exists(regular):
            return regular, (bold if os.path.exists(bold) else regular)
    return None, None


def _num(v):
    try:
        n = float(v)
        return n
    except (TypeError, ValueError):
        return None


def _fmt(v, max_frac=2):
    n = _num(v)
    if n is None:
        return '—'
    return f"{n:.{max_frac}f}".rstrip('0').rstrip('.')


def _fmt_euro(v):
    n = _num(v)
    if n is None:
        return '—'
    return f"{n:,.2f} €".replace(",", " ")


class PackReportPDF(FPDF):
    """Multi-page Pack Data Sheet generator (generic PDS style)."""

    def __init__(self, lang_code='ca'):
        super().__init__(format='A4', unit='mm')
        self.lang_code = lang_code if lang_code in STRINGS else 'ca'
        self.strs = STRINGS[self.lang_code]
        self.set_auto_page_break(auto=False)

        regular, bold = _find_unicode_font()
        if regular:
            self.add_font('Pack', '', regular)
            self.add_font('Pack', 'B', bold or regular)
            self.font_family = 'Pack'
        else:
            self.font_family = 'helvetica'

    # ── low-level helpers ───────────────────────────────────────
    def _font(self, style='', size=9):
        self.set_font(self.font_family, style, size)

    def _set_fill(self, rgb):
        self.set_fill_color(*rgb)

    def _set_text(self, rgb):
        self.set_text_color(*rgb)

    def _set_draw(self, rgb):
        self.set_draw_color(*rgb)

    def _rounded_rect(self, x, y, w, h, r=2, fill=None, line=None, line_width=0.3):
        if fill is not None:
            self._set_fill(fill)
        if line is not None:
            self._set_draw(line)
        self.set_line_width(line_width)
        self.rect(x, y, w, h, style='DF' if fill is not None else 'D')

    def _fit_image(self, path, x, y, box_w, box_h):
        """Place an image inside a box preserving aspect ratio. Returns (w, h, x, y)."""
        if not path or not os.path.exists(path):
            return None
        try:
            info = self.images[path]
            iw, ih = info['w'], info['h']
        except Exception:
            iw, ih = box_w, box_h
        scale = min(box_w / iw, box_h / ih)
        w, h = iw * scale, ih * scale
        return w, h, x + (box_w - w) / 2, y + (box_h - h) / 2

    def _section_title(self, label):
        self._set_fill(GREEN)
        self.rect(9, self.get_y(), 1.4, 5.5, 'F')
        self._set_text(GREEN)
        self._font('B', 8)
        self.set_xy(12, self.get_y() + 0.5)
        self.cell(150, 4, label.upper())

    def _page_footer(self, n, total=2):
        self._set_text(LIGHT_GRAY)
        self._font('B', 6.5)
        self.set_xy(160, 288)
        self.cell(41, 4, f"{self.strs['page']} {n}/{total}", align='R')

    # ── page 1 ──────────────────────────────────────────────────
    def _draw_doc_header(self, name, part_number, dims_text, weight_text,
                         revision, date_str):
        self._set_text(GREEN)
        self._font('B', 7)
        self.set_xy(9, 9)
        self.cell(120, 4, self.strs['kicker'].upper(), ln=0)
        self._set_text(DARK)
        self._font('B', 17)
        self.set_xy(9, 14)
        self.cell(135, 8, self._clip(name, 46), ln=0)
        self._set_text(GRAY)
        self._font('', 9)
        self.set_xy(9, 23)
        sub = f"{part_number} · " if part_number else ""
        self.cell(140, 4, f"{sub}{dims_text} · {self.strs['weight']} {weight_text} kg")

        # Right: PackAssist branding
        self._set_text(GREEN)
        self._font('B', 13)
        self.set_xy(120, 10)
        self.cell(81, 6, "PackAssist", ln=0, align='R')
        self._set_text(GRAY)
        self._font('', 8)
        self.set_xy(120, 17)
        self.cell(81, 4, f"{VERSION} · {date_str}", ln=0, align='R')
        if revision:
            self.set_xy(120, 22)
            self.cell(81, 4, f"{self.strs['revision']} {revision}", ln=0, align='R')

        # Header bottom border
        self._set_draw(DARK)
        self.set_line_width(1.0)
        self.line(9, 29, 201, 29)

    def _draw_kv(self, x, y, w, h, label, value, highlight=False):
        self._rounded_rect(x, y, w, h, r=1.6,
                           fill=(GREEN_LIGHT if highlight else None),
                           line=(GREEN if highlight else BORDER), line_width=0.3)
        self._set_text(GRAY)
        self._font('B', 6)
        self.set_xy(x + 1.6, y + 1.4)
        self.cell(w - 3, 3, self._clip(label, 28), ln=0)
        self._set_text(DARK if not highlight else GREEN)
        self._font('B', 8)
        self.set_xy(x + 1.6, y + 4.6)
        self.cell(w - 3, 4, self._clip(value, 30), ln=0)

    def _draw_metric(self, x, y, w, h, value, label, highlight=False, size=11):
        self._rounded_rect(x, y, w, h, r=2,
                           fill=(GREEN if highlight else None),
                           line=(GREEN if highlight else BORDER), line_width=0.4)
        self._set_text((255, 255, 255) if highlight else GREEN)
        self._font('B', size)
        self.set_xy(x + 2, y + 2.5)
        self.multi_cell(w - 4, size + 1.0, self._clip(str(value), 18), align='L')
        self._set_text((255, 255, 255) if highlight else GRAY)
        self._font('B', 6)
        self.set_xy(x + 2, y + h - 6)
        self.multi_cell(w - 4, 2.8, label, align='L')

    def _draw_views(self, views, hero_path, metrics):
        y0 = self.get_y()
        # hero (left) + metrics (right)
        self._rounded_rect(9, y0, 112, 76, r=2.5, fill=BG, line=BORDER)
        fit = self._fit_image(hero_path, 13, y0 + 2, 104, 66)
        if fit:
            w, h, x, y = fit
            self.image(hero_path, x, y, w=w, h=h)
        self._set_text(GRAY)
        self._font('B', 6.5)
        self.set_xy(9, y0 + 69)
        self.cell(112, 4, self.strs['isometricView'], align='C')

        # metrics col: 2x2 grid
        mx, my, mw, mh, mg = 124, y0, 37, 37, 2
        for i, (value, label, size) in enumerate(metrics):
            col, row = i % 2, i // 2
            self._draw_metric(mx + col * (mw + mg), my + row * (mh + mg),
                              mw, mh, value, label,
                              highlight=(row == 1 and col == 1), size=size)

        # small views row
        y1 = y0 + 76 + 2
        for i, (key, label) in enumerate(zip(['top', 'front', 'side'],
                                             [self.strs['topView'], self.strs['frontView'], self.strs['sideView']])):
            x = 9 + i * 64
            self._rounded_rect(x, y1, 60, 28, r=2, fill=BG, line=BORDER)
            fit = self._fit_image(views.get(key), x + 3, y1 + 1.5, 54, 21)
            if fit:
                w, ih, ix, iy = fit
                self.image(views.get(key), ix, iy, w=w, h=ih)
            self._set_text(GRAY)
            self._font('B', 6.5)
            self.set_xy(x, y1 + 22.5)
            self.cell(60, 4, label, align='C')
        self.set_y(y1 + 28 + 2)

    # ── data tables ─────────────────────────────────────────────
    def _table_row(self, pairs, header=False):
        """pairs: list of (label, value, width_mm). One table row."""
        x = 9
        row_h = 7.5
        row_y = self.get_y()
        for label, value, width in pairs:
            self._rounded_rect(x, row_y, width, row_h, r=0,
                               fill=(GREEN_LIGHT if header else None),
                               line=BORDER, line_width=0.25)
            if header:
                self._set_text(GREEN_DARK)
                self._font('B', 6.5)
                self.set_xy(x + 1.6, row_y + 1.6)
                self.multi_cell(width - 3, 3, label, align='L')
            else:
                self._set_text(DARK)
                self._font('B', 6.5)
                self.set_xy(x + 1.6, row_y + 1.4)
                self.multi_cell(width - 3, 3, label, align='L')
                self._set_text(GRAY)
                self._font('', 6.5)
                self.set_xy(x + 1.6 + width / 2, row_y + 1.4)
                self.multi_cell(width / 2 - 1.6, 3, value, align='L')
            x += width
        self.set_y(row_y + row_h)

    # ── page 2 ──────────────────────────────────────────────────
    def _draw_components(self, items, items_total):
        self._section_title(self.strs['components'])
        self.ln(7)
        headers = [(self.strs['desc'], 'D', 60), (self.strs['matType'], 'M', 22),
                   (self.strs['dimsCol'], 'L', 24), (self.strs['qty'], 'Q', 12),
                   (self.strs['priceUnit'], 'P', 22), (self.strs['costCol'], 'C', 20)]
        self._table_row([(h[0], '', h[2]) for h in headers], header=True)
        if not items:
            self._table_row([('—', '—', 160)])
        for it in items:
            dims = f"{_fmt(it.get('l'))}×{_fmt(it.get('w'))}×{_fmt(it.get('h'))}" if any(_num(it.get(k)) is not None for k in ('l', 'w', 'h')) else '—'
            self._table_row([
                (it.get('desc', ''), '', 60),
                (it.get('material', '—'), '', 22),
                (dims, '', 24),
                (_fmt(it.get('qty'), 0), '', 12),
                (_fmt_euro(it.get('price')), '', 22),
                (_fmt_euro(_num(it.get('qty')) * (_num(it.get('price')) or 0)), '', 20),
            ])
        if items_total is not None:
            self._set_text(GREEN_DARK)
            self._font('B', 7)
            self.set_xy(9, self.get_y() + 1.5)
            self.cell(120, 4, f"{self.strs['itemsTotal']}: {_fmt_euro(items_total)}", ln=0)
            self.ln(6)

    def _draw_cost(self, cost):
        if not cost:
            return
        y0 = self.get_y() + 1
        h = 26
        self._rounded_rect(9, y0, 192, h + 8, r=2.5, fill=GREEN_LIGHT, line=GREEN, line_width=0.6)
        self._set_text(GREEN)
        self._font('B', 7.5)
        self.set_xy(11, y0 + 2)
        self.cell(60, 4, self.strs['costTitle'].upper(), ln=0)

        col_w, gap, x0 = 45, 4, 11
        cols = [
            (self.strs['boxCost'], cost.get('boxCost')),
            (self.strs['packagingCost'], cost.get('packagingCost')),
            (self.strs['freightCost'], cost.get('freightCost')),
            (self.strs['costPerPart'], cost.get('costPerPart')),
        ]
        for i, (label, value) in enumerate(cols):
            x = x0 + i * (col_w + gap)
            highlight = (i == 3)
            self._rounded_rect(x, y0 + 7, col_w, h - 7, r=2,
                               fill=(GREEN if highlight else None),
                               line=(GREEN if highlight else GREEN_PALE), line_width=0.4)
            self._set_text((255, 255, 255) if highlight else GREEN)
            self._font('B', 10)
            self.set_xy(x + 2, y0 + 9)
            self.multi_cell(col_w - 4, 4.5, self._clip(_fmt_euro(value), 12), align='L')
            self._set_text((255, 255, 255) if highlight else GRAY)
            self._font('B', 6)
            self.set_xy(x + 2, y0 + h - 6)
            self.multi_cell(col_w - 4, 2.8, label, align='L')
        self.set_y(y0 + h + 8 + 2)

    def _draw_supplier(self, supplier):
        if not any(supplier.get(k) for k in ('name', 'address', 'contact', 'phone', 'email', 'function')):
            return
        self._section_title(self.strs['supplierInfo'])
        self.ln(6.5)
        pairs = [
            ((self.strs['supplierName'], supplier.get('name') or '—'),
             (self.strs['supplierAddress'], supplier.get('address') or '—'),
             (self.strs['supplierContact'], supplier.get('contact') or '—')),
            ((self.strs['supplierPhone'], supplier.get('phone') or '—'),
             (self.strs['supplierEmail'], supplier.get('email') or '—'),
             (self.strs['supplierFunction'], supplier.get('function') or '—')),
        ]
        for row_pairs in pairs:
            cells = []
            for label, value in row_pairs:
                cells.append((label, value, 64))
            self._table_row(cells)
        self.ln(2)

    def _draw_approvals(self, approvals):
        if not any(approvals.get(k) for k in ('conceptName', 'finalName', 'createdBy')):
            return
        self._section_title(self.strs['approvals'])
        self.ln(6.5)
        headers = [(self.strs['step'], 'S', 30), (self.strs['function'], 'F', 42),
                   (self.strs['name'], 'N', 42), (self.strs['signature'], 'S', 36),
                   (self.strs['date'], 'D', 26)]
        self._table_row([(h[0], '', h[2]) for h in headers], header=True)
        rows = [
            ('CONCEPT', approvals.get('conceptFunction'), approvals.get('conceptName'), approvals.get('conceptDate')),
            ('FINAL APPROVAL', approvals.get('finalFunction'), approvals.get('finalName'), approvals.get('finalDate')),
        ]
        for step, fn, nm, dt in rows:
            self._table_row([
                (step, '', 30), (fn or '—', '', 42), (nm or '—', '', 42),
                ('', '', 36), (dt or '', '', 26),
            ])
        if approvals.get('createdBy'):
            self._table_row([(self.strs['createdBy'], approvals.get('createdBy') or '', 176)])
        self.ln(2)

    def _draw_comments(self, comments):
        if not comments:
            return
        self._section_title(self.strs['additionalComments'])
        self.ln(6)
        self._rounded_rect(9, self.get_y(), 192, 14, r=2, fill=None, line=BORDER)
        self._set_text(GRAY)
        self._font('', 7.5)
        self.set_xy(11, self.get_y() + 1.5)
        self.multi_cell(188, 3.6, comments[:280], align='L')
        self.set_y(self.get_y() + 14 + 2)

    # ── value formatting ───────────────────────────────────────
    def _fmt_dim(self, v):
        n = _num(v)
        if n is None:
            return '—'
        return _fmt(n)

    def _clip(self, text, max_chars):
        text = str(text)
        return text if len(text) <= max_chars else text[: max_chars - 1] + "…"

    # ── main entry point ───────────────────────────────────────
    def generate_pack_report(self, data, output_path):
        self.add_page()
        lang = data.get('lang_code', self.lang_code)
        if lang not in STRINGS:
            lang = 'ca'
        self.lang_code = lang
        self.strs = STRINGS[lang]

        piece_dims = data.get('piece_dims', data.get('pieceDims', [0, 0, 0]))
        if isinstance(piece_dims, dict):
            piece_dims = [piece_dims.get('l', 0), piece_dims.get('w', 0), piece_dims.get('h', 0)]
        box_dims = data.get('box_dims', data.get('boxDims', [0, 0, 0]))
        if isinstance(box_dims, dict):
            box_dims = [box_dims.get('length', 0), box_dims.get('width', 0), box_dims.get('height', 0)]
        name = data.get('name') or data.get('part_name') or 'Part'
        part = data.get('part') or {}
        supplier = data.get('supplier') or {}
        cost = data.get('cost') or {}
        items = data.get('items') or []
        pallet = data.get('pallet') or {}
        approvals = data.get('approvals') or {}
        comments = data.get('comments') or ''

        mode = data.get('mode', 'bulk')
        mode_label = {
            'fast': self.strs['modeFast'],
            'bulk': self.strs['modeBulk'],
            'gpu': self.strs['modeGpu'],
        }.get(mode, mode)
        gpu_method = data.get('gpuMethod')
        if mode == 'gpu' and gpu_method:
            mode_label = f"{mode_label} · {gpu_method}"

        piece_count = data.get('piece_count', data.get('pieceCount', 0))
        piece_weight = data.get('piece_weight', data.get('pieceWeight', 0))
        total_weight = data.get('total_weight', data.get('estimatedTotalWeight'))
        if total_weight is None:
            total_weight = piece_count * piece_weight
        max_weight = data.get('max_weight', data.get('maxWeight'))
        volume_usage = data.get('volume_usage', data.get('fillPct'))
        if volume_usage is None:
            pv = data.get('piece_volume_cm3', 0)
            bv = data.get('box_volume_cm3', 0)
            volume_usage = (piece_count * pv / bv * 100) if bv else 0

        interlocked = data.get('interlocked') or {}
        interlock_count = interlocked.get('count', 0)
        trays = data.get('trays') or []
        tray_count = len(trays)
        tray_pieces = [t.get('pieces', 0) for t in trays]

        date_str = data.get('date') or datetime.now().strftime('%d/%m/%Y')
        dims_text = " × ".join(self._fmt_dim(d) for d in piece_dims[:3])

        self._draw_doc_header(name, part.get('number', ''), dims_text,
                              _fmt(piece_weight, 4), part.get('revision', ''), date_str)

        # Part info grid (4 cols x 2 rows)
        info_cells = [
            (self.strs['partNumber'], part.get('number') or '—', False),
            (self.strs['project'], part.get('project') or '—', False),
            (self.strs['material'], part.get('material') or '—', False),
            (self.strs['supplierName'], supplier.get('name') or '—', False),
            (self.strs['dimensions'], dims_text, True),
            (self.strs['weightPerPiece'], f"{_fmt(piece_weight, 4)} kg", True),
            (self.strs['modeUsed'], mode_label, False),
            (self.strs['volumeUsage'], f"{_fmt(volume_usage)} %", False),
        ]
        x0, y0, cw, ch, gap = 9, 32, 47.5, 12, 2
        for i, (label, value, hl) in enumerate(info_cells):
            col, row = i % 4, i // 4
            self._draw_kv(x0 + col * (cw + gap), y0 + row * (ch + 2),
                          cw, ch, label, value, highlight=hl)
        self.set_y(y0 + 2 * (ch + 2) + 1)

        # Views + hero
        images = data.get('images') or {}
        hero_path = data.get('hero_image') or images.get('hero')
        box_dims_str = "×".join(str(d) for d in box_dims[:3]) + " mm"
        self._draw_views({
            'top': data.get('top_image') or images.get('top'),
            'front': data.get('front_image') or images.get('front'),
            'side': data.get('side_image') or images.get('side'),
        }, hero_path, [
            (f"{piece_count}", self.strs['pieceCount'], 11),
            (f"{_fmt(volume_usage)} %", self.strs['volumeUsage'], 11),
            (box_dims_str, self.strs['boxDims'], 8),
            (f"{_fmt(total_weight)} kg", self.strs['totalWeight'], 11),
        ])

        # Warnings
        if interlock_count > 0:
            self._rounded_rect(9, self.get_y(), 192, 7, r=2, fill=RED_BG, line=RED_BORDER)
            self._set_text(RED)
            self._font('B', 7)
            self.set_xy(11, self.get_y() + 1.5)
            self.cell(188, 4, f"{self.strs['interlockedWarning']}: {interlock_count} {self.strs['pieces']}")
            self.ln(8)
        if tray_count > 1:
            self._rounded_rect(9, self.get_y(), 192, 7, r=2, fill=BLUE_BG, line=BLUE_BORDER)
            self._set_text(BLUE)
            self._font('B', 7)
            self.set_xy(11, self.get_y() + 1.5)
            pieces_str = " + ".join(str(p) for p in tray_pieces)
            self.cell(188, 4, f"{self.strs['traySummary']}: {tray_count} {self.strs['boxes']} ({pieces_str}) = {piece_count} {self.strs['pieces']}")
            self.ln(8)

        # Box (PU) table
        if self.get_y() > 225:
            self.add_page()
        self._section_title(self.strs['boxInfo'])
        self.ln(6.5)
        box_dims_str = "×".join(str(d) for d in box_dims[:3]) + " mm"
        self._table_row([
            (self.strs['boxDims'], box_dims_str, 88),
            (self.strs['pieceCount'], str(piece_count), 44),
            (self.strs['volumeUsage'], f"{_fmt(volume_usage)} %", 44),
        ])
        self._table_row([
            (self.strs['modeUsed'], mode_label, 88),
            (self.strs['totalWeight'], f"{_fmt(total_weight)} kg", 44),
            (self.strs['maxWeight'], f"{_fmt(max_weight)} kg" if _num(max_weight) is not None else '—', 44),
        ])
        self.ln(3)

        # Pallet (SU) table
        if any(_num(pallet.get(k)) is not None or pallet.get(k) for k in ('l', 'w', 'h', 'weight', 'boxes')):
            self._section_title(self.strs['palletInfo'])
            self.ln(6.5)
            pallet_dims = f"{_fmt(pallet.get('l'))}×{_fmt(pallet.get('w'))}×{_fmt(pallet.get('h'))}"
            self._table_row([
                (self.strs['palletDims'], pallet_dims, 88),
                (self.strs['palletWeight'], f"{_fmt(pallet.get('weight'))} kg", 44),
                (self.strs['boxesPerPallet'], _fmt(pallet.get('boxes'), 0), 44),
            ])
            self.ln(2)

        self._page_footer(1)
        # ── page 2 ──
        self.add_page()
        self._set_text(GREEN)
        self._font('B', 7)
        self.set_xy(9, 9)
        self.cell(120, 4, self.strs['kicker'].upper(), ln=0)
        self._set_text(GRAY)
        self._font('', 8)
        self.set_xy(9, 14)
        sub = f" · PN {part.get('number')}" if part.get('number') else ""
        self.cell(140, 4, f"{name}{sub}")
        self._set_text(GRAY)
        self._font('', 8)
        self.set_xy(120, 14)
        self.cell(81, 4, f"{VERSION} · {date_str}", align='R')
        self._set_draw(DARK)
        self.set_line_width(0.6)
        self.line(9, 19, 201, 19)
        self.set_y(22)

        # Components
        items_total = None
        costs = []
        for it in items:
            q = _num(it.get('qty')) or 0
            p = _num(it.get('price')) or 0
            costs.append(q * p)
        if costs:
            items_total = sum(costs)
        self._draw_components(items, items_total)

        # Cost (merged with computed per-part cost)
        cost_out = dict(cost)
        if cost_out.get('costPerPart') is None and piece_count:
            base = (items_total or 0) + (_num(cost.get('boxCost')) or 0)
            cost_out['costPerPart'] = base / piece_count
        self._draw_cost(cost_out if (cost_out.get('boxCost') is not None or
                                     cost_out.get('packagingCost') is not None or
                                     cost_out.get('freightCost') is not None or
                                     cost_out.get('costPerPart') is not None or items_total) else None)

        self._draw_supplier(supplier)
        self._draw_approvals(approvals)
        self._draw_comments(comments)

        self._page_footer(2)

        self.output(output_path)


def _resolve_path(p, base_dir):
    if not p:
        return None
    if os.path.isabs(p):
        return p if os.path.exists(p) else None
    return os.path.join(base_dir, p) if os.path.exists(os.path.join(base_dir, p)) else p


def main():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], encoding='utf-8') as fh:
            data = json.load(fh)
        base_dir = os.path.dirname(os.path.abspath(sys.argv[1]))
        data.setdefault('images', {})
        for key in ('hero_image', 'top_image', 'front_image', 'side_image'):
            data[key] = _resolve_path(data.get(key), base_dir)
        for key in ('hero', 'top', 'front', 'side'):
            if key in data.get('images', {}):
                data['images'][key] = _resolve_path(data['images'][key], base_dir)
    else:
        data = {
            'name': 'ANCHOR BRACKET APR1',
            'part_number': '672346000A',
            'piece_dims': [50, 67, 50],
            'box_dims': [160, 160, 160],
            'piece_count': 79,
            'piece_weight': 0.104,
            'total_weight': 8.216,
            'volume_usage': 11.5,
            'mode': 'gpu',
            'gpuMethod': 'stacking',
            'lang_code': 'ca',
            'part': {
                'number': '672346000A',
                'project': 'RENAULT',
                'revision': '1',
                'material': 'Acer',
            },
            'supplier': {
                'name': 'SOME S.A.',
                'address': 'CALLE BELLMUNT, 120',
                'contact': 'Bartlomiej Kaczor',
                'phone': '+48 44 731 49 11',
                'email': 'bkaczor@some.es',
                'function': 'Packaging Engineer',
            },
            'cost': {
                'boxCost': 0.85,
                'packagingCost': 0.22,
                'freightCost': 1.20,
            },
            'items': [
                {'desc': 'Cardboard box with lid', 'material': 'Cardboard',
                 'l': 600, 'w': 400, 'h': 270, 'qty': 12, 'price': 0.6},
                {'desc': 'Cardboard plates', 'material': 'Cardboard',
                 'l': 585, 'w': 385, 'h': 0.7, 'qty': 48, 'price': 0.08},
            ],
            'pallet': {'l': 1200, 'w': 800, 'h': 145, 'weight': 25, 'boxes': 40},
            'approvals': {
                'createdBy': 'Oriol Canillas',
                'conceptFunction': 'Logistics Planner',
                'conceptName': 'Adriana Popescu',
                'conceptDate': '17/02/2026',
                'finalFunction': 'Logistics Planner',
                'finalName': 'Adriana Popescu',
                'finalDate': '18/03/2026',
            },
            'comments': 'Comentaris addicionals de l\'empaquetatge.',
        }

    output_path = sys.argv[2] if len(sys.argv) > 2 else 'test_pack_report.pdf'
    pdf = PackReportPDF(lang_code=data.get('lang_code', 'ca'))
    pdf.generate_pack_report(data, output_path)
    print(f"Pack report generated: {output_path}")


if __name__ == "__main__":
    main()
