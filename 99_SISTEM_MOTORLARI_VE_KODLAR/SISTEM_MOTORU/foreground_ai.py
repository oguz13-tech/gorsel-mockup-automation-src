import os
import sys
import json
import logging
import cv2
import numpy as np
from pathlib import Path
from contextlib import nullcontext
from PIL import Image

import torch

logger = logging.getLogger("ForegroundAI")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s][ForegroundAI] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

ENGINE_DIR = Path(__file__).resolve().parent
MASKS_DIR = ENGINE_DIR / "masks"
MASKS_DIR.mkdir(parents=True, exist_ok=True)


class ForegroundAIEngine:
    """
    Canva Magic Grab / Sihirli Silgi mantığında çalışan
    Grounding DINO + SAM 2.1 Akıllı Ön Plan / Occlusion Motoru.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        
        self.dino_proc = None
        self.dino_model = None
        self.sam_proc = None
        self.sam_model = None
        self.models_loaded = False
        
        self.default_prompts = (
            "food. fruit. vegetable. tomato. garlic. knife. utensil. "
            "hand. plant. flower. decoration. kitchen object. accessory. lemon. herb."
        )

    def _autocast_context(self):
        """CUDA'da fp16 autocast, CPU'da güvenli no-op context döndür."""
        if self.device == "cuda":
            return torch.autocast(device_type="cuda", dtype=self.dtype)
        return nullcontext()

    def _ensure_models_loaded(self):
        """Lazy loading: Modeller yalnızca ilk ihtiyaç duyulduğunda GPU/RAM'e yüklenir."""
        if self.models_loaded:
            return

        logger.info(f"AI Modelleri yükleniyor... (Cihaz: {self.device}, Dtype: {self.dtype})")
        
        try:
            from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
            from transformers import Sam2Processor, Sam2Model

            # 1. Grounding DINO (Hafif ve Hızlı ~170MB)
            dino_id = "IDEA-Research/grounding-dino-tiny"
            logger.info(f"Grounding DINO yükleniyor: {dino_id}")
            self.dino_proc = AutoProcessor.from_pretrained(dino_id)
            self.dino_model = AutoModelForZeroShotObjectDetection.from_pretrained(dino_id).to(
                device=self.device
            )
            self.dino_model.eval()

            # 2. SAM 2.1 Hiera Small (~180MB)
            sam_id = "facebook/sam2.1-hiera-small"
            logger.info(f"SAM 2.1 yükleniyor: {sam_id}")
            self.sam_proc = Sam2Processor.from_pretrained(sam_id)
            self.sam_model = Sam2Model.from_pretrained(sam_id).to(
                device=self.device
            )
            self.sam_model.eval()

            self.models_loaded = True
            logger.info("Grounding DINO ve SAM 2.1 başarıyla hafızaya alındı!")
        except Exception as e:
            logger.error(f"AI Modelleri yüklenirken hata oluştu: {e}")
            raise e

    def get_mask_path_for_template(self, template_name: str) -> Path:
        """Şablon adına göre ön plan maske dosya yolunu döner."""
        stem = Path(template_name).stem
        return MASKS_DIR / f"{stem}_foreground_mask.png"

    def load_cached_mask(self, template_name: str) -> np.ndarray | None:
        """Diskte kayıtlı maske varsa okur (0..255 uint8)."""
        mask_path = self.get_mask_path_for_template(template_name)
        if mask_path.exists():
            try:
                mask = cv2.imdecode(np.fromfile(str(mask_path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
                if mask is not None:
                    return mask
            except Exception as e:
                logger.warning(f"Cache maske okunamadı: {e}")
        return None

    def save_mask_to_cache(self, template_name: str, mask: np.ndarray) -> str:
        """Üretilen veya düzenlenen maskeyi diske kaydeder."""
        mask_path = self.get_mask_path_for_template(template_name)
        _, enc = cv2.imencode(".png", mask)
        with open(mask_path, "wb") as f:
            f.write(enc.tobytes())
        logger.info(f"Ön plan maskesi kaydedildi: {mask_path}")
        return str(mask_path)

    def segment_point(self, image_bgr: np.ndarray, point_xy: tuple[int, int], is_positive: bool = True) -> np.ndarray | None:
        """
        Canva 'Nesne / Bileşen' Modu:
        Kullanıcının tıkladığı koordinattaki nesneyi SAM 2.1 ile anında segment eder.
        Dönüş: HxW uint8 maske (0..255)
        """
        self._ensure_models_loaded()
        h, w = image_bgr.shape[:2]
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(image_rgb)

        px, py = point_xy
        point = [[[[float(px), float(py)]]]]
        label = [[[1 if is_positive else 0]]]

        inputs = self.sam_proc(
            images=image_pil,
            input_points=point,
            input_labels=label,
            return_tensors="pt"
        ).to(self.device)

        try:
            with torch.inference_mode(), self._autocast_context():
                outputs = self.sam_model(**inputs)

            iou_scores = outputs.iou_scores[0, 0].cpu().numpy()
            best_idx = int(np.argmax(iou_scores))

            processed = self.sam_proc.post_process_masks(
                outputs.pred_masks,
                inputs["original_sizes"]
            )
            mask_tensor = processed[0][0, best_idx]
            mask_np = (mask_tensor.cpu().numpy().astype(np.uint8)) * 255
            return mask_np
        except torch.cuda.OutOfMemoryError:
            logger.error("VRAM yetersiz (OOM) - point segmentation başarısız.")
            torch.cuda.empty_cache()
            return None
        except Exception as e:
            logger.error(f"segment_point hatası: {e}")
            return None

    def segment_box(self, image_bgr: np.ndarray, box_xyxy: list[int]) -> np.ndarray | None:
        """
        Canva 'Alan' Modu:
        Kullanıcının çizdiği veya seçtiği kutunun içindeki nesneyi SAM 2.1 ile çıkarır.
        """
        self._ensure_models_loaded()
        h, w = image_bgr.shape[:2]
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(image_rgb)

        box = [[[float(c) for c in box_xyxy]]]
        inputs = self.sam_proc(
            images=image_pil,
            input_boxes=box,
            return_tensors="pt"
        ).to(self.device)

        try:
            with torch.inference_mode(), self._autocast_context():
                outputs = self.sam_model(**inputs)

            iou_scores = outputs.iou_scores[0, 0].cpu().numpy()
            best_idx = int(np.argmax(iou_scores))

            processed = self.sam_proc.post_process_masks(
                outputs.pred_masks,
                inputs["original_sizes"]
            )
            mask_tensor = processed[0][0, best_idx]
            mask_np = (mask_tensor.cpu().numpy().astype(np.uint8)) * 255
            return mask_np
        except torch.cuda.OutOfMemoryError:
            logger.error("VRAM yetersiz (OOM) - box segmentation başarısız.")
            torch.cuda.empty_cache()
            return None
        except Exception as e:
            logger.error(f"segment_box hatası: {e}")
            return None

    def detect_foreground(
        self,
        image_bgr: np.ndarray,
        surface_polygon: list,
        prompts: str | list | None = None,
        box_threshold: float = 0.20,
        text_threshold: float = 0.20,
        min_surface_overlap: float = 0.02,
        feather: float = 1.0
    ) -> dict:
        """
        Canva 'Ön Plan' / Otomatik Tespit Modu:
        1. Grounding DINO ile şablondaki olası fiziksel nesneleri bulur.
        2. Baskı alanı (surface_polygon) ile kesişen nesneleri filtreler.
        3. SAM 2.1 ile milimetrik pürüzsüz maskeleri çıkarır.
        4. Nesneleri birleştirir, kenar yumuşatması (feathering) uygular.
        """
        h, w = image_bgr.shape[:2]
        if surface_polygon is None or len(surface_polygon) < 3:
            return {
                "success": False,
                "mask": None,
                "objects": [],
                "confidence": 0.0,
                "reason": "Gecersiz surface_polygon"
            }

        # 1. Surface Mask (Baskı Alanı)
        pts = np.array(surface_polygon, dtype=np.int32)
        surface_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(surface_mask, [pts], 255)
        surface_area = float(np.count_nonzero(surface_mask))
        if surface_area <= 0:
            return {
                "success": False,
                "mask": None,
                "objects": [],
                "confidence": 0.0,
                "reason": "Bos surface_polygon"
            }

        min_surface_overlap = float(np.clip(min_surface_overlap, 0.0, 1.0))

        # Resolution-relative surface margin catches knives/utensils that just
        # cross the printable boundary without baking in one pixel size.
        margin_px = max(9, int(round(min(h, w) * 0.025)))
        if margin_px % 2 == 0:
            margin_px += 1
        surface_dilated = cv2.dilate(
            surface_mask,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (margin_px, margin_px)),
        )

        # 2. Text Prompts
        if prompts is None:
            prompt_text = self.default_prompts
        elif isinstance(prompts, list):
            prompt_text = ". ".join(prompts) + "."
        else:
            prompt_text = str(prompts)

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(image_rgb)

        try:
            self._ensure_models_loaded()
        except Exception as e:
            return {
                "success": False,
                "mask": None,
                "objects": [],
                "confidence": 0.0,
                "reason": f"Model yukleme hatasi: {e}"
            }

        # 3. Grounding DINO ile Nesne Tespiti
        try:
            dino_inputs = self.dino_proc(
                images=image_pil,
                text=prompt_text.lower(),
                return_tensors="pt"
            ).to(self.device)

            with torch.inference_mode(), self._autocast_context():
                dino_outputs = self.dino_model(**dino_inputs)

            dino_results = self.dino_proc.post_process_grounded_object_detection(
                dino_outputs,
                input_ids=dino_inputs.input_ids,
                threshold=box_threshold,
                text_threshold=text_threshold,
                target_sizes=[(h, w)]
            )[0]

            raw_boxes = dino_results["boxes"].cpu().numpy()
            raw_scores = dino_results["scores"].cpu().numpy()
            raw_labels = dino_results.get("text_labels", dino_results.get("labels", []))
            logger.info(f"Grounding DINO toplam {len(raw_boxes)} aday nesne tespit etti.")
        except torch.cuda.OutOfMemoryError:
            logger.error("VRAM yetersiz (OOM) - Grounding DINO başarısız.")
            torch.cuda.empty_cache()
            return {
                "success": False,
                "mask": None,
                "objects": [],
                "confidence": 0.0,
                "reason": "CUDA OutOfMemory"
            }
        except Exception as e:
            logger.error(f"DINO inference hatası: {e}")
            return {
                "success": False,
                "mask": None,
                "objects": [],
                "confidence": 0.0,
                "reason": str(e)
            }

        # 4. Surface-Overlap Filtresi (Baskı alanıyla kesişmeyenleri eler)
        candidate_boxes = []
        candidate_metadata = []

        for b, s, l in zip(raw_boxes, raw_scores, raw_labels):
            x1, y1, x2, y2 = [int(np.clip(v, 0, max_dim)) for v, max_dim in zip(b, [w, h, w, h])]
            bw = x2 - x1
            bh = y2 - y1
            if bw < 20 or bh < 20:
                continue

            # Bu kutunun yüzeyle kesişimi var mı?
            box_mask = np.zeros((h, w), dtype=np.uint8)
            box_mask[y1:y2, x1:x2] = 255
            
            # Yüzeyle doğrudan veya sınır tamponuyla kesişim
            intersection = cv2.bitwise_and(box_mask, surface_dilated)
            intersect_px = int(np.count_nonzero(intersection))
            box_area = max(1, bw * bh)
            box_overlap = intersect_px / float(box_area)
            min_intersection_px = max(48, int((w * h) * 0.00002))
            if intersect_px < min_intersection_px or box_overlap < min_surface_overlap:
                continue

            # Tahtanın/yüzeyin kendisini kapsayan dev kutuları eler.
            if bw > w * 0.88 and bh > h * 0.88:
                continue

            candidate_boxes.append([x1, y1, x2, y2])
            candidate_metadata.append({
                "label": str(l),
                "score": float(s),
                "box": [x1, y1, x2, y2],
                "box_surface_overlap": round(box_overlap, 4),
            })

        if not candidate_boxes:
            logger.info("Baskı yüzeyini kapatan hiçbir ön plan nesnesi bulunamadı.")
            return {
                "success": True,
                "mask": np.zeros((h, w), dtype=np.uint8),
                "objects": [],
                "confidence": 0.95,
                "reason": "no_foreground_object_detected"
            }

        logger.info(f"Surface ile kesişen {len(candidate_boxes)} nesne SAM 2.1 ile segment ediliyor...")

        # 5. SAM 2.1 ile Bounding Box Segmentasyonu
        selected_masks = []
        final_objects = []

        try:
            for box, meta in zip(candidate_boxes, candidate_metadata):
                mask_np = self.segment_box(image_bgr, box)
                if mask_np is None:
                    continue

                # Maskenin yüzey içi ve yüzey dışı pikselleri
                inside_px = np.count_nonzero(cv2.bitwise_and(mask_np, surface_mask))
                outside_px = np.count_nonzero(cv2.bitwise_and(mask_np, cv2.bitwise_not(surface_mask)))
                total_px = inside_px + outside_px

                if total_px == 0:
                    continue

                overlap_ratio = inside_px / float(total_px)
                surface_fraction = inside_px / max(surface_area, 1.0)
                min_inside_px = max(64, int(surface_area * 0.0005))
                min_outside_px = max(64, int((w * h) * 0.00002))

                # Strong case: a physical object crosses the print boundary.
                crosses_boundary = (
                    inside_px >= min_inside_px
                    and outside_px >= min_outside_px
                    and overlap_ratio >= min_surface_overlap
                    and total_px <= surface_area * 0.65
                )

                # Important real-world case: tomato/garlic/etc. can sit entirely
                # on top of a cutting board. The old rule rejected these because
                # it required outside pixels. Accept only compact, high-confidence
                # interior detections to limit printed-art false positives.
                interior_object = (
                    inside_px >= min_inside_px
                    and overlap_ratio >= 0.94
                    and float(meta["score"]) >= max(0.40, box_threshold + 0.15)
                    and total_px <= surface_area * 0.30
                    and surface_fraction <= 0.30
                )

                is_occluder = crosses_boundary or interior_object

                if is_occluder:
                    selected_masks.append(mask_np)
                    meta["surface_overlap"] = round(overlap_ratio, 3)
                    meta["surface_fraction"] = round(surface_fraction, 4)
                    meta["mask_area"] = int(total_px)
                    meta["acceptance_mode"] = (
                        "cross_boundary" if crosses_boundary else "interior_high_confidence"
                    )
                    final_objects.append(meta)
                    logger.info(
                        f"  + KABUL EDILDI: '{meta['label']}' "
                        f"(score: {meta['score']:.2f}, in={inside_px}, out={outside_px}, "
                        f"overlap={overlap_ratio:.1%}, mode={meta['acceptance_mode']})"
                    )
                else:
                    logger.info(
                        f"  - REDDEDILDI: '{meta['label']}' "
                        f"(in={inside_px}, out={outside_px}, overlap={overlap_ratio:.1%})"
                    )
        except Exception as e:
            logger.error(f"SAM 2.1 segmentasyon hatası: {e}")

        if not selected_masks:
            return {
                "success": True,
                "mask": np.zeros((h, w), dtype=np.uint8),
                "objects": [],
                "confidence": 0.90,
                "reason": "no_objects_overlapped_surface"
            }

        # 6. Maskeleri Birleştir (Bitwise OR)
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        for m in selected_masks:
            combined_mask = cv2.bitwise_or(combined_mask, m)

        # 7. Mask Cleanup & Feathering
        # Küçük delikleri kapat (morph close)
        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        cleaned = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, k_close)

        # Küçük saçak ve pürüzleri temizle
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned)
        final_mask = np.zeros((h, w), dtype=np.uint8)
        min_component_area = max(50, int((w * h) * 0.00002))
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_component_area:
                final_mask[labels == i] = 255

        # Feathering (Kenar yumuşatma)
        if feather > 0.1:
            k_size = int(feather * 6) | 1
            blurred = cv2.GaussianBlur(final_mask, (k_size, k_size), sigmaX=feather, sigmaY=feather)
            final_mask = blurred

        avg_conf = float(np.mean([o["score"] for o in final_objects])) if final_objects else 0.85

        return {
            "success": True,
            "mask": final_mask,
            "objects": final_objects,
            "confidence": round(avg_conf, 3),
            "reason": "ok"
        }
