"""Reorder existing store Excel exports by design, then PETEK measurement.

This one-shot maintenance utility preserves the header, every cell value,
hyperlink, and cell style while moving complete product rows.  It creates a
recoverable sibling backup before atomically replacing the requested workbook.
"""
from __future__ import annotations

import argparse
import copy
import os
import shutil
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from URETIM_V4.store_identity_v485 import excel_row_sort_key


def reorder(path: Path, *, backup_suffix: str = ".bak_before_design_measure_sort.xlsx") -> dict:
    path = Path(path).resolve()
    if path.suffix.lower() != ".xlsx" or not path.is_file() or path.is_symlink():
        raise ValueError(f"Güvenli XLSX dosyası bekleniyor: {path}")
    backup = path.with_name(path.stem + backup_suffix)
    if backup.exists():
        raise FileExistsError(f"Yedek zaten var, üzerine yazılmadı: {backup}")
    shutil.copy2(path, backup)

    workbook = load_workbook(path)
    try:
        for sheet in workbook.worksheets:
            if sheet.max_row < 2:
                continue
            width = sheet.max_column
            rows = []
            for row_number in range(2, sheet.max_row + 1):
                cells = [sheet.cell(row_number, col) for col in range(1, width + 1)]
                values = tuple(cell.value for cell in cells)
                snapshots = []
                for cell in cells:
                    snapshots.append({
                        "value": cell.value,
                        "style": copy.copy(cell._style) if cell.has_style else None,
                        "number_format": cell.number_format,
                        "font": copy.copy(cell.font),
                        "fill": copy.copy(cell.fill),
                        "border": copy.copy(cell.border),
                        "alignment": copy.copy(cell.alignment),
                        "protection": copy.copy(cell.protection),
                        "hyperlink": copy.copy(cell.hyperlink) if cell.hyperlink else None,
                        "comment": copy.copy(cell.comment) if cell.comment else None,
                    })
                if not any(value is not None for value in values):
                    rows.append((None, sheet.row_dimensions[row_number].height, snapshots, values))
                    continue
                identity = (values[0], values[1], values[2], values[3])
                rows.append((excel_row_sort_key(identity), sheet.row_dimensions[row_number].height, snapshots, values))
            populated = [row for row in rows if row[0] is not None]
            blanks = [row for row in rows if row[0] is None]
            ordered = sorted(populated, key=lambda item: item[0]) + blanks
            for target_row, (_, source_height, source_cells, _) in enumerate(ordered, start=2):
                # Heights are copied from the original row before writes.  A
                # cell snapshot is used because writing earlier rows mutates
                # live worksheet cells and would otherwise corrupt later
                # source rows during the reorder.
                sheet.row_dimensions[target_row].height = source_height
                for col, source in enumerate(source_cells, start=1):
                    target = sheet.cell(target_row, col)
                    target.value = source["value"]
                    if source["style"] is not None:
                        target._style = copy.copy(source["style"])
                    target.number_format = source["number_format"]
                    target.font = copy.copy(source["font"])
                    target.fill = copy.copy(source["fill"])
                    target.border = copy.copy(source["border"])
                    target.alignment = copy.copy(source["alignment"])
                    target.protection = copy.copy(source["protection"])
                    target.hyperlink = copy.copy(source["hyperlink"]) if source["hyperlink"] else None
                    target.comment = copy.copy(source["comment"]) if source["comment"] else None
            for row_number in range(2 + len(ordered), sheet.max_row + 1):
                for col in range(1, width + 1):
                    sheet.cell(row_number, col).value = None
                    sheet.cell(row_number, col).hyperlink = None
    finally:
        fd, tmp_name = tempfile.mkstemp(prefix=".reordered-trendyol-", suffix=".xlsx", dir=path.parent)
        os.close(fd)
        try:
            workbook.save(tmp_name)
            os.replace(tmp_name, path)
        finally:
            Path(tmp_name).unlink(missing_ok=True)
            workbook.close()

    check = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = check.active
        identities = [(sheet.cell(r, 1).value, sheet.cell(r, 2).value,
                       sheet.cell(r, 3).value, sheet.cell(r, 4).value)
                      for r in range(2, sheet.max_row + 1)
                      if sheet.cell(r, 1).value is not None]
        if identities != sorted(identities, key=excel_row_sort_key):
            raise ValueError(f"Sıralama doğrulaması başarısız: {path}")
        return {"path": str(path), "backup": str(backup), "rows": len(identities)}
    finally:
        check.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        print(reorder(path))


if __name__ == "__main__":
    main()
