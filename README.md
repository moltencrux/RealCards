# RealCards

**Print your Anki cards. For real.**

RealCards is a modern Anki Add-on that enables exporting to PDF/HTML for printing paper flashcards with **card-level selection**. RealCards is Flatpak-friendly and does not require a separately installed browser to render PDF files.


Currently, this is an initial relase, so there will certainly be bugs. Please be understanding. If you encounter a problem, please file a bug reports, or better yet, [contribute](#Contributing)!

---

## Features

- **Export selected cards only** (Not the whole note)
- **Deck or note export** via `File → Export`
- **HTML & PDF output**
- **Flatpak friendly** (uses `xdg-desktop-portal`)
- **Audio hidden** (`.noPrint` CSS)
- **Clean, modern code**

---

## Installation

1. Download from [AnkiWeb](#) (coming soon) or GitHub
2. Install in Anki → Tools → Add-ons → Import
3. Restart Anki

---

## Usage

### From Anki Browser

- To export by card
    - Toggle to card view mode
    - Select cards to print
    - `Cards` (or right click) -> `RealCards` -> `Export Selected Cards -> HTML/PDF`

- To export by note
    - Toggle to note view mode
    - Select notes to print
    - `Notes` (or right click) -> `Export Notes`
    - Select `RealCards (HTML/PDF)` in the combo box -> Click `Export`

### From Main Window
- `File` -> `Export` -> `RealCards (HTML/PDF)`
- Select the deck to export
- click `Export`

---

## Contributing
Contributions to RealCards are welcome! To contribute, please fork the repository, make your changes, and submit a pull request.

## License

**AGPLv3** — see [LICENSE](LICENSE)

Inspired by [Papercards](https://ankiweb.net/shared/info/2042118948) 
,Improved for modern Anki, Flatpak, and card-level control.

---

## Author

[Moltencrux] — [GitHub](https://github.com/moltencrux)

---