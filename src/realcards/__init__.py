#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright: Moltencrux
# License: GNU AGPL, version 3; http://www.gnu.org/licenses/agpl.html
###############################################################################

"""
RealCards – Export Anki cards to printable HTML/PDF
Anki 25.09+ | Deck Export + Browser Selected Cards
"""

import base64
import re
from pathlib import Path
from string import Template
from urllib.request import urlopen
import time
from itertools import batched

from aqt import mw, gui_hooks
from aqt.qt import (
    QWebEngineView, QWebEnginePage, QEventLoop, QTimer, Qt, QUrl,
    QFileDialog, QAction
)
from aqt.utils import showInfo, showCritical, openLink
from aqt.import_export.exporting import Exporter, ExportOptions
from aqt.browser import Browser
from anki.collection import NoteIdsLimit
from anki.cards import Card
from anki.utils import ids2str

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
DEFAULT_CONFIG = {
    "paper": {
        "format": "A4",
        "orientation": "portrait",
        "cardsPerRow": 3,
        "cardsPerCol": 6
    },
    "card": {
        "fontSize": "12pt",
        "padding": "0.8em",
        "showBorder": True,
        "reverseOrderOnBack": False,
        "skipQuestionOnBack": True
    }
}

# ----------------------------------------------------------------------
class RealCardsExporterBase (Exporter):
    key = "realcards_html"
    extension = "html"
    show_deck_list = True

    def export(self, mw, options: ExportOptions) -> None:
        path = Path(options.out_path)

        # Handle note selection (siblings)
        if options.limit and isinstance(options.limit, NoteIdsLimit):
            note_ids = options.limit.note_ids
            cids = mw.col.db.list(f"SELECT id FROM cards WHERE nid IN {ids2str(note_ids)}")
        else:
            did = mw.col.decks.current()["id"]
            cids = mw.col.db.list(f"SELECT id FROM cards WHERE did = ?", did)

        if not cids:
            showInfo("No cards to export.")
            return

        cards = [mw.col.get_card(cid) for cid in cids]

        runner = RealCardsRunner(
            col=mw.col,
            cards=cards,
            is_pdf=self.is_pdf,
            include_media=options.include_media
        )
        runner.run(path)

        openLink(QUrl.fromLocalFile(str(path)))
        showInfo(f"Exported: {path.name}")


# ----------------------------------------------------------------------
# HTML & PDF EXPORTERS (Thin Wrappers)
# ----------------------------------------------------------------------
class RealCardsPDFExporter(RealCardsExporterBase):
    key = "realcards_pdf"
    extension = "pdf"
    is_pdf = True

    @staticmethod
    def name() -> str:
        return "RealCards (PDF)"


class RealCardsHTMLExporter(RealCardsExporterBase):
    key = "realcards_html"
    extension = "html"
    is_pdf = False

    @staticmethod
    def name() -> str:
        return "RealCards (HTML)"


# ----------------------------------------------------------------------
# Core Exporter Logic
# ----------------------------------------------------------------------
class RealCardsRunner:
    def __init__(self, col, cards=None, is_pdf=False, include_media=False):
        self.col = col
        self.cards = cards or []
        self.is_pdf = is_pdf
        self.include_media = include_media
        self.config = self._load_config()
        self.media_dir = Path(col.media.dir())
        self.templates_dir = Path(__file__).parent / "templates"

    def _load_config(self):
        cfg = mw.addonManager.getConfig(__name__)
        for k, v in DEFAULT_CONFIG["paper"].items():
            cfg["paper"].setdefault(k, v)
        for k, v in DEFAULT_CONFIG["card"].items():
            cfg["card"].setdefault(k, v)
        return cfg

    def _render_question(self, card: Card) -> str:
        output = card.render_output(True, True)  # reload=True, browser=True
        html = output.question_text
        return self._render_side(html)

    def _render_answer(self, card: Card) -> str:
        output = card.render_output(True, True)  # reload=True, browser=True
        html = output.answer_text

        # Strip front if present
        if "<hr id=answer>" in html:
            html = html.split("<hr id=answer>", 1)[1].strip()
        return self._render_side(html)

    def _render_side(self, html: str) -> str:
        """Render card side with playImage, noPrint, etc."""
        html = mw.prepare_card_text_for_display(html)
        html = re.sub(r"<style>.*?</style>", "", html, flags=re.DOTALL)
        if self.include_media:
            html = re.sub(r'(<img[^>]* src=")([^"]+)(")', self._embed_image, html)

        return html

    def _embed_image(self, m):
        prefix, src, suffix = m.groups()
        if src.startswith(("http://", "https://")):
            try:
                data = urlopen(src).read()
            except:
                return m.group(0)
        else:
            p = self.media_dir / Path(src).name
            if not p.exists():
                return m.group(0)
            data = p.read_bytes()
        ext = Path(src).suffix.lstrip(".").lower()
        if ext not in {"png", "jpg", "jpeg", "gif", "svg", "webp"}:
            ext = "png"
        b64 = base64.b64encode(data).decode()
        return f'{prefix}data:image/{ext};base64,{b64}{suffix}'

    def _css(self) -> str:
        settings = {
            "papersize": self.config["paper"]["format"],
            "orientation": self.config["paper"]["orientation"],
            "cardWidth": f"{100 / self.config['paper']['cardsPerRow']:.3f}%",
            "cardHeight": f"{100 / self.config['paper']['cardsPerCol']:.3f}%",
            "fontSize": self.config["card"]["fontSize"],
            "cardPadding": self.config["card"]["padding"],
            "borderWidth": "1" if self.config["card"]["showBorder"] else "0",
            "flexDirection": "row-reverse" if self.config["card"]["reverseOrderOnBack"] else "row",
        }
        css = (self.templates_dir / "style.css").read_text()
        return Template(css).safe_substitute(settings)

    def _layout(self, cards: list[Card]) -> str:
        per_page = self.config["paper"]["cardsPerRow"] * self.config["paper"]["cardsPerCol"]
        html = ""

        for page in batched(self.cards, per_page):
            # Front: Questions
            q_html = '<div class="pageA">\n'
            for card in page:
                q = self._render_question(card)
                q_html += f'<div class="cardA">{q}</div>\n'
            q_html += "</div>\n"

            # Back: Answers
            a_html = '<div class="pageB">\n'
            for card in page:
                a = self._render_answer(card)
                if self.config["card"]["skipQuestionOnBack"]:
                    parts = a.split("<hr id=answer>", 1)
                    a = parts[-1].strip() if len(parts) > 1 else a
                a_html += f'<div class="cardB">{a}</div>\n'
            a_html += "</div>\n"

            html += q_html + a_html

        return html

    def run(self, path: Path):
        if not self.cards:
            showInfo("No cards to export.")
            return

        content = self._layout(self.cards)
        css = self._css()
        page_tpl = (self.templates_dir / "page.html").read_text()
        full_html = Template(page_tpl).substitute({"style": css, "content": content})

        if self.is_pdf:
            self._render_to_pdf(full_html, path)
        else:
            path.write_text(full_html, encoding="utf-8")

    def _render_to_pdf(self, html_content: str, output_path: Path):
        view = QWebEngineView()
        view.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        page = view.page()

        # Flag to track completion
        done = False
        success = False

        def on_pdf(data: bytes):
            nonlocal done, success
            if data:
                try:
                    output_path.write_bytes(data)
                    success = True
                except Exception as e:
                    showCritical(f"Write failed: {e}")
            done = True
            view.close()

        def on_load(ok: bool):
            if ok:
                page.printToPdf(on_pdf)
            else:
                on_pdf(b"")

        page.loadFinished.connect(on_load)
        page.setHtml(html_content, QUrl("file://"))

        # Wait for completion with timeout
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(30000)

        def check():
            if done:
                loop.quit()

        poll = QTimer()
        poll.timeout.connect(check)
        poll.start(100)

        loop.exec()

        if not success:
            output_path.unlink(missing_ok=True)
            raise RuntimeError("PDF rendering failed")


# ----------------------------------------------------------------------
# Register Exporters
# ----------------------------------------------------------------------
def exporters_hook_new(exporters_list):
    exporters_list.append(RealCardsHTMLExporter)
    exporters_list.append(RealCardsPDFExporter)

gui_hooks.exporters_list_did_initialize.append(exporters_hook_new)


# ----------------------------------------------------------------------
# BROWSER MENU: Export Selected Cards (No Siblings)
# ----------------------------------------------------------------------
def setup_browser_menu(browser: Browser):
    menu = browser.form.menu_Cards
    submenu = menu.addMenu("RealCards")

    act_html = QAction("Export Selected Cards → HTML", browser)
    act_html.triggered.connect(lambda: export_selected_cards(browser, is_pdf=False))
    submenu.addAction(act_html)

    act_pdf = QAction("Export Selected Cards → PDF", browser)
    act_pdf.triggered.connect(lambda: export_selected_cards(browser, is_pdf=True))
    submenu.addAction(act_pdf)

gui_hooks.browser_menus_did_init.append(setup_browser_menu)


def export_selected_cards(browser: Browser, is_pdf: bool):
    cids = browser.selectedCards()
    if not cids:
        showInfo("No cards selected.")
        return

    cards = [mw.col.get_card(cid) for cid in cids]

    ext = "pdf" if is_pdf else "html"
    default_name = f"RealCards_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"
    path, _ = QFileDialog.getSaveFileName(
        browser,
        "Save RealCards",
        str(Path.home() / default_name),
        f"{'PDF' if is_pdf else 'HTML'} Files (*.{ext})"
    )
    if not path:
        return

    runner = RealCardsRunner(
        col=mw.col,
        cards=cards,
        is_pdf=is_pdf,
        include_media=True
    )
    runner.run(Path(path))

    openLink(QUrl.fromLocalFile(path))
    showInfo(f"Exported {len(cards)} card(s) to {Path(path).name}")
