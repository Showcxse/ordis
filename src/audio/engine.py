import asyncio
import numpy as np
import sounddevice as sd
from src.config import TTS_ENABLED, TARGET_SAMPLE_RATE
from src.audio.providers import get_tts_provider
from src.audio.dsp import apply_normal_dsp, apply_glitch_dsp


class OrdisVoiceEngine:
    """Parallel TTS synthesis, glitch DSP routing, and audio playback."""

    def __init__(self) -> None:
        self.enabled = TTS_ENABLED
        self.provider = get_tts_provider() if self.enabled else None

    async def _render_segment(self, mode: str, text: str) -> np.ndarray:
        if not self.provider or not text.strip():
            return np.zeros(0, dtype=np.float32)
        #SHELFED FOR NOW REMOVING THE DSP. MAY TRY THIS AGAIN LATER AT SOME POINT IDK
        #raw_audio = await self.provider.synthesize(text, mode)
        #if mode == "glitch":
        #    return apply_glitch_dsp(raw_audio, TARGET_SAMPLE_RATE)
        #return apply_normal_dsp(raw_audio, TARGET_SAMPLE_RATE)
        return await self.provider.synthesize(text, mode)

    async def speak_async(self, segments: list[tuple[str, str]]) -> None:
        if not self.enabled or not self.provider or not segments:
            return

        rendered_chunks: list[np.ndarray] = []
        for mode, text in segments:
            chunk = await self._render_segment(mode, text)
            if len(chunk) > 0:
                rendered_chunks.append(chunk)

        if not rendered_chunks:
            return

        # Stitch segments together with a 35ms gap
        gap = np.zeros(int(TARGET_SAMPLE_RATE * 0.035), dtype=np.float32)
        stitched: list[np.ndarray] = []
        for i, chunk in enumerate(rendered_chunks):
            stitched.append(chunk)
            if i < len(rendered_chunks) - 1:
                stitched.append(gap)

        master_audio = np.concatenate(stitched, axis=0)
        sd.play(master_audio, samplerate=TARGET_SAMPLE_RATE)
        sd.wait()

    def speak(self, segments: list[tuple[str, str]]) -> None:
        """Synchronous wrapper."""
        if not self.enabled:
            return
        try:
            asyncio.run(self.speak_async(segments))
        except KeyboardInterrupt:
            sd.stop()