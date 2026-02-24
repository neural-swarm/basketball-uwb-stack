"""Basketball UWB/LPS tracking MVP tutorial scaffold.

The package provides a runnable end-to-end demo pipeline that simulates UWB/LPS and IMU
streams, performs basic time alignment and sensor fusion, and computes streaming analytics.
"""

from .config import DemoConfig
from .pipeline import TrackingEngine

__all__ = ["DemoConfig", "TrackingEngine"]
