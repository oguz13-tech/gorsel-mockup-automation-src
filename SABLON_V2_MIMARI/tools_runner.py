# -*- coding: utf-8 -*-
"""Independent end-user utility suite for the mockup workspace.

Each tool can be started on its own and never depends on the factory render
loop. Destructive operations are intentionally blocked inside the live
template pools so utility usage cannot invalidate approved template hashes.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

import requests
from openpyxl import Workbook
from PIL import Image


SOURCE_ROOT = Path(__file__).resolve().parent.parent
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def resolve_runtime_root() -> Path:
    override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    candidates = [
        home / "OneDrive" / "Masaüstü" / "GörselÜretme-ve-Mockup Otomasyonu",
        home / "Desktop" / "GörselÜretme-ve-Mockup Otomasyonu",
        SOURCE_ROOT,
    ]
    for candidate in candidates:
        if (candidate / "SABLON_V2_MIMARI" / "ayarlar.db").is_file():
            return candidate.resolve()
    return SOURCE_ROOT.resolve()


RUNTIME_ROOT = resolve_runtime_root()
os.environ["MOCKUP_RUNTIME_WORKSPACE"] = str(RUNTIME_ROOT)


def _ui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog

    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    return root, filedialog, messagebox, simpledialog


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _protected_template_roots(runtime_root: Path | None = None) -> list[Path]:
    root = (runtime_root or RUNTIME_ROOT).resolve()
    return [
        root / "2_SABLON_HAVUZU",
        root / "2_SABLON_HAVUZU_ORIJINAL_YEDEK",
    ]


def ensure_not_live_template_path(
    paths: list[Path],
    runtime_root: Path | None = None,
) -> None:
    protected = _protected_template_roots(runtime_root)
    for path in paths:
        for root in protected:
            if root.exists() and _is_under(path, root):
                raise ValueError(
                    "Bu araç aktif şablon veya orijinal-yedek klasöründe "
                    "dosya adı değiştiremez. Bu klasörleri İnceleme Merkezi "
                    "yönetir."
                )


def _sanitize_prefix(prefix: str) -> str:
    prefix = str(prefix or "").strip()
    prefix = re.sub(r'[<>:"/\\|?*]+', "_", prefix)
    prefix = prefix.rstrip(" .")
    if not prefix:
        raise ValueError("Geçerli bir başlangıç adı yazın.")
    return prefix


def rename_images(
    files: list[Path],
    prefix: str,
    runtime_root: Path | None = None,
) -> list[Path]:
    """Collision-safe, two-phase rename for selected files in one folder."""
    selected = [Path(p).resolve() for p in files]
    if not selected:
        raise ValueError("İsimlendirilecek görsel seçilmedi.")
    if any(not p.is_file() for p in selected):
        raise ValueError("Seçim içinde bulunamayan dosya var.")
    if any(p.suffix.lower() not in IMAGE_EXTS for p in selected):
        raise ValueError("Seçimde desteklenmeyen dosya türü var.")

    parents = {p.parent for p in selected}
    if len(parents) != 1:
        raise ValueError("Görseller aynı klasörden seçilmelidir.")

    ensure_not_live_template_path(selected, runtime_root)
    prefix = _sanitize_prefix(prefix)
    selected = sorted(selected, key=lambda p: p.name.casefold())
    parent = selected[0].parent
    selected_set = {p.resolve() for p in selected}

    targets = [
        parent / f"{prefix}{index:03d}{source.suffix.lower()}"
        for index, source in enumerate(selected, start=1)
    ]
    if len({p.name.casefold() for p in targets}) != len(targets):
        raise ValueError("Yeni dosya adları kendi içinde çakışıyor.")

    for target in targets:
        if target.exists() and target.resolve() not in selected_set:
            raise FileExistsError(
                f"Hedef ad zaten kullanılıyor: {target.name}"
            )

    temp_pairs: list[tuple[Path, Path]] = []
    final_pairs: list[tuple[Path, Path]] = []
    try:
        for source in selected:
            temp = source.with_name(
                f".__jarvis_rename_{uuid.uuid4().hex}{source.suffix.lower()}"
            )
            source.rename(temp)
            temp_pairs.append((source, temp))

        for (source, temp), target in zip(temp_pairs, targets):
            temp.rename(target)
            final_pairs.append((source, target))
        return targets
    except Exception:
        # Roll back anything already finalized, then untouched temp files.
        for original, final in reversed(final_pairs):
            if final.exists() and not original.exists():
                try:
                    final.rename(original)
                except OSError:
                    pass
        for original, temp in reversed(temp_pairs):
            if temp.exists() and not original.exists():
                try:
                    temp.rename(original)
                except OSError:
                    pass
        raise


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 10000):
        candidate = path.with_name(
            f"{path.stem}_{index}{path.suffix}"
        )
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Çıktı adı üretilemedi: {path.name}")


def convert_images(
    files: list[Path],
    target_format: str,
) -> tuple[Path, list[Path]]:
    target = str(target_format or "").upper().strip()
    if target not in {"JPG", "PNG"}:
        raise ValueError("Hedef format JPG veya PNG olmalıdır.")

    selected = [Path(p).resolve() for p in files]
    if not selected:
        raise ValueError("Dönüştürülecek görsel seçilmedi.")
    parents = {p.parent for p in selected}
    if len(parents) != 1:
        raise ValueError("Görseller aynı klasörden seçilmelidir.")

    output_dir = selected[0].parent / f"FORMAT_{target}_CIKTILARI"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    for source in selected:
        if source.suffix.lower() not in IMAGE_EXTS:
            continue
        with Image.open(source) as image:
            if target == "JPG":
                destination = _unique_destination(
                    output_dir / f"{source.stem}.jpg"
                )
                image.convert("RGB").save(
                    destination,
                    format="JPEG",
                    quality=95,
                    optimize=True,
                )
            else:
                destination = _unique_destination(
                    output_dir / f"{source.stem}.png"
                )
                image.convert("RGBA").save(
                    destination,
                    format="PNG",
                    optimize=True,
                )
            outputs.append(destination)

    return output_dir, outputs


def watermark_images(
    logo_path: Path,
    files: list[Path],
) -> tuple[Path, list[Path]]:
    logo_path = Path(logo_path).resolve()
    selected = [Path(p).resolve() for p in files]
    if not logo_path.is_file():
        raise ValueError("Filigran logosu bulunamadı.")
    if not selected:
        raise ValueError("Filigran uygulanacak görsel seçilmedi.")

    parents = {p.parent for p in selected}
    if len(parents) != 1:
        raise ValueError("Görseller aynı klasörden seçilmelidir.")

    output_dir = selected[0].parent / "FILIGRANLI_GORSELLER"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    with Image.open(logo_path) as logo_source:
        logo = logo_source.convert("RGBA")
        for source in selected:
            with Image.open(source) as input_image:
                image = input_image.convert("RGBA")
                wm_width = max(1, int(image.width * 0.20))
                scale = wm_width / max(1, logo.width)
                wm_height = max(1, int(logo.height * scale))
                resized = logo.resize(
                    (wm_width, wm_height),
                    Image.Resampling.LANCZOS,
                )
                pad_x = int(image.width * 0.05)
                pad_y = int(image.height * 0.05)
                position = (
                    max(0, image.width - wm_width - pad_x),
                    max(0, image.height - wm_height - pad_y),
                )
                composed = image.copy()
                composed.alpha_composite(resized, position)

                destination = _unique_destination(
                    output_dir / source.name
                )
                if destination.suffix.lower() in {".jpg", ".jpeg"}:
                    composed.convert("RGB").save(
                        destination,
                        quality=95,
                        optimize=True,
                    )
                else:
                    composed.save(destination)
                outputs.append(destination)

    return output_dir, outputs


def _load_cloud_settings() -> dict:
    db_path = RUNTIME_ROOT / "SABLON_V2_MIMARI" / "ayarlar.db"
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT value FROM settings WHERE key='bulut_ayarlari'"
            ).fetchone()
            conn.close()
            if row and row[0]:
                value = json.loads(row[0])
                if isinstance(value, dict):
                    return value
        except Exception:
            pass

    for candidate in (
        RUNTIME_ROOT / "ayarlar.json",
        SOURCE_ROOT / "ayarlar.json",
    ):
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            cfg = data.get("bulut_ayarlari", {})
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
    return {}


def _imgbb_keys() -> list[str]:
    cfg = _load_cloud_settings()
    configured = cfg.get("imgbb_keys") or []
    if not isinstance(configured, list):
        configured = []
    env = [
        key.strip()
        for key in os.environ.get("IMGBB_KEYS", "").split(",")
        if key.strip()
    ]
    return [
        str(key).strip()
        for key in (configured or env)
        if str(key).strip()
    ]


def upload_to_imgbb(image_path: Path, api_keys: list[str]) -> str | None:
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    for key in api_keys:
        try:
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": key, "image": encoded},
                timeout=45,
            )
            if response.status_code == 200:
                payload = response.json()
                url = (
                    payload.get("data", {}).get("url")
                    if isinstance(payload, dict)
                    else None
                )
                if url:
                    return str(url)
        except Exception:
            continue
    return None


def images_to_link_excel(files: list[Path]) -> tuple[Path, int, int]:
    selected = [Path(p).resolve() for p in files]
    if not selected:
        raise ValueError("Linke dönüştürülecek görsel seçilmedi.")
    parents = {p.parent for p in selected}
    if len(parents) != 1:
        raise ValueError("Görseller aynı klasörden seçilmelidir.")

    keys = _imgbb_keys()
    if not keys:
        raise RuntimeError(
            "ImgBB anahtarı bulunamadı. Sistem ayarlarında "
            "bulut_ayarlari.imgbb_keys yapılandırılmalı."
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Görsel Linkleri"
    sheet.append(["Dosya Adı", "Resim Linki", "Sistem Dosya Yolu"])

    success = 0
    failed = 0
    for index, source in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] Yükleniyor: {source.name}")
        url = upload_to_imgbb(source, keys)
        if url:
            success += 1
            sheet.append([source.name, url, str(source)])
        else:
            failed += 1
            sheet.append([source.name, "YÜKLEME_HATASI", str(source)])

    output = _unique_destination(
        selected[0].parent / "Gorsel_Linkleri.xlsx"
    )
    workbook.save(output)
    return output, success, failed


def _load_seo_module():
    script = (
        SOURCE_ROOT
        / "ÜRÜN ADI YAZDIRMA BOTU"
        / "Benzersiz-ürün-adlari-yaz.py"
    )
    if not script.is_file():
        raise FileNotFoundError("SEO üretici scripti bulunamadı.")
    spec = importlib.util.spec_from_file_location("jarvis_seo_tool", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("SEO üretici yüklenemedi.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate_seo_excel(
    count: int,
    mode: str,
    output_dir: Path,
) -> Path:
    count = max(1, min(int(count), 5000))
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    module = _load_seo_module()

    if mode == "titles":
        groups = module.urun_isim_dosyasini_oku()
        values = module.isimleri_uret(count, groups)
        if not values:
            raise RuntimeError("SEO ürün adı üretilemedi.")
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "SEO Ürün Adları"
        sheet.append(["Sıra", "Ürün Adı", "Karakter Sayısı"])
        for index, value in enumerate(values, start=1):
            sheet.append([index, value, len(value)])
        output = _unique_destination(
            output_dir / "SEO_Urun_Adlari.xlsx"
        )
    elif mode == "descriptions":
        sentences, keywords = module.aciklama_dosyasini_oku()
        values = module.aciklamalari_uret(
            count,
            sentences,
            keywords,
        )
        if not values:
            raise RuntimeError("SEO ürün açıklaması üretilemedi.")
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "SEO Açıklamalar"
        sheet.append(["Sıra", "Ürün Açıklaması"])
        for index, value in enumerate(values, start=1):
            sheet.append([index, value])
        output = _unique_destination(
            output_dir / "SEO_Urun_Aciklamalari.xlsx"
        )
    else:
        raise ValueError("Bilinmeyen SEO modu.")

    workbook.save(output)
    return output


def _open_folder(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))
    except Exception:
        pass


def interactive_rename() -> int:
    root, filedialog, messagebox, simpledialog = _ui()
    try:
        files = filedialog.askopenfilenames(
            title="İsimlendirilecek Görselleri Seçin",
            filetypes=[
                ("Görseller", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        if not files:
            return 0
        prefix = simpledialog.askstring(
            "Görsel İsimlendirici",
            "Görseller hangi kelime ile başlasın?\nÖrnek: Tablo_",
            initialvalue="Gorsel_",
            parent=root,
        )
        if prefix is None:
            return 0
        outputs = rename_images(
            [Path(p) for p in files],
            prefix,
            RUNTIME_ROOT,
        )
        _open_folder(outputs[0].parent)
        messagebox.showinfo(
            "Tamamlandı",
            f"{len(outputs)} görsel yeniden adlandırıldı.\n"
            f"İlk dosya: {outputs[0].name}",
            parent=root,
        )
        return 0
    except Exception as exc:
        messagebox.showerror("İsimlendirme Hatası", str(exc), parent=root)
        return 1
    finally:
        root.destroy()


def interactive_convert() -> int:
    root, filedialog, messagebox, simpledialog = _ui()
    try:
        files = filedialog.askopenfilenames(
            title="Dönüştürülecek Görselleri Seçin",
            filetypes=[
                ("Görseller", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        if not files:
            return 0
        target = simpledialog.askstring(
            "Format Çevirici",
            "Hedef formatı yazın: JPG veya PNG",
            initialvalue="JPG",
            parent=root,
        )
        if target is None:
            return 0
        output_dir, outputs = convert_images(
            [Path(p) for p in files],
            target,
        )
        _open_folder(output_dir)
        messagebox.showinfo(
            "Tamamlandı",
            f"{len(outputs)} görsel dönüştürüldü.\n"
            f"Çıktı: {output_dir}",
            parent=root,
        )
        return 0
    except Exception as exc:
        messagebox.showerror("Format Hatası", str(exc), parent=root)
        return 1
    finally:
        root.destroy()


def interactive_watermark() -> int:
    root, filedialog, messagebox, _simpledialog = _ui()
    try:
        logo = filedialog.askopenfilename(
            title="1. Adım: Filigran Logosunu Seçin",
            filetypes=[("PNG Görseli", "*.png"), ("Görseller", "*.*")],
        )
        if not logo:
            return 0
        files = filedialog.askopenfilenames(
            title="2. Adım: Filigran Uygulanacak Görselleri Seçin",
            filetypes=[
                ("Görseller", "*.png *.jpg *.jpeg *.webp"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        if not files:
            return 0
        output_dir, outputs = watermark_images(
            Path(logo),
            [Path(p) for p in files],
        )
        _open_folder(output_dir)
        messagebox.showinfo(
            "Tamamlandı",
            f"{len(outputs)} görsele filigran uygulandı.\n"
            f"Çıktı: {output_dir}",
            parent=root,
        )
        return 0
    except Exception as exc:
        messagebox.showerror("Filigran Hatası", str(exc), parent=root)
        return 1
    finally:
        root.destroy()


def interactive_links() -> int:
    root, filedialog, messagebox, _simpledialog = _ui()
    try:
        files = filedialog.askopenfilenames(
            title="Linke Dönüştürülecek Görselleri Seçin",
            filetypes=[
                ("Görseller", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        if not files:
            return 0
        output, success, failed = images_to_link_excel(
            [Path(p) for p in files]
        )
        _open_folder(output.parent)
        if failed:
            messagebox.showwarning(
                "İşlem Tamamlandı",
                f"Başarılı: {success}\nHatalı: {failed}\n"
                f"Excel: {output}",
                parent=root,
            )
            return 1
        messagebox.showinfo(
            "Tamamlandı",
            f"{success} görsel linke dönüştürüldü.\nExcel: {output}",
            parent=root,
        )
        return 0
    except Exception as exc:
        messagebox.showerror("Link Dönüştürme Hatası", str(exc), parent=root)
        return 1
    finally:
        root.destroy()


def interactive_seo(mode: str) -> int:
    root, filedialog, messagebox, simpledialog = _ui()
    try:
        count = simpledialog.askinteger(
            "SEO Üretici",
            "Kaç adet üretilecek?",
            initialvalue=10,
            minvalue=1,
            maxvalue=5000,
            parent=root,
        )
        if not count:
            return 0
        output_dir = filedialog.askdirectory(
            title="Excel Çıktısının Kaydedileceği Klasörü Seçin"
        )
        if not output_dir:
            return 0
        output = generate_seo_excel(
            count,
            mode,
            Path(output_dir),
        )
        _open_folder(output.parent)
        label = (
            "SEO ürün adı"
            if mode == "titles"
            else "SEO ürün açıklaması"
        )
        messagebox.showinfo(
            "Tamamlandı",
            f"{count} hedefiyle {label} üretildi.\nExcel: {output}",
            parent=root,
        )
        return 0
    except Exception as exc:
        messagebox.showerror("SEO Üretim Hatası", str(exc), parent=root)
        return 1
    finally:
        root.destroy()


def interactive_4k() -> int:
    root, filedialog, messagebox, _simpledialog = _ui()
    try:
        input_dir = filedialog.askdirectory(
            title="4K Yapılacak Görsellerin Klasörünü Seçin"
        )
        if not input_dir:
            return 0
        source = Path(input_dir).resolve()
        output = source / "4K_POWER_TOOL_OUTPUT"
        script = (
            SOURCE_ROOT
            / "99_SISTEM_MOTORLARI_VE_KODLAR"
            / "SISTEM_MOTORU"
            / "kalite_artirici_otomasyon.py"
        )
        if not script.is_file():
            raise FileNotFoundError("4K kalite motoru bulunamadı.")

        cmd = [
            sys.executable,
            str(script),
            "--input",
            str(source),
            "--output",
            str(output),
            "--force-ai",
        ]
        kwargs = {"cwd": str(SOURCE_ROOT)}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen(cmd, **kwargs)
        messagebox.showinfo(
            "4K İşlemi Başlatıldı",
            "4K kalite işlemi ayrı pencerede çalışıyor.\n"
            f"Çıktı klasörü: {output}",
            parent=root,
        )
        return 0
    except Exception as exc:
        messagebox.showerror("4K Kalite Hatası", str(exc), parent=root)
        return 1
    finally:
        root.destroy()


TOOLS = {
    "rename": interactive_rename,
    "convert": interactive_convert,
    "watermark": interactive_watermark,
    "4k": interactive_4k,
    "links": interactive_links,
    "seo_titles": lambda: interactive_seo("titles"),
    "seo_descriptions": lambda: interactive_seo("descriptions"),
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bağımsız e-ticaret görsel araçları."
    )
    parser.add_argument("tool", choices=sorted(TOOLS))
    args = parser.parse_args()
    return int(TOOLS[args.tool]())


if __name__ == "__main__":
    raise SystemExit(main())
