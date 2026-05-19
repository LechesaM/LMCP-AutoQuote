from __future__ import annotations

import warnings


warnings.filterwarnings(
    "ignore",
    message=r"PyPDF2 is deprecated\. Please move to the pypdf library instead\.",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+",
    category=Warning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type swigvarlink has no __module__ attribute",
    category=DeprecationWarning,
)
