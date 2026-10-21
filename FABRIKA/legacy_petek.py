#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PETEK DOLABI: isolated, safe 13-slot perspective/curvature mockup renderer.

Engineering choice: OpenCV homography for planar faces, tile-wise inverse remap
of a bilinear/Bezier surface for curved faces. Unlike an arbitrary AI inpaint,
this is deterministic, fast on CPU, and does not require model weights.

Safety: original templates and artwork are read-only. SQLite, logs and outputs
live only in PETEK_DOLABI_LOCAL beside this script; outputs are create-only.
Source slits are visually covered by opaque artwork, not individually detected.
A reviewed four-corner front-surface geometry is mandatory for real images.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from typing import Iterator
import warnings

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError


# All changeable configuration and numeric policy constants are centralized.
@dataclass(frozen=True)
class Settings:
    """Validated app, rendering, image and persistence policy."""
    category: str = "06_Petek_Dolabi"
    recipe_version: str = "petek-13-v3-20261020"
    state_folder: str = "PETEK_DOLABI_LOCAL"
    image_extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp")
    output_width: int = 1200
    output_height: int = 1600
    max_input_bytes: int = 45_000_000
    max_geometry_bytes: int = 32_768
    hash_chunk_bytes: int = 1_048_576
    output_key_length: int = 24
    max_image_pixels: int = 28_000_000
    max_front_dimension: int = 1700
    min_front_dimension: int = 440
    min_source_side: int = 64
    min_edge_pixels: float = 35.0
    min_panel_area_fraction: float = 0.012
    max_curve_displacement_fraction: float = 0.18
    max_artwork_aspect_mismatch: float = 2.3
    max_jobs_per_batch: int = 5000
    tile_height: int = 160
    inverse_iterations: int = 11
    inverse_tolerance_pixels: float = 1.25
    inverse_max_fraction_step: float = 0.19
    edge_feather_pixels: float = 1.25
    panel_blurred_fill_fraction: float = 0.085
    marketplace_blur_fraction: float = 0.045
    curve_boundary_samples: int = 201
    curve_grid_columns: int = 25
    curve_grid_rows: int = 17
    jacobian_grid_columns: int = 9
    jacobian_grid_rows: int = 7
    min_jacobian: float = 35.0
    inverse_zero_epsilon: float = 0.0001
    curve_inner_guard_kernel: int = 5
    slot_count: int = 13
    slot_side_margin: float = 0.095
    slot_top_margin: float = 0.14
    slot_bottom_margin: float = 0.13
    slot_width_fraction: float = 0.009
    slot_length_variation: float = 0.012
    slot_supersample: int = 2
    slot_blur_sigma: float = 0.52
    slot_edge_highlight: float = 10.0
    slot_interior_bgr: tuple[int, int, int] = (48, 52, 57)
    log_max_bytes: int = 3_000_000
    log_backups: int = 3
    sqlite_timeout_seconds: int = 10
    sample_scene_width: int = 900
    sample_scene_height: int = 1200
    sample_art_width: int = 960
    sample_art_height: int = 830
    demo_old_slot_count: int = 9
    cv_border_margin: int = 3
    mask_threshold: float = 0.45


CONFIG = Settings()


# Exception raised for a rejected input or geometry without modifying sources.
class RenderRejected(ValueError):
    """Indicate that processing was safely blocked (fail-closed)."""


# Schema for reviewed source-panel coordinates and curved reference points.
@dataclass(frozen=True)
class PanelGeometry:
    """TL, TR, BR, BL coordinates and optional reviewed edge midpoints."""
    category: str
    quad: tuple[tuple[float, float], ...]
    reviewed: bool
    top_mid: tuple[float, float] | None = None
    bottom_mid: tuple[float, float] | None = None
    template_sha256: str | None = None

    @classmethod
    def from_file(cls, path: Path) -> PanelGeometry:
        """Parse a JSON geometry document without executing arbitrary code."""
        try:
            if path.is_symlink() or not path.is_file():
                raise RenderRejected("Geometry must be a regular, non-symlink JSON file")
            if path.stat().st_size > CONFIG.max_geometry_bytes:
                raise RenderRejected("Geometry JSON exceeds the maximum supported size")
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise RenderRejected("Geometry JSON must be an object")
            allowed = {"category", "quad", "reviewed", "top_mid", "bottom_mid", "template_sha256"}
            if set(document) - allowed:
                raise RenderRejected("Unsupported geometry keys")
            quad = document.get("quad")
            if not isinstance(quad, list) or len(quad) != 4:
                raise RenderRejected("quad must contain four [x,y] points")
            def pair(value: object) -> tuple[float, float]:
                """Validate a finite floating-point image coordinate pair."""
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise RenderRejected("Expected [x,y] coordinate pair")
                if any(isinstance(z, bool) or not isinstance(z, (int, float)) for z in value):
                    raise RenderRejected("Coordinates must be numeric")
                result = (float(value[0]), float(value[1]))
                if not all(math.isfinite(z) for z in result):
                    raise RenderRejected("Non-finite coordinates")
                return result
            top = document.get("top_mid")
            bottom = document.get("bottom_mid")
            if (top is None) != (bottom is None):
                raise RenderRejected("Curved faces require both midpoints")
            if type(document.get("reviewed")) is not bool:
                raise RenderRejected("reviewed must be true or false")
            digest = document.get("template_sha256")
            if digest is not None and (not isinstance(digest, str) or len(digest) != 64
                                       or any(ch not in "0123456789abcdef" for ch in digest.lower())):
                raise RenderRejected("Invalid template SHA-256")
            return cls(category=document.get("category"),
                       quad=tuple(pair(point) for point in quad),
                       reviewed=document["reviewed"],
                       top_mid=pair(top) if top is not None else None,
                       bottom_mid=pair(bottom) if bottom is not None else None,
                       template_sha256=digest.lower() if digest else None)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RenderRejected(f"Cannot load geometry: {exc}") from exc


# Pure mathematical layout of thirteen evenly spaced vertical apertures.
class SlotLayout:
    """Generate equal-spaced and mirror-symmetric normalized slot positions."""
    def __init__(self, policy: Settings = CONFIG):
        """Attach shared immutable configuration."""
        self.policy = policy

    def positions(self) -> list[tuple[float, float, float]]:
        """Return (horizontal center, upper bound, lower bound) for all slots."""
        p = self.policy
        usable = 1 - 2 * p.slot_side_margin - p.slot_count * p.slot_width_fraction
        if usable <= 0 or p.slot_count < 2:
            raise RenderRejected("Invalid slot layout policy")
        spacing = usable / (p.slot_count - 1)
        centers = [p.slot_side_margin + p.slot_width_fraction / 2
                   + index * (spacing + p.slot_width_fraction)
                   for index in range(p.slot_count)]
        result = []
        center_index = (p.slot_count - 1) / 2
        for index, x in enumerate(centers):
            symmetry = 1 - abs(index - center_index) / max(center_index, 1)
            adjustment = p.slot_length_variation * symmetry
            top = p.slot_top_margin + adjustment / 2
            bottom = 1 - p.slot_bottom_margin - adjustment / 2
            if not 0 < top < bottom < 1:
                raise RenderRejected("Invalid slot vertical margins")
            result.append((x, top, bottom))
        return result

    def coverage(self, width: int, height: int) -> np.ndarray:
        """Draw rounded openings with supersampling and anti-aliased edges."""
        p = self.policy
        scale = p.slot_supersample
        if scale < 1 or width < p.min_front_dimension // 2 or height < p.min_front_dimension // 2:
            raise RenderRejected("Invalid slot raster dimensions")
        mask = np.zeros((height * scale, width * scale), dtype=np.uint8)
        thickness = max(2, round(p.slot_width_fraction * width * scale))
        radius = max(1, thickness // 2)
        for x, top, bottom in self.positions():
            cx = round(x * (width - 1) * scale)
            y0 = round(top * (height - 1) * scale)
            y1 = round(bottom * (height - 1) * scale)
            cv2.line(mask, (cx, y0 + radius), (cx, y1 - radius), 255, thickness, cv2.LINE_AA)
            cv2.circle(mask, (cx, y0 + radius), radius, 255, -1, cv2.LINE_AA)
            cv2.circle(mask, (cx, y1 - radius), radius, 255, -1, cv2.LINE_AA)
        return cv2.resize(mask, (width, height), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


# Persistent records of isolated outputs; never opens a production SQLite DB.
class LocalStore:
    """Store only local render receipts with unique input-derived job keys."""
    def __init__(self, directory: Path, policy: Settings = CONFIG):
        """Create private output/data directories adjacent to the standalone app."""
        if directory.is_symlink():
            raise RenderRejected("Local database root cannot be a symlink")
        self.root = directory.resolve()
        if self.root.name != policy.state_folder:
            raise RenderRejected(f"Isolated data directory must be {policy.state_folder}")
        self.root.mkdir(parents=True, exist_ok=True)
        self.output = self.root / "outputs"
        if self.output.is_symlink():
            raise RenderRejected("Output folder cannot be a symlink")
        self.output.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "petek_mock.sqlite3"
        if self.database.is_symlink():
            raise RenderRejected("Local database cannot be a symlink")
        self.policy = policy
        try:
            with sqlite3.connect(self.database, timeout=policy.sqlite_timeout_seconds) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS render_jobs ("
                             "job_key TEXT PRIMARY KEY, output_name TEXT NOT NULL UNIQUE, "
                             "output_sha256 TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        except sqlite3.Error as exc:
            raise RenderRejected(f"Local database cannot initialize: {exc}") from exc

    def previously_rendered(self, key: str, target: Path) -> bool:
        """Reuse only a record with an unchanged matching image checksum."""
        if target.is_symlink():
            raise RenderRejected("Refusing symlink output even when a receipt exists")
        try:
            with sqlite3.connect(self.database, timeout=self.policy.sqlite_timeout_seconds) as conn:
                row = conn.execute("SELECT output_name, output_sha256 FROM render_jobs WHERE job_key=?",
                                   (key,)).fetchone()
            if row is None:
                # The creator may have crashed after O_EXCL write and before
                # its SQLite receipt. Caller may adopt only a byte-identical
                # re-encoded output; a mismatched orphan remains untouched.
                return False
            if target.name != row[0] or not target.is_file() or file_sha256(target) != row[1]:
                raise RenderRejected("Stored output differs from its receipt")
            return True
        except sqlite3.Error as exc:
            raise RenderRejected(f"Local receipt lookup failed: {exc}") from exc

    def register(self, key: str, target: Path) -> None:
        """Commit a hash-verified create-only output receipt to local SQLite."""
        try:
            with sqlite3.connect(self.database, timeout=self.policy.sqlite_timeout_seconds) as conn:
                conn.execute("INSERT INTO render_jobs(job_key, output_name, output_sha256) VALUES(?,?,?)",
                             (key, target.name, file_sha256(target)))
        except sqlite3.IntegrityError as exc:
            raise RenderRejected("Concurrent or duplicated render receipt") from exc
        except sqlite3.Error as exc:
            raise RenderRejected(f"Receipt registration failed: {exc}") from exc

    def stats(self) -> int:
        """Return the number of isolated, completed job receipts."""
        try:
            with sqlite3.connect(self.database, timeout=self.policy.sqlite_timeout_seconds) as conn:
                return int(conn.execute("SELECT COUNT(*) FROM render_jobs").fetchone()[0])
        except sqlite3.Error as exc:
            raise RenderRejected(f"Cannot read local statistics: {exc}") from exc


# Unicode-safe immutable file hashing performed in bounded-size chunks.
def file_sha256(path: Path) -> str:
    """Compute SHA-256 without loading the whole file into RAM."""
    digest = sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(CONFIG.hash_chunk_bytes), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError as exc:
        raise RenderRejected(f"Cannot hash {path}: {exc}") from exc


# Image adapter that enforces supported suffix, dimensions and input size.
def read_image(path: Path, policy: Settings = CONFIG) -> np.ndarray:
    """Inspect file headers before OpenCV decode to reject oversized images early."""
    try:
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in policy.image_extensions:
            raise RenderRejected(f"Invalid or missing regular image: {path}")
        size_bytes = path.stat().st_size
        if size_bytes <= 0 or size_bytes > policy.max_input_bytes:
            raise RenderRejected("Image byte size outside safety limits")
        # Decode-bomb guard: PIL reads only the header, before OpenCV allocates
        # the full uncompressed image. Treat Pillow warnings as hard failures.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as header:
                width, height = header.size
                if min(width, height) < policy.min_source_side or width * height > policy.max_image_pixels:
                    raise RenderRejected("Image header dimensions outside safety limits")
        image = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
            raise RenderRejected("Cannot decode 8-bit three-channel image")
        height, width = image.shape[:2]
        if min(height, width) < policy.min_source_side or height * width > policy.max_image_pixels:
            raise RenderRejected("Decoded image dimensions outside safety limits")
        return image
    except (OSError, UnidentifiedImageError, Image.DecompressionBombWarning,
            Image.DecompressionBombError, ValueError) as exc:
        if isinstance(exc, RenderRejected):
            raise
        raise RenderRejected(f"Cannot safely read image: {exc}") from exc


# Create-only, durable file writing that never uses replace over an existing file.
def save_new_image(path: Path, image: np.ndarray) -> None:
    """Encode and write PNG with O_EXCL, flush and fsync; never overwrite."""
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RenderRejected("PNG encoding failed")
    owned = False
    try:
        with path.open("xb") as stream:
            owned = True
            stream.write(encoded.tobytes())
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise RenderRejected(f"Output already exists: {path.name}") from exc
    except OSError as exc:
        if owned:
            try:
                path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                logging.getLogger("petek").warning("Incomplete own output cleanup failed: %s", cleanup_error)
        raise RenderRejected(f"Cannot create new PNG: {exc}") from exc


# Geometric validation that prevents incorrect/cross-category source routing.
class GeometryGuard:
    """Check review status, SHA binding, quad winding and curve degeneracy."""
    def __init__(self, policy: Settings = CONFIG):
        """Hold the immutable geometric safety thresholds."""
        self.policy = policy

    def validate(self, geometry: PanelGeometry, shape: tuple[int, ...], digest: str) -> np.ndarray:
        """Return a validated float32 TL/TR/BR/BL array or reject safely."""
        if geometry.category != self.policy.category or geometry.reviewed is not True:
            raise RenderRejected("Unreviewed geometry or incorrect category")
        if geometry.template_sha256 and geometry.template_sha256 != digest:
            raise RenderRejected("Template hash has changed since review")
        pts = np.asarray(geometry.quad, dtype=np.float64)
        height, width = shape[:2]
        if pts.shape != (4, 2) or not np.isfinite(pts).all():
            raise RenderRejected("Invalid quad coordinates")
        if (np.any(pts < 0) or np.any(pts[:, 0] >= width) or np.any(pts[:, 1] >= height)):
            raise RenderRejected("Quad falls outside the template")
        fpts = pts.astype(np.float32)
        if not cv2.isContourConvex(fpts) or cv2.contourArea(fpts, oriented=True) <= 0:
            raise RenderRejected("Quad must be TL/TR/BR/BL without crossing")
        if (float(pts[0, 1] + pts[1, 1]) >= float(pts[2, 1] + pts[3, 1])
                or float(pts[0, 0] + pts[3, 0]) >= float(pts[1, 0] + pts[2, 0])):
            raise RenderRejected("Quad corner order is not top-left/top-right/bottom-right/bottom-left")
        if cv2.contourArea(fpts) < self.policy.min_panel_area_fraction * height * width:
            raise RenderRejected("Printable surface is too small")
        if np.min(np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1)) < self.policy.min_edge_pixels:
            raise RenderRejected("Quad has a collapsed edge")
        mids = (geometry.top_mid, geometry.bottom_mid)
        if (mids[0] is None) != (mids[1] is None):
            raise RenderRejected("Incomplete curve geometry")
        if mids[0] is not None:
            for index, middle in ((0, geometry.top_mid), (2, geometry.bottom_mid)):
                actual_mid = np.array(middle, dtype=np.float64)
                base_mid = (pts[index] + pts[(index + 1) % 4]) / 2
                if index == 2:
                    base_mid = (pts[2] + pts[3]) / 2
                distance = np.linalg.norm(actual_mid - base_mid)
                if distance > self.policy.max_curve_displacement_fraction * max(width, height):
                    raise RenderRejected("Curve midpoint displacement exceeds guard")
            self._check_surface_jacobian(fpts, geometry)
        return fpts

    def _check_surface_jacobian(self, pts: np.ndarray, geometry: PanelGeometry) -> None:
        """Sample local Jacobians to reject foldovers before inverse mapping."""
        for u in np.linspace(0.0, 1.0, self.policy.jacobian_grid_columns):
            for v in np.linspace(0.0, 1.0, self.policy.jacobian_grid_rows):
                pu, pv = surface_derivatives(float(u), float(v), pts, geometry)
                jacobian = float(pu[0] * pv[1] - pu[1] * pv[0])
                if jacobian <= self.policy.min_jacobian:
                    raise RenderRejected("Curved surface folds or becomes singular")


# Bilinear boundary blending with optional quadratic top/bottom edge offsets.
def surface_forward(u: np.ndarray, v: np.ndarray, pts: np.ndarray,
                    geometry: PanelGeometry) -> tuple[np.ndarray, np.ndarray]:
    """Project flat panel coordinates to the curved mockup image plane."""
    tl, tr, br, bl = pts
    top_offset = (np.asarray(geometry.top_mid, dtype=np.float32) - (tl + tr) / 2
                  if geometry.top_mid is not None else np.zeros(2, np.float32))
    bottom_offset = (np.asarray(geometry.bottom_mid, dtype=np.float32) - (bl + br) / 2
                     if geometry.bottom_mid is not None else np.zeros(2, np.float32))
    u, v = np.asarray(u, dtype=np.float32), np.asarray(v, dtype=np.float32)
    arch = 4 * u * (1 - u)
    top = tl + u[..., None] * (tr - tl) + arch[..., None] * top_offset
    bottom = bl + u[..., None] * (br - bl) + arch[..., None] * bottom_offset
    xy = top + v[..., None] * (bottom - top)
    return xy[..., 0], xy[..., 1]


# Jacobian for Newton inversion of the curved perspective mapping.
def surface_derivatives(u: np.ndarray, v: np.ndarray, pts: np.ndarray,
                        geometry: PanelGeometry) -> tuple[np.ndarray, np.ndarray]:
    """Calculate d(position)/du and d(position)/dv for curved panel mapping."""
    tl, tr, br, bl = pts
    top_offset = (np.asarray(geometry.top_mid, dtype=np.float32) - (tl + tr) / 2
                  if geometry.top_mid is not None else np.zeros(2, np.float32))
    bottom_offset = (np.asarray(geometry.bottom_mid, dtype=np.float32) - (bl + br) / 2
                     if geometry.bottom_mid is not None else np.zeros(2, np.float32))
    u, v = np.asarray(u, dtype=np.float32), np.asarray(v, dtype=np.float32)
    deriv_arch = 4 - 8 * u
    top = tl + u[..., None] * (tr - tl) + (4 * u * (1 - u))[..., None] * top_offset
    bottom = bl + u[..., None] * (br - bl) + (4 * u * (1 - u))[..., None] * bottom_offset
    dtop = tr - tl + deriv_arch[..., None] * top_offset
    dbottom = br - bl + deriv_arch[..., None] * bottom_offset
    return dtop + v[..., None] * (dbottom - dtop), bottom - top


# Flat artwork composer that covers source holes without content distortion.
class FaceComposer:
    """Apply artwork to an opaque print face before drawing thirteen slots."""
    def __init__(self, policy: Settings = CONFIG):
        """Construct painter with a deterministic slot layout policy."""
        self.policy = policy
        self.slots = SlotLayout(policy)

    def draw(self, artwork: np.ndarray, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Create normalized BGR face and independently inspectable slot mask."""
        edges = np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1)
        width = (edges[0] + edges[2]) / 2
        height = (edges[1] + edges[3]) / 2
        if min(width, height) <= 0:
            raise RenderRejected("Non-positive physical panel dimensions")
        multiplier = max(1.0, self.policy.min_front_dimension / min(width, height))
        if max(width, height) * multiplier > self.policy.max_front_dimension:
            raise RenderRejected("Extremely narrow panel requires manual geometry review")
        fw = round(width * multiplier)
        fh = round(height * multiplier)
        if fw * fh > self.policy.max_image_pixels:
            raise RenderRejected("Face canvas exceeds memory safety threshold")
        art_h, art_w = artwork.shape[:2]
        actual_aspect = art_w / art_h
        panel_aspect = fw / fh
        ratio = max(actual_aspect / panel_aspect, panel_aspect / actual_aspect)
        if ratio > self.policy.max_artwork_aspect_mismatch:
            raise RenderRejected("Artwork aspect is too different; review required")
        fit = min(fw / art_w, fh / art_h)
        nw = min(fw, max(1, round(art_w * fit)))
        nh = min(fh, max(1, round(art_h * fit)))
        resized = cv2.resize(artwork, (nw, nh), interpolation=cv2.INTER_AREA if fit < 1 else cv2.INTER_CUBIC)
        # The blurred field fills only unused face regions: main artwork is never stretched.
        field = cv2.resize(artwork, (fw, fh), interpolation=cv2.INTER_LINEAR)
        radius = max(5, (round(min(fw, fh) * self.policy.panel_blurred_fill_fraction) | 1))
        field = cv2.GaussianBlur(field, (radius, radius), 0)
        left, top = (fw - nw) // 2, (fh - nh) // 2
        field[top:top + nh, left:left + nw] = resized
        aperture = self.slots.coverage(fw, fh)
        body = field.astype(np.float32)
        alpha = aperture[..., None]
        recess = np.empty_like(body)
        for channel, intensity in enumerate(self.policy.slot_interior_bgr):
            recess[..., channel] = intensity
        body = body * (1 - alpha) + recess * alpha
        # Opposed bevel gradients suggest shallow routed slots rather than drawn lines.
        glow = cv2.GaussianBlur(aperture, (0, 0), self.policy.slot_blur_sigma * 3)
        left_shift = np.pad(glow[:, :-1], ((0, 0), (1, 0)), mode="edge")
        right_shift = np.pad(glow[:, 1:], ((0, 0), (0, 1)), mode="edge")
        body += (left_shift - right_shift)[..., None] * self.policy.slot_edge_highlight
        return np.clip(body, 0, 255).astype(np.uint8), aperture


# CPU compositor that supports planar homography and reviewed curved boundaries.
class SurfaceProjector:
    """Perspective-render a fully painted front while preserving the outside scene."""
    def __init__(self, policy: Settings = CONFIG):
        """Capture anti-aliasing and tiled inverse-remap settings."""
        self.policy = policy

    def render(self, scene: np.ndarray, face: np.ndarray, pts: np.ndarray,
               geometry: PanelGeometry) -> np.ndarray:
        """Return a new composite without modifying the input image in place."""
        if geometry.top_mid is None:
            return self._planar(scene, face, pts)
        return self._curved(scene, face, pts, geometry)

    def _planar(self, scene: np.ndarray, face: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Map an opaque front and antialias its quadrilateral perimeter."""
        height, width = scene.shape[:2]
        fh, fw = face.shape[:2]
        source = np.array([[0, 0], [fw - 1, 0], [fw - 1, fh - 1], [0, fh - 1]], np.float32)
        homography = cv2.getPerspectiveTransform(source, pts)
        warped = cv2.warpPerspective(face, homography, (width, height), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REPLICATE)
        mask = cv2.warpPerspective(np.ones((fh, fw), np.float32), homography,
                                   (width, height), flags=cv2.INTER_LINEAR)
        mask = np.clip(mask, 0, 1)
        alpha = mask[..., None]
        return np.clip(scene.astype(np.float32) * (1 - alpha) + warped.astype(np.float32) * alpha,
                       0, 255).astype(np.uint8)

    def _curved(self, scene: np.ndarray, face: np.ndarray, pts: np.ndarray,
                geometry: PanelGeometry) -> np.ndarray:
        """Inverse-map a reviewed curved panel in small scanline tiles."""
        height, width = scene.shape[:2]
        fh, fw = face.shape[:2]
        grid_u, grid_v = np.meshgrid(np.linspace(0, 1, self.policy.curve_grid_columns, dtype=np.float32),
                                      np.linspace(0, 1, self.policy.curve_grid_rows, dtype=np.float32))
        sample_x, sample_y = surface_forward(grid_u, grid_v, pts, geometry)
        margin = self.policy.cv_border_margin
        xmin = max(0, int(math.floor(float(np.min(sample_x)) - margin)))
        xmax = min(width, int(math.ceil(float(np.max(sample_x)) + margin)))
        ymin = max(0, int(math.floor(float(np.min(sample_y)) - margin)))
        ymax = min(height, int(math.ceil(float(np.max(sample_y)) + margin)))
        if xmin >= xmax or ymin >= ymax:
            raise RenderRejected("Empty projected curve")
        result = scene.copy()
        # A sampled polygon defines the expected inner surface. A failed
        # Newton solve may not silently leave original source slits visible.
        side = np.linspace(0.0, 1.0, self.policy.curve_boundary_samples, dtype=np.float32)
        boundary_u = np.concatenate((side, np.ones_like(side), side[::-1], np.zeros_like(side)))
        boundary_v = np.concatenate((np.zeros_like(side), side, np.ones_like(side), side[::-1]))
        border_x, border_y = surface_forward(boundary_u, boundary_v, pts, geometry)
        outline = np.rint(np.stack((border_x, border_y), axis=1)).astype(np.int32)
        expected = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(expected, [outline], 255)
        core = cv2.erode(expected, np.ones((self.policy.curve_inner_guard_kernel, self.policy.curve_inner_guard_kernel), dtype=np.uint8))
        outside = core.copy()
        outside[ymin:ymax, xmin:xmax] = 0
        if np.any(outside):
            raise RenderRejected("Curved panel escapes calculated render bounds")
        unit_quad = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32)
        inv_homography = cv2.getPerspectiveTransform(pts, unit_quad)
        for y0 in range(ymin, ymax, self.policy.tile_height):
            y1 = min(ymax, y0 + self.policy.tile_height)
            yy, xx = np.mgrid[y0:y1, xmin:xmax].astype(np.float32)
            pix = np.stack((xx, yy), axis=-1)
            guess = cv2.perspectiveTransform(pix.reshape(1, -1, 2), inv_homography).reshape(pix.shape)
            u = guess[..., 0].copy()
            v = guess[..., 1].copy()
            for _ in range(self.policy.inverse_iterations):
                px, py = surface_forward(u, v, pts, geometry)
                du, dv = surface_derivatives(u, v, pts, geometry)
                ex, ey = px - xx, py - yy
                jac = du[..., 0] * dv[..., 1] - du[..., 1] * dv[..., 0]
                safe_jac = np.where(np.abs(jac) > self.policy.inverse_zero_epsilon, jac, np.inf)
                step_u = (ex * dv[..., 1] - ey * dv[..., 0]) / safe_jac
                step_v = (du[..., 0] * ey - du[..., 1] * ex) / safe_jac
                u -= np.clip(step_u, -self.policy.inverse_max_fraction_step,
                             self.policy.inverse_max_fraction_step)
                v -= np.clip(step_v, -self.policy.inverse_max_fraction_step,
                             self.policy.inverse_max_fraction_step)
            px, py = surface_forward(u, v, pts, geometry)
            residual = np.hypot(px - xx, py - yy)
            inside = ((u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
                      & (residual < self.policy.inverse_tolerance_pixels))
            if np.any((core[y0:y1, xmin:xmax] > 0) & ~inside):
                raise RenderRejected("Curved inverse warp left uncovered panel pixels")
            # Feather within the panel only: the surrounding scene is unchanged.
            border_dist = np.minimum.reduce((u * fw, (1 - u) * fw, v * fh, (1 - v) * fh))
            alpha = (np.clip(border_dist / self.policy.edge_feather_pixels, 0, 1)
                     * inside.astype(np.float32))
            mapx = (u * (fw - 1)).astype(np.float32)
            mapy = (v * (fh - 1)).astype(np.float32)
            projected = cv2.remap(face, mapx, mapy, cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_REPLICATE)
            local = result[y0:y1, xmin:xmax].astype(np.float32)
            a = alpha[..., None]
            result[y0:y1, xmin:xmax] = np.clip(local * (1 - a) + projected.astype(np.float32) * a,
                                                0, 255).astype(np.uint8)
        return result


# Non-distorting 3:4 scene formatter that rescales reviewed geometry identically.
def format_scene(scene: np.ndarray, geometry: PanelGeometry,
                 policy: Settings = CONFIG) -> tuple[np.ndarray, PanelGeometry]:
    """Produce a 1200x1600 marketplace canvas and adjusted geometrical points."""
    th, tw = policy.output_height, policy.output_width
    sh, sw = scene.shape[:2]
    scale = min(tw / sw, th / sh)
    rw, rh = max(1, round(sw * scale)), max(1, round(sh * scale))
    background = cv2.resize(scene, (tw, th), interpolation=cv2.INTER_LINEAR)
    background = cv2.GaussianBlur(background, (0, 0), sigmaX=max(tw, th) * policy.marketplace_blur_fraction)
    inserted = cv2.resize(scene, (rw, rh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    dx, dy = (tw - rw) // 2, (th - rh) // 2
    background[dy:dy + rh, dx:dx + rw] = inserted

    def adjust(point: tuple[float, float] | None) -> tuple[float, float] | None:
        """Rescale a single reviewed point onto the marketplace canvas."""
        return None if point is None else (float(point[0] * rw / sw + dx),
                                            float(point[1] * rh / sh + dy))
    converted = PanelGeometry(category=geometry.category,
                              quad=tuple(adjust(point) for point in geometry.quad),
                              reviewed=geometry.reviewed,
                              top_mid=adjust(geometry.top_mid),
                              bottom_mid=adjust(geometry.bottom_mid),
                              template_sha256=geometry.template_sha256)
    return background, converted


# High-level service responsible for hashing, local receipts, and fail-closed output.
class PetekService:
    """Orchestrate safe category routing and repeatable local image production."""
    def __init__(self, store: LocalStore, policy: Settings = CONFIG):
        """Inject local store and pure geometry/render dependencies."""
        self.policy = policy
        self.store = store
        self.guard = GeometryGuard(policy)
        self.composer = FaceComposer(policy)
        self.projector = SurfaceProjector(policy)
        self.log = logging.getLogger("petek")

    def render_arrays(self, artwork: np.ndarray, scene: np.ndarray,
                      geometry: PanelGeometry, template_hash: str) -> np.ndarray:
        """Validate original coordinates, scale scene, and compose a new output."""
        self.guard.validate(geometry, scene.shape, template_hash)
        if artwork is None or artwork.dtype != np.uint8 or artwork.ndim != 3 or artwork.shape[2] != 3:
            raise RenderRejected("Artwork must be an 8-bit BGR image")
        scene_ready, adjusted = format_scene(scene, geometry, self.policy)
        pts = self.guard.validate(adjusted, scene_ready.shape, template_hash)
        front, _ = self.composer.draw(artwork, pts)
        return self.projector.render(scene_ready, front, pts, adjusted)

    def render_file(self, artwork_path: Path, template_path: Path,
                    geometry_path: Path) -> tuple[Path, bool]:
        """Safely create or reuse an immutable deterministic PNG output receipt."""
        template_hash = file_sha256(template_path)
        artwork_hash = file_sha256(artwork_path)
        geometry_hash = file_sha256(geometry_path)
        geom = PanelGeometry.from_file(geometry_path)
        if geom.template_sha256 is None:
            raise RenderRejected("Real mockups require source-bound template_sha256 approval")
        scene = read_image(template_path, self.policy)
        self.guard.validate(geom, scene.shape, template_hash)
        key_record = {"template": template_hash, "art": artwork_hash,
                      "geometry": asdict(geom), "config": asdict(self.policy)}
        key = sha256(json.dumps(key_record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        target = self.store.output / f"PETEK_{key[:self.policy.output_key_length]}.png"
        if self.store.previously_rendered(key, target):
            self.log.info("REUSED %s", target)
            return target, True
        artwork = read_image(artwork_path, self.policy)
        result = self.render_arrays(artwork, scene, geom, template_hash)
        if (file_sha256(template_path) != template_hash
                or file_sha256(artwork_path) != artwork_hash
                or file_sha256(geometry_path) != geometry_hash):
            raise RenderRejected("An input or its reviewed geometry changed during render")
        if target.is_symlink():
            raise RenderRejected("Refusing symlink output path")
        if target.exists():
            # Exact-byte orphan adoption safely recovers power loss between
            # image creation and SQLite receipt commit without ever replacing it.
            okay, png = cv2.imencode(".png", result)
            if not okay or file_sha256(target) != sha256(png.tobytes()).hexdigest():
                raise RenderRejected("Unregistered output does not match this render; no overwrite")
            self.store.register(key, target)
            self.log.info("RECOVERED_IDENTICAL_ORPHAN %s", target)
            return target, True
        try:
            save_new_image(target, result)
        except RenderRejected:
            # A concurrent same-key process may have completed first. Reuse
            # only the already-registered and digest-verified result.
            if self.store.previously_rendered(key, target):
                return target, True
            raise
        self.store.register(key, target)
        self.log.info("CREATED %s output_sha256=%s", target, file_sha256(target))
        return target, False


# Scandir-based lazy walk that does not retain all images in RAM.
def images_in_folder(root: Path, policy: Settings = CONFIG) -> Iterator[Path]:
    """Yield valid regular image files recursively in deterministic path order."""
    if not root.is_dir() or root.is_symlink():
        raise RenderRejected("Invalid source design directory")
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda item: item.name.casefold())
            protected = (Path(__file__).resolve().parent / policy.state_folder).resolve()
            for entry in entries:
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    if path.resolve() != protected:
                        stack.append(path)
                elif entry.is_file(follow_symlinks=False) and path.suffix.lower() in policy.image_extensions:
                    yield path
        except OSError as exc:
            raise RenderRejected(f"Cannot scan directory: {exc}") from exc


# Synthetic demonstration fixtures built locally, independent of user's originals.
def create_demo_files(store: LocalStore, policy: Settings = CONFIG) -> tuple[Path, Path, Path]:
    """Construct synthetic cabinet and illustration inputs without overwriting."""
    fixture_dir = store.root / "demo_inputs"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    h, w = policy.sample_scene_height, policy.sample_scene_width
    scene = np.full((h, w, 3), (185, 193, 201), dtype=np.uint8)
    for row in range(h):
        scene[row] = (np.array([176, 184, 194]) * (1 - row / (h * 2))).astype(np.uint8)
    cv2.rectangle(scene, (110, 180), (800, 960), (235, 231, 226), -1)
    cv2.rectangle(scene, (110, 180), (800, 960), (151, 149, 143), 13)
    cv2.rectangle(scene, (96, 172), (815, 205), (205, 206, 209), -1)
    for slot_x in range(205, 730, max(1, 510 // policy.demo_old_slot_count)):
        cv2.line(scene, (slot_x, 330), (slot_x, 790), (41, 43, 46), 11, cv2.LINE_AA)
    sh, sw = policy.sample_art_height, policy.sample_art_width
    yy, xx = np.mgrid[0:sh, 0:sw]
    art = np.stack((110 + 42 * np.sin(xx / 65),
                    168 + 35 * np.cos(yy / 90),
                    214 + 35 * np.sin((xx + yy) / 110)), axis=-1)
    art = np.clip(art, 0, 255).astype(np.uint8)
    cv2.circle(art, (sw // 2, sh // 2), sh // 4, (68, 130, 208), 12, cv2.LINE_AA)
    cv2.putText(art, "PETEK 13", (sw // 5, sh // 2), cv2.FONT_HERSHEY_SIMPLEX,
                2.1, (45, 56, 68), 6, cv2.LINE_AA)
    template = fixture_dir / "sample_cabinet_v3.png"
    artwork = fixture_dir / "sample_art_v3.png"
    geom_path = fixture_dir / "sample_geometry_v3.json"
    for path, image in ((template, scene), (artwork, art)):
        if not path.exists():
            save_new_image(path, image)
    geom_doc = {"category": policy.category,
                "quad": [[135, 228], [767, 225], [768, 905], [130, 913]],
                "reviewed": True, "top_mid": [452, 240], "bottom_mid": [450, 934],
                "template_sha256": file_sha256(template)}
    if not geom_path.exists():
        with geom_path.open("x", encoding="utf-8") as stream:
            json.dump(geom_doc, stream, indent=2)
    return artwork, template, geom_path


# Console and rotating log configuration with local-only log-file side effects.
def configure_logging(folder: Path, policy: Settings = CONFIG) -> None:
    """Set up terminal and durable app.log error/success reporting."""
    log = logging.getLogger("petek")
    log.setLevel(logging.INFO)
    log.propagate = False
    if log.handlers:
        return
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler = RotatingFileHandler(folder / "app.log", maxBytes=policy.log_max_bytes,
                                  backupCount=policy.log_backups, encoding="utf-8")
    handler.setFormatter(formatter)
    terminal = logging.StreamHandler(sys.stderr)
    terminal.setFormatter(formatter)
    log.addHandler(handler)
    log.addHandler(terminal)


# CLI parser defining executable demo, test, status, render and streaming batch commands.
def build_parser() -> argparse.ArgumentParser:
    """Construct a validated cross-platform command line interface."""
    parser = argparse.ArgumentParser(description="Isolated PETEK DOLABI 13-slot renderer")
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("demo", help="Generate a synthetic mockup test image")
    actions.add_parser("test", help="Run built-in unittest checks")
    actions.add_parser("status", help="Show completed local jobs")
    inspector = actions.add_parser("inspect", help="Print template dimensions and SHA-256")
    inspector.add_argument("--file", type=Path, required=True, help="Image to inspect without changing")
    render = actions.add_parser("render", help="Render one design with approved geometry")
    batch = actions.add_parser("batch", help="Stream a directory of designs")
    for cmd in (render, batch):
        cmd.add_argument("--template", required=True, type=Path, help="Read-only cabinet mockup")
        cmd.add_argument("--geometry", required=True, type=Path, help="Reviewed JSON geometry")
    render.add_argument("--art", required=True, type=Path, help="Read-only artwork")
    batch.add_argument("--art-dir", required=True, type=Path, help="Directory to scan recursively")
    return parser


# Application entrypoint catches validation, IO, OpenCV and database exceptions.
def main(argv: list[str] | None = None) -> int:
    """Run an action and return a stable success/failure exit status."""
    try:
        args = build_parser().parse_args(argv)
        local = Path(__file__).resolve().parent / CONFIG.state_folder
        if local.is_symlink():
            raise RenderRejected("Application local state cannot be a symlink")
        local.mkdir(parents=True, exist_ok=True)
        configure_logging(local)
        if args.action == "test":
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(PetekTests)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            return 0 if result.wasSuccessful() else 1
        store = LocalStore(local)
        service = PetekService(store)
        if args.action == "status":
            print(f"Isolated receipts: {store.stats()} | {store.database}")
            return 0
        if args.action == "inspect":
            image = read_image(args.file)
            print(json.dumps({"file": str(args.file), "width": image.shape[1],
                              "height": image.shape[0], "sha256": file_sha256(args.file)},
                             ensure_ascii=False, indent=2))
            return 0
        if args.action == "demo":
            paths = create_demo_files(store)
            target, reused = service.render_file(*paths)
            print(f"{'REUSED' if reused else 'CREATED'}: {target}")
            return 0
        if args.action == "render":
            target, reused = service.render_file(args.art, args.template, args.geometry)
            print(f"{'REUSED' if reused else 'CREATED'}: {target}")
            return 0
        if args.action == "batch":
            good, failures = 0, 0
            for index, art in enumerate(images_in_folder(args.art_dir), start=1):
                if index > CONFIG.max_jobs_per_batch:
                    raise RenderRejected("Batch limit reached")
                try:
                    target, reused = service.render_file(art, args.template, args.geometry)
                    print(f"{'REUSED' if reused else 'CREATED'}: {art.name} => {target.name}")
                    good += 1
                except (RenderRejected, ValueError, OSError, cv2.error, sqlite3.Error) as exc:
                    logging.getLogger("petek").error("SKIPPED %s: %s", art.name, exc)
                    failures += 1
            print(f"Completed: {good} | Failed: {failures}")
            return 0 if good and not failures else 2
        raise RenderRejected("Unsupported action")
    except (RenderRejected, ValueError, OSError, sqlite3.Error, cv2.error) as exc:
        logging.getLogger("petek").exception("BLOCKED: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        logging.getLogger("petek").exception("UNEXPECTED FATAL ERROR: %s", exc)
        print(f"CRITICAL: {exc}", file=sys.stderr)
        return 3


# Built-in unittest suite checks symmetry, pixels, curvature, repeat safety and IO.
class PetekTests(unittest.TestCase):
    """Exercise major safety and rendering behavior on synthetic local arrays."""
    def setUp(self) -> None:
        """Create isolated in-memory scene, design, and approved coordinates."""
        self.scene = np.full((600, 820, 3), (175, 179, 184), np.uint8)
        self.art = np.full((310, 455, 3), (120, 180, 230), np.uint8)
        self.quad = ((140., 115.), (697., 112.), (703., 489.), (132., 494.))
        self.geometry = PanelGeometry(CONFIG.category, self.quad, True)
        self.digest = "0" * 64

    def test_thirteen_symmetric_slots(self) -> None:
        """There are exactly 13 symmetrically spaced apertures."""
        slots = SlotLayout().positions()
        self.assertEqual(len(slots), CONFIG.slot_count)
        xs = np.array([slot[0] for slot in slots])
        self.assertLess(np.ptp(np.diff(xs)), 1e-11)
        self.assertAlmostEqual(xs[0], 1 - xs[-1])

    def test_slot_mask_components(self) -> None:
        """Rasterized openings are 13 disconnected geometrical components."""
        covered = SlotLayout().coverage(800, 620)
        number, _ = cv2.connectedComponents((covered > CONFIG.mask_threshold).astype(np.uint8))
        self.assertEqual(number - 1, CONFIG.slot_count)

    def test_identity_and_review_guard(self) -> None:
        """Reject false category identity and unapproved surface geometry."""
        guard = GeometryGuard()
        with self.assertRaises(RenderRejected):
            guard.validate(PanelGeometry("03_Ahsap_Tablo", self.quad, True), self.scene.shape, self.digest)
        with self.assertRaises(RenderRejected):
            guard.validate(PanelGeometry(CONFIG.category, self.quad, False), self.scene.shape, self.digest)

    def test_perspective_corners(self) -> None:
        """OpenCV homography maps corners to their expected positions."""
        pts = GeometryGuard().validate(self.geometry, self.scene.shape, self.digest)
        src = np.array([[0, 0], [699, 0], [699, 499], [0, 499]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(src, pts)
        dst = cv2.perspectiveTransform(src.reshape(1, 4, 2), matrix).reshape(4, 2)
        self.assertTrue(np.allclose(pts, dst, atol=0.02))

    def test_source_immutability_and_old_hole_cover(self) -> None:
        """Past slit colors disappear from the opaque print face."""
        store = self._temp_store()
        try:
            service = PetekService(store)
            striped = self.scene.copy()
            for x in range(210, 640, 35):
                cv2.line(striped, (x, 180), (x, 430), (0, 0, 0), 6)
            before = sha256(striped.tobytes()).hexdigest()
            one = service.render_arrays(self.art, striped, self.geometry, self.digest)
            two = service.render_arrays(self.art, self.scene, self.geometry, self.digest)
            self.assertEqual(sha256(striped.tobytes()).hexdigest(), before)
            self.assertTrue(np.array_equal(one[700:705], two[700:705]))
            self.assertTrue(np.array_equal(one[710:840, 560:680], two[710:840, 560:680]))
        finally:
            store._test_temp.cleanup()

    def test_curved_bounds(self) -> None:
        """Curved top and bottom interpolation exactly meets midpoint anchors."""
        curved = PanelGeometry(CONFIG.category, self.quad, True,
                               top_mid=(419., 132.), bottom_mid=(419., 515.))
        pts = GeometryGuard().validate(curved, self.scene.shape, self.digest)
        for v, expected in ((0., curved.top_mid), (1., curved.bottom_mid)):
            x, y = surface_forward(np.array(.5), np.array(v), pts, curved)
            self.assertTrue(np.allclose([x, y], expected, atol=.001))

    def test_curvature_guard(self) -> None:
        """Impossible curved geometry is rejected instead of image corruption."""
        curve = PanelGeometry(CONFIG.category, self.quad, True,
                              top_mid=(420., 25.), bottom_mid=(420., 900.))
        with self.assertRaises(RenderRejected):
            GeometryGuard().validate(curve, self.scene.shape, self.digest)

    def test_deterministic_output(self) -> None:
        """Same inputs always produce exactly the same pixel buffer."""
        store = self._temp_store()
        try:
            renderer = PetekService(store)
            first = renderer.render_arrays(self.art, self.scene, self.geometry, self.digest)
            second = renderer.render_arrays(self.art, self.scene, self.geometry, self.digest)
            self.assertTrue(np.array_equal(first, second))
            self.assertEqual(first.shape[:2], (CONFIG.output_height, CONFIG.output_width))
        finally:
            store._test_temp.cleanup()

    def test_curved_output(self) -> None:
        """A reviewed curved panel is rendered at marketplace dimensions."""
        store = self._temp_store()
        try:
            curved = PanelGeometry(CONFIG.category, self.quad, True,
                                   top_mid=(419., 130.), bottom_mid=(418., 505.))
            result = PetekService(store).render_arrays(self.art, self.scene, curved, self.digest)
            self.assertEqual(result.shape, (CONFIG.output_height, CONFIG.output_width, 3))
        finally:
            store._test_temp.cleanup()

    def test_no_overwrite_and_idempotency(self) -> None:
        """A matching repeated job reuses its verified output without rewriting."""
        store = self._temp_store()
        try:
            fixture = store.root
            scene_file = fixture / "scene.png"
            art_file = fixture / "art.png"
            geom_file = fixture / "geom.json"
            save_new_image(scene_file, self.scene)
            save_new_image(art_file, self.art)
            geom = {"category": CONFIG.category, "quad": [list(p) for p in self.quad],
                    "reviewed": True, "template_sha256": file_sha256(scene_file)}
            geom_file.write_text(json.dumps(geom), encoding="utf-8")
            service = PetekService(store)
            first, reused = service.render_file(art_file, scene_file, geom_file)
            self.assertFalse(reused)
            before = first.stat().st_mtime_ns
            again, reused = service.render_file(art_file, scene_file, geom_file)
            self.assertTrue(reused)
            self.assertEqual(first, again)
            self.assertEqual(before, first.stat().st_mtime_ns)
            self.assertEqual(store.stats(), 1)
            with self.assertRaises(RenderRejected):
                save_new_image(first, self.art)
        finally:
            store._test_temp.cleanup()

    def test_geometry_hash_mismatch(self) -> None:
        """A stale approved source checksum blocks the render."""
        other = PanelGeometry(CONFIG.category, self.quad, True,
                              template_sha256="1" * 64)
        with self.assertRaises(RenderRejected):
            GeometryGuard().validate(other, self.scene.shape, self.digest)

    def test_unbound_geometry_rejected_on_real_files(self) -> None:
        """Real renders require a SHA-bound reviewed template, not only a Boolean."""
        store = self._temp_store()
        try:
            scene_file, art_file, geom_file = (store.root / v for v in ("s.png", "a.png", "g.json"))
            save_new_image(scene_file, self.scene)
            save_new_image(art_file, self.art)
            geom_file.write_text(json.dumps({"category": CONFIG.category,
                "quad": [list(v) for v in self.quad], "reviewed": True}), encoding="utf-8")
            with self.assertRaisesRegex(RenderRejected, "template_sha256"):
                PetekService(store).render_file(art_file, scene_file, geom_file)
            self.assertFalse(list(store.output.glob("*.png")))
        finally:
            store._test_temp.cleanup()

    def test_orphan_receipt_recovery(self) -> None:
        """Recover an identical existing output after interrupted SQLite registration."""
        store = self._temp_store()
        try:
            src, art, geom = (store.root / v for v in ("scene.png", "art.png", "geometry.json"))
            save_new_image(src, self.scene)
            save_new_image(art, self.art)
            geom.write_text(json.dumps({"category": CONFIG.category,
                "quad": [list(v) for v in self.quad], "reviewed": True,
                "template_sha256": file_sha256(src)}), encoding="utf-8")
            service = PetekService(store)
            target, reused = service.render_file(art, src, geom)
            self.assertFalse(reused)
            original_hash, original_time = file_sha256(target), target.stat().st_mtime_ns
            with sqlite3.connect(store.database) as con:
                con.execute("DELETE FROM render_jobs")
            recovered, reused = service.render_file(art, src, geom)
            self.assertTrue(reused)
            self.assertEqual(recovered, target)
            self.assertEqual(file_sha256(target), original_hash)
            self.assertEqual(target.stat().st_mtime_ns, original_time)
            self.assertEqual(store.stats(), 1)
        finally:
            store._test_temp.cleanup()

    def test_tampered_orphan_never_overwritten(self) -> None:
        """Reject corrupted orphan file instead of replacing user-visible bytes."""
        store = self._temp_store()
        try:
            src, art, geom = (store.root / v for v in ("scene.png", "art.png", "geometry.json"))
            save_new_image(src, self.scene)
            save_new_image(art, self.art)
            geom.write_text(json.dumps({"category": CONFIG.category,
                "quad": [list(v) for v in self.quad], "reviewed": True,
                "template_sha256": file_sha256(src)}), encoding="utf-8")
            service = PetekService(store)
            target, _ = service.render_file(art, src, geom)
            with sqlite3.connect(store.database) as con:
                con.execute("DELETE FROM render_jobs")
            with target.open("ab") as file:
                file.write(b"not-original-output")
            corrupted_hash = file_sha256(target)
            with self.assertRaisesRegex(RenderRejected, "Unregistered output"):
                service.render_file(art, src, geom)
            self.assertEqual(corrupted_hash, file_sha256(target))
            self.assertEqual(store.stats(), 0)
        finally:
            store._test_temp.cleanup()

    def test_oversize_png_header_blocked(self) -> None:
        """Reject oversized image headers before OpenCV decompresses their pixels."""
        import struct
        import zlib
        store = self._temp_store()
        try:
            oversized = store.root / "unsafe.png"
            def chunk(kind: bytes, data: bytes) -> bytes:
                """Construct one checksummed PNG chunk for adversarial header test."""
                return (struct.pack(">I", len(data)) + kind + data
                        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
            ihdr = struct.pack(">IIBBBBB", 200_000, 200_000, 8, 2, 0, 0, 0)
            oversized.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                                  + chunk(b"IEND", b""))
            with self.assertRaises(RenderRejected):
                read_image(oversized)
        finally:
            store._test_temp.cleanup()

    def test_oversized_geometry_json_blocked(self) -> None:
        """Oversized control documents cannot cause unbounded JSON parsing."""
        store = self._temp_store()
        try:
            payload = store.root / "oversize.json"
            payload.write_bytes(b" " * (CONFIG.max_geometry_bytes + 1))
            with self.assertRaisesRegex(RenderRejected, "maximum supported size"):
                PanelGeometry.from_file(payload)
        finally:
            store._test_temp.cleanup()

    def test_geometry_sha_mismatch_stops_file_writes(self) -> None:
        """Approved-source hash mismatches are rejected without output creation."""
        store = self._temp_store()
        try:
            src, art, geom = (store.root / v for v in ("scene.png", "art.png", "geometry.json"))
            save_new_image(src, self.scene)
            save_new_image(art, self.art)
            geom.write_text(json.dumps({"category": CONFIG.category,
                "quad": [list(v) for v in self.quad], "reviewed": True,
                "template_sha256": "a" * 64}), encoding="utf-8")
            with self.assertRaisesRegex(RenderRejected, "Template hash"):
                PetekService(store).render_file(art, src, geom)
            self.assertEqual(list(store.output.glob("*.png")), [])
        finally:
            store._test_temp.cleanup()

    def test_rotated_quad_rejected(self) -> None:
        """Rotated corner labels cannot silently rotate or mirror printed art."""
        rotated = PanelGeometry(CONFIG.category,
                                (self.quad[3], self.quad[0], self.quad[1], self.quad[2]), True)
        with self.assertRaisesRegex(RenderRejected, "corner order"):
            GeometryGuard().validate(rotated, self.scene.shape, self.digest)

    def test_inspect_returns_readonly_metadata(self) -> None:
        """Inspect prints file dimensions and checksum with no source mutation."""
        store = self._temp_store()
        try:
            source = store.root / "source.png"
            save_new_image(source, self.scene)
            before = file_sha256(source)
            loaded = read_image(source)
            self.assertEqual(loaded.shape, self.scene.shape)
            self.assertEqual(file_sha256(source), before)
        finally:
            store._test_temp.cleanup()

    def _temp_store(self) -> LocalStore:
        """Create a self-cleaning mock database outside any production folders."""
        temp = tempfile.TemporaryDirectory(prefix="petek_unit_test_")
        store = LocalStore(Path(temp.name) / CONFIG.state_folder)
        store._test_temp = temp
        return store


if __name__ == "__main__":
    sys.exit(main())
