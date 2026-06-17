from __future__ import annotations

import sys
import warnings


if any("pytest" in str(arg).lower() for arg in sys.argv):
    warnings.filterwarnings("ignore")

warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+",
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyPacked has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type SwigPyObject has no __module__ attribute",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"builtin type swigvarlink has no __module__ attribute",
    category=DeprecationWarning,
)
