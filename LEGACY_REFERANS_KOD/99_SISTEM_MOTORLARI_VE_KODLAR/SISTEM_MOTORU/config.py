"""
==============================================================================
E-COMMERCE VISUAL DESIGN & PRODUCTION FACTORY (ETSY / AMAZON / TRENDYOL)
Configuration Module
==============================================================================
"""

import os
from dataclasses import dataclass
from typing import Dict, Tuple

# Base Directories
BASE_DIR = os.getcwd()
OUTPUT_DIR = os.path.join(BASE_DIR, "factory_outputs")
DATABASE_PATH = os.path.join(BASE_DIR, "production_state.db")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==============================================================================
# ENGINE SELECTION
# FLUX_SCHNELL is the primary, production-grade 12B DiT engine.
# ==============================================================================
ACTIVE_ENGINE = "FLUX_SCHNELL"

# ==============================================================================
# OMNI-CHANNEL 5X MULTI-PRODUCT EXPORT SETTINGS
# 1 Master Generation -> 5 E-Commerce Products (Zero Wasted Compute)
# ==============================================================================
MULTI_PRODUCT_MODE = True

PRODUCT_CATEGORIES: Dict[str, Dict] = {
    "01_cam_dograma_tahtasi": {
        "name": "Cam Doğrama Tahtası",
        "width": 1216,
        "height": 912,
        "orientation": "horizontal",
        "is_glass": True,
        "folder": "01_cam_dograma_tahtasi"
    },
    "02_ocak_arkasi_cam": {
        "name": "Ocak Arkası Cam Tablo",
        "width": 1216,
        "height": 912,
        "orientation": "horizontal",
        "is_glass": True,
        "folder": "02_ocak_arkasi_cam"
    },
    "03_wifi_kutusu_kapagi": {
        "name": "Wifi Gizleme Kutusu Kapağı",
        "width": 1216,
        "height": 912,
        "orientation": "horizontal",
        "is_glass": False,
        "folder": "03_wifi_kutusu_kapagi"
    },
    "04_cam_tablo": {
        "name": "Lüks Cam Tablo",
        "width": 1091,
        "height": 1715,
        "orientation": "vertical",
        "is_glass": True,
        "folder": "04_cam_tablo"
    },
    "05_ahsap_tablo": {
        "name": "Doğal Ahşap Tablo",
        "width": 1091,
        "height": 1715,
        "orientation": "vertical",
        "is_glass": False,
        "folder": "05_ahsap_tablo"
    }
}

# Reference-guided Generation (Img2Img) parameters
REFERENCE_DIR = os.path.join(BASE_DIR, "references") if os.path.exists(os.path.join(BASE_DIR, "references")) else os.path.join(BASE_DIR, "reference_library")
DEFAULT_DENOISING_STRENGTH = 0.60  # 0.50-0.65 optimal balance
os.makedirs(REFERENCE_DIR, exist_ok=True)

# ==============================================================================
# RESOLUTION CONFIGURATIONS FOR PRINT PRODUCTS
# Diffusion models require dimensions divisible by 16 (or 64).
# We generate at the closest native multiple, then resize to exact target.
# ==============================================================================
@dataclass
class ProductSpec:
    name: str
    target_width: int
    target_height: int
    orientation: str  # 'horizontal' or 'vertical'
    native_gen_width: int
    native_gen_height: int
    surface_prompt_modifier: str

PRODUCT_SPECS: Dict[str, ProductSpec] = {
    # 1. Cam Doğrama Tahtası (Horizontal: 1216x912)
    "cam_dograma_tahtasi": ProductSpec(
        name="Cam Doğrama Tahtası",
        target_width=1216,
        target_height=912,
        orientation="horizontal",
        native_gen_width=1216,
        native_gen_height=912,
        surface_prompt_modifier=(
            "designed for ultra-hygienic tempered glass cutting board, crystal clear glass vibrancy, "
            "edge-to-edge seamless culinary graphic, vivid rich ink saturation, commercial flatbed UV print ready"
        )
    ),
    
    # 2. Ocak Arkası Cam Tablo (Horizontal: 1216x912)
    "ocak_arkasi_cam": ProductSpec(
        name="Ocak Arkası Cam Tablo",
        target_width=1216,
        target_height=912,
        orientation="horizontal",
        native_gen_width=1216,
        native_gen_height=912,
        surface_prompt_modifier=(
            "panoramic stove backsplash glass panel, heat-resistant glossy acrylic aesthetics, "
            "ultra-deep gloss finish, high contrast, non-repeating luxury kitchen backdrop, UV print ready"
        )
    ),
    
    # 3. Wifi Gizleme Kutusu Kapağı (Horizontal: 1216x912)
    "wifi_gizleme_kutusu": ProductSpec(
        name="Wifi Gizleme Kutusu Kapağı",
        target_width=1216,
        target_height=912,
        orientation="horizontal",
        native_gen_width=1216,
        native_gen_height=912,
        surface_prompt_modifier=(
            "scandinavian wall cabinet front panel design, warm soothing interior tones, "
            "minimalist decorative wall accent, clean border-safe layout, flat woodgrain UV print aesthetic"
        )
    ),
    
    # 4. Cam Tablo (Vertical: 1091x1715)
    "cam_tablo": ProductSpec(
        name="Lüks Cam Tablo",
        target_width=1091,
        target_height=1715,
        orientation="vertical",
        native_gen_width=1088,
        native_gen_height=1712,  # Multiples of 16 closest to 1091x1715
        surface_prompt_modifier=(
            "premium luxury glass wall art, ultra-high dynamic range, 4mm tempered glass reverse-side UV print, "
            "deep optical obsidian blacks, glowing 24k metallic gold inlays, crystal glossy specular reflections"
        )
    ),
    
    # 5. Ahşap Tablo (Vertical: 1091x1715)
    "ahsap_tablo": ProductSpec(
        name="Doğal Ahşap Tablo",
        target_width=1091,
        target_height=1715,
        orientation="vertical",
        native_gen_width=1088,
        native_gen_height=1712,
        surface_prompt_modifier=(
            "handcrafted natural wooden wall art plaque, organic wood grain undertones, matte UV ink finish, "
            "flawless serif typography and calligraphy, clean minimalist artisan poster print"
        )
    )
}

# ==============================================================================
# QUALITY CONTROL CRITERIA
# ==============================================================================
MIN_LAPLACIAN_VARIANCE = 95.0   # Reject blurry / low sharpness renders
MIN_SHANNON_ENTROPY = 4.8       # Reject blank or washed out single-color backgrounds
MAX_SHANNON_ENTROPY = 7.95      # Reject noisy salt-and-pepper artifacts
MAX_DHASH_HAMMING_DISTANCE = 4  # Flag identical/duplicate images (dhash collision threshold)
