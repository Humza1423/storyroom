"""Shared deterministic window math for estimates and worker indexing."""

import math

from . import config


def segment_windows(frame_count):
    windows = []
    start = 0
    while start < frame_count:
        end = min(start + config.VISUAL_WINDOW_FRAMES, frame_count)
        if end > start:
            windows.append((start, end))
        if end >= frame_count:
            break
        start += config.VISUAL_STRIDE_FRAMES
    return windows


def sampled_frames(start_frame, end_frame):
    # Embedding 2 samples videos no longer than 32 seconds at 1 fps.
    return max(1, math.ceil((end_frame - start_frame) / config.FPS))
