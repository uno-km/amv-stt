# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
AMEVA Unified Exception Hierarchy for Termux AI Engines.
Component: [STT]
"""
from typing import Optional, Any


class AmevaTermuxError(Exception):
    """Root exception for all Termux On-Device AI Engines."""
    COMPONENT_TAG = "[STT]"
    DEFAULT_CODE = "E000_UNKNOWN"

    def __init__(self, message: str, code: Optional[Any] = None, details: Optional[Any] = None):
        self.code = code or self.DEFAULT_CODE
        self.details = details
        self.raw_message = message
        super().__init__(message if message.startswith("[ERROR:") else f"{self.COMPONENT_TAG} [{self.code}] {message}")


TermuxSTTError = AmevaTermuxError


class ErrorCode:
    PLATFORM_NOT_SUPPORTED = 1
    MODEL_NOT_FOUND = 2
    AUDIO_PROCESSING_ERROR = 3
    INFERENCE_TIMEOUT = 4
    INVALID_ARGUMENT = 5
    RUNTIME_NOT_INSTALLED = 10
    VULKAN_DEVICE = 11
    CLUSTER_CONNECTION = 12
    CLUSTER_CONFIG = 13
    UNKNOWN_ERROR = 99


class ExitCode:
    SUCCESS = 0
    FAILURE = 1
    INVALID_USAGE = 2
    NOT_FOUND = 3
    TIMEOUT = 4


class PlatformNotSupportedError(AmevaTermuxError):
    DEFAULT_CODE = ErrorCode.PLATFORM_NOT_SUPPORTED

class RuntimeRequiredError(PlatformNotSupportedError):
    """A GPU request needs ameva-runtime (AMUDA), which is missing or too old.

    The message is the shared AMU_ERR_RUNTIME_REQUIRED explanation. The CLI exits with status 69;
    nothing is run and there is no CPU fallback.
    """

    DEFAULT_CODE = ErrorCode.RUNTIME_NOT_INSTALLED
    runtime_required = True


class ModelNotFoundError(AmevaTermuxError):
    DEFAULT_CODE = ErrorCode.MODEL_NOT_FOUND


class AudioProcessingError(AmevaTermuxError):
    DEFAULT_CODE = ErrorCode.AUDIO_PROCESSING_ERROR


class InferenceTimeoutError(AmevaTermuxError):
    DEFAULT_CODE = ErrorCode.INFERENCE_TIMEOUT


class HardwareCompatibilityError(AmevaTermuxError):
    DEFAULT_CODE = "E003_HARDWARE_INCOMPATIBLE"


class RuntimeNotFoundError(AmevaTermuxError):
    DEFAULT_CODE = "E004_RUNTIME_NOT_FOUND"


class ProvisioningError(AmevaTermuxError):
    DEFAULT_CODE = "E005_PROVISIONING_FAILED"


class InferenceExecutionError(AmevaTermuxError):
    DEFAULT_CODE = "E007_INFERENCE_FAILED"


class ModelCorruptedError(AmevaTermuxError):
    DEFAULT_CODE = "E008_MODEL_CORRUPTED"


class ModelDownloadError(ProvisioningError):
    DEFAULT_CODE = "E009_MODEL_DOWNLOAD_FAILED"


class ClusterConnectionError(TermuxSTTError):
    """Raised when one or more distributed RPC worker nodes cannot be reached or fail handshake."""
    DEFAULT_CODE = ErrorCode.CLUSTER_CONNECTION


class ClusterConfigurationError(TermuxSTTError):
    """Raised when cluster parameters (tensor split, backend, vram budget) are invalid."""
    DEFAULT_CODE = ErrorCode.CLUSTER_CONFIG


class ClusterLicenseRequiredError(TermuxSTTError):
    """Raised when distributed clustering is invoked without required AMEVA Cluster license."""
    DEFAULT_CODE = "E403_CLUSTER_LICENSE_REQUIRED"

    def __init__(self, message: str = ""):
        if not message:
            message = (
                "\n================================================================================\n"
                "[AMEVA-CLUSTER] CLUSTER LICENSE REQUIRED (E403)\n"
                "================================================================================\n"
                "Multi-device distributed clustering is an exclusive capability of 'ameva-cluster'.\n"
                "Standalone distributed execution without the official AMEVA-Cluster package is prohibited.\n\n"
                "Resolution:\n"
                "  1. Install official AMEVA-Cluster runtime:\n"
                "     pip install ameva-cluster  (or npm install @ameva/cluster)\n"
                "  2. Launch worker/master through 'ameva-cluster' control plane:\n"
                "     ameva-cluster worker\n"
                "     ameva-cluster master -m model.gguf\n"
                "================================================================================"
            )
        super().__init__(message)
