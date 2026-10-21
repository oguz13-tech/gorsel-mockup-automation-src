# -*- coding: utf-8 -*-
"""Strict opaque PETEK V3 adapter for the existing six-category factory.

The legacy process_mockup can route only PETEK here. Other categories remain
unchanged. No cloud API or user asset mutation is performed by this adapter.
"""
from __future__ import annotations

import logging
from pathlib import Path
import numpy as np

from .petek_mask_store import PetekProfileStore, safe_uid
from .petek_surface_v3 import CATEGORY, RECIPE, PetekSafetyError, sha256_file

LOGGER = logging.getLogger("petek.factory")


def approved_receipt(runtime_root: Path, template_path: Path,
                     config: dict) -> dict:
    """Resolve an immutable mask receipt for factory artifact-key versioning."""
    root = Path(runtime_root).resolve()
    target = root / "2_SABLON_HAVUZU"
    store = PetekProfileStore(root, target)
    template_path = Path(template_path)
    if template_path.parent.name != CATEGORY:
        raise PetekSafetyError("PETEK_CATEGORY_ROUTE_MISMATCH")
    uid = safe_uid(str(config.get("petek_mask_uid") or template_path.stem))
    profile, mask = store.find(uid, template_path, approved_only=True)
    legacy_quad = config.get("koseler")
    if not isinstance(legacy_quad, (tuple,list)) or len(legacy_quad) != 4:
        raise PetekSafetyError("LEGACY_APPROVED_QUAD_REQUIRED")
    if not np.allclose(np.asarray(legacy_quad,dtype=float),
                       np.asarray(profile["front_quad"],dtype=float),
                       atol=1.5,rtol=0):
        raise PetekSafetyError("MASK_QUAD_DIFFERS_FROM_GEOMETRY_APPROVAL")
    expected_hash = str(config.get("source_asset_sha256") or "")
    if expected_hash and expected_hash != profile["source_sha256"]:
        raise PetekSafetyError("PROFILE_SOURCE_SHA_MISMATCH")
    return {"uid":uid, "mask_sha256":profile["mask_sha256"],
            "source_sha256":profile["source_sha256"],
            "recipe":RECIPE, "profile":profile, "mask":mask, "store":store}


def render_from_legacy_factory(raw_path: Path, template_path: Path,
                               config: dict, output_path: Path,
                               runtime_root: Path, template_sha: str | None = None) -> bool:
    """Render PETEK only from two independently approved profiles."""
    try:
        receipt = approved_receipt(runtime_root, template_path, config)
        if template_sha and template_sha != receipt["source_sha256"]:
            raise PetekSafetyError("FACTORY_TEMPLATE_HASH_MISMATCH")
        # Existing factory filenames end with .jpg; renderer encodes JPEG
        # rather than mislabeling PNG as JPEG.
        result = receipt["store"].render(receipt["uid"],template_path,
                                          raw_path,output_path,marketplace=bool(
                                              config.get("marketplace_ready",True)))
        LOGGER.info("PETEK V3 isolated render success %s",result["artifact_key"])
        return True
    except (PetekSafetyError,ValueError,OSError) as exc:
        LOGGER.error("PETEK V3 fail-closed: %s",exc)
        return False
    except Exception:
        LOGGER.exception("Unexpected PETEK V3 rendering error")
        return False
