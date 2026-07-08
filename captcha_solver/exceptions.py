"""Custom exception types for the captcha solver."""


class CaptchaNotFoundError(Exception):
    """Raised when no captcha element can be found on the page."""


class VisionAPIError(Exception):
    """Raised when the vision API call fails (auth, timeout, bad response)."""


class ContourDetectionError(Exception):
    """Raised when OpenCV contour detection yields insufficient candidates."""


class CoordinateMappingError(Exception):
    """Raised when coordinate mapping between pixel spaces is invalid."""
