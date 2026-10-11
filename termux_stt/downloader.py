# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
AMEVA Unified Model Downloader for termux-stt.
"""
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from .models.hub import ModelHub
from .hardware import get_unified_model_search_dirs

AVAILABLE_MODELS = {
    "tiny": {"name": "ggml-tiny.bin", "size_mb": 75, "desc": "Whisper Tiny (Fastest)"},
    "base": {"name": "ggml-base.bin", "size_mb": 142, "desc": "Whisper Base (Recommended Default)"},
    "small": {"name": "ggml-small.bin", "size_mb": 466, "desc": "Whisper Small (High Precision)"},
}

def resolve_model_path(model_name: str = "base") -> Path:
    search_dirs = get_unified_model_search_dirs("stt")
    clean = model_name.lower().replace("whisper-", "").replace("ggml-", "").replace(".bin", "")
    fname = AVAILABLE_MODELS.get(clean, {}).get("name", f"ggml-{clean}.bin")
    
    for d in search_dirs:
        cand = d / fname
        if cand.is_file():
            return cand.resolve()
        
    hub = ModelHub()
    return Path(hub.get_model_path(clean))

def download_model(model_name: str = "base", output_dir: Optional[Path] = None, force: bool = False) -> Path:
    hub = ModelHub(cache_dir=output_dir)
    clean = model_name.lower().replace("whisper-", "").replace("ggml-", "").replace(".bin", "")
    return Path(hub.download_model(clean, force=force))

def list_models() -> List[Dict[str, Any]]:
    return [{"id": k, **v} for k, v in AVAILABLE_MODELS.items()]

def verify_file_sha256(file_path: Union[str, Path], expected_sha256: str) -> bool:
    """Standard Unified SHA-256 Checksum Verifier for termux-stt."""
    return ModelHub.verify_integrity(str(file_path), expected_sha256)

