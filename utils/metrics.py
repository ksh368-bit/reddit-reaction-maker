"""Metrics collection and export for observability."""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collect and export pipeline metrics for observability and SLA monitoring."""

    def __init__(self, enabled: bool = True):
        """
        Initialize metrics collector.

        Args:
            enabled: Whether to collect metrics (default: True)
        """
        self.enabled = enabled
        self.metrics = {
            "timestamp": datetime.now().isoformat(),
            "start_time": time.time(),
            "tts_duration_sec": 0.0,
            "video_composition_duration_sec": 0.0,
            "youtube_upload_duration_sec": 0.0,
            "whisper_fallback_count": 0,
            "background_type": None,  # "gameplay" | "manga_cover" | "solid_color"
            "post_virality_score": None,
            "segments_count": 0,
            "success": False,
            "error_type": None,  # "tts_failed" | "video_failed" | "youtube_failed" | "rate_limited"
            "error_message": None,
            "subreddit": None,
            "post_id": None,
            "youtube_video_id": None,
        }

    def record(self, key: str, value) -> None:
        """Record a metric value."""
        if self.enabled:
            self.metrics[key] = value
            logger.debug(f"Metric recorded: {key}={value}")

    def start_timer(self, key: str) -> float:
        """Start a timer and return the start time."""
        if not self.enabled:
            return 0.0
        return time.time()

    def end_timer(self, key: str, start_time: float) -> float:
        """End a timer and record the duration."""
        if not self.enabled:
            return 0.0
        duration = time.time() - start_time
        self.record(key, duration)
        return duration

    def increment_counter(self, key: str, amount: int = 1) -> None:
        """Increment a counter metric."""
        if not self.enabled:
            return
        current = self.metrics.get(key, 0)
        self.metrics[key] = current + amount
        logger.debug(f"Counter incremented: {key} += {amount}")

    def mark_success(self) -> None:
        """Mark the pipeline as successful."""
        if self.enabled:
            self.metrics["success"] = True
            self.metrics["end_time"] = time.time()
            logger.info("Pipeline marked as successful")

    def mark_error(self, error_type: str, message: str = "") -> None:
        """Mark the pipeline as failed with error details."""
        if self.enabled:
            self.metrics["success"] = False
            self.metrics["error_type"] = error_type
            self.metrics["error_message"] = message
            self.metrics["end_time"] = time.time()
            logger.error(f"Pipeline error: {error_type} - {message}")

    def export_json(self, output_dir: str = "output") -> str | None:
        """
        Export metrics to JSON file and return the path.

        Args:
            output_dir: Directory to save metrics file

        Returns:
            Path to metrics file, or None if disabled or error
        """
        if not self.enabled:
            return None

        try:
            # Calculate total duration
            if "end_time" in self.metrics and "start_time" in self.metrics:
                total_duration = self.metrics["end_time"] - self.metrics["start_time"]
                self.metrics["total_duration_sec"] = total_duration

            # Create metrics directory
            metrics_dir = os.path.join(output_dir, "_metrics")
            os.makedirs(metrics_dir, exist_ok=True)

            # Generate filename with timestamp
            now = datetime.now()
            filename = now.strftime("metrics_%Y%m%d_%H%M%S.json")
            filepath = os.path.join(metrics_dir, filename)

            # Write metrics
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, indent=2, default=str)

            logger.info(f"Metrics exported to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return None

    def export_to_datadog(self, api_key: str | None = None) -> bool:
        """
        Export metrics to Datadog if API key is available.

        Args:
            api_key: Datadog API key (uses env var if not provided)

        Returns:
            True if successful, False otherwise
        """
        api_key = api_key or os.environ.get("DATADOG_API_KEY")
        if not api_key or not self.enabled:
            return False

        try:
            import requests

            # Datadog metrics API endpoint
            url = "https://api.datadoghq.com/api/v1/series"
            headers = {"DD-API-KEY": api_key}

            # Format metrics for Datadog (series format)
            timestamp = int(time.time())
            series = []

            for key, value in self.metrics.items():
                if isinstance(value, (int, float)) and key.endswith("_sec"):
                    series.append({
                        "metric": f"reddit_shorts.{key}",
                        "points": [[timestamp, value]],
                        "type": "gauge",
                    })

            if series:
                payload = {"series": series}
                response = requests.post(url, json=payload, headers=headers, timeout=5)
                if response.status_code == 202:
                    logger.info("Metrics sent to Datadog")
                    return True
                else:
                    logger.warning(f"Datadog upload failed: {response.status_code}")
                    return False

            return False

        except ImportError:
            logger.warning("requests library not installed; Datadog export skipped")
            return False
        except Exception as e:
            logger.warning(f"Datadog export failed: {e}")
            return False

    def get_summary(self) -> dict:
        """Get a summary of collected metrics."""
        summary = {
            "status": "success" if self.metrics["success"] else "failed",
            "total_duration": self.metrics.get("total_duration_sec", 0),
            "tts_duration": self.metrics.get("tts_duration_sec", 0),
            "video_duration": self.metrics.get("video_composition_duration_sec", 0),
            "segments_generated": self.metrics.get("segments_count", 0),
        }
        if self.metrics.get("error_type"):
            summary["error"] = f"{self.metrics['error_type']}: {self.metrics.get('error_message', '')}"
        if self.metrics.get("youtube_video_id"):
            summary["youtube_video"] = f"https://youtu.be/{self.metrics['youtube_video_id']}"
        return summary
