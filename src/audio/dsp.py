import numpy as np
from pedalboard import (
    Pedalboard,
    Delay,
    HighpassFilter,
    LowpassFilter,
    Compressor,
    Limiter,
)
from src.config import TARGET_SAMPLE_RATE

# 1. NORMAL VOICE DSP: Crisp metallic Cephalon resonator (keep as-is since you liked it!)
NORMAL_PEDALBOARD = Pedalboard([
    HighpassFilter(cutoff_frequency_hz=220),
    Delay(delay_seconds=0.012, feedback=0.15, mix=0.22),
    Compressor(threshold_db=-18, ratio=3.0),
    Limiter(threshold_db=-3.0),
])

# 2. GLITCH VOICE DSP: Zero PitchShift/Distortion so your Glitch Clone stays 100% intelligible
GLITCH_PEDALBOARD = Pedalboard([
    HighpassFilter(cutoff_frequency_hz=120),  # Keep the natural low-end from your angry clone
    LowpassFilter(cutoff_frequency_hz=6500),
    Delay(delay_seconds=0.015, feedback=0.20, mix=0.25),  # Tight metallic double
    Compressor(threshold_db=-18, ratio=3.5),
    Limiter(threshold_db=-3.0),
])


def ensure_mono_and_resample(
    audio: np.ndarray, orig_sr: int, target_sr: int = TARGET_SAMPLE_RATE
) -> np.ndarray:
    """Ensures audio is 1D float32 mono and resampled to target_sr."""
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = audio.astype(np.float32)

    if orig_sr != target_sr and len(audio) > 0:
        duration = len(audio) / orig_sr
        target_length = int(duration * target_sr)
        old_indices = np.linspace(0, len(audio) - 1, num=len(audio))
        new_indices = np.linspace(0, len(audio) - 1, num=target_length)
        audio = np.interp(new_indices, old_indices, audio).astype(np.float32)

    return audio


def make_cd_skip_stutter(audio: np.ndarray, sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """
    Instead of a fake sine-wave beep, grabs the first 35ms of Ordis's actual glitched word
    and stutters it twice (like a cracked Cephalon memory buffer skipping).
    """
    slice_len = int(sr * 0.035)  # 35ms slice
    if len(audio) <= slice_len * 2:
        return audio

    stutter_chunk = audio[:slice_len] * 0.6
    gap = np.zeros(int(sr * 0.012), dtype=np.float32)
    return np.concatenate([stutter_chunk, gap, stutter_chunk, gap, audio], axis=0)


def apply_normal_dsp(audio: np.ndarray, sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Applies the crisp 12ms metallic Cephalon comb filter to normal speech."""
    if len(audio) == 0:
        return audio
    return NORMAL_PEDALBOARD(audio, sr)


def apply_glitch_dsp(audio: np.ndarray, sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Uses the clean Glitch Voice Clone with a 35ms buffer-stutter entrance and zero pitch warping."""
    if len(audio) == 0:
        return audio

    voiced = GLITCH_PEDALBOARD(audio, sr)
    return make_cd_skip_stutter(voiced, sr)