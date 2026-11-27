import asyncio
import numpy as np
import sounddevice as sd
from src.config import TTS_ENABLED, TARGET_SAMPLE_RATE, MIC_SAMPLE_RATE
from src.audio.providers import get_tts_provider
from src.audio.dsp import apply_normal_dsp, apply_glitch_dsp
import time
import webrtcvad


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

    async def speak_async(self, segments: list[tuple[str, str]], allow_interrupt: bool = True) -> bool:
        if not self.enabled or not self.provider or not segments:
            return False

        rendered_chunks: list[np.ndarray] = []
        for mode, text in segments:
            chunk = await self._render_segment(mode, text)
            if len(chunk) > 0:
                rendered_chunks.append(chunk)

        if not rendered_chunks:
            return False

        # Stitch segments together with a 35ms gap
        gap = np.zeros(int(TARGET_SAMPLE_RATE * 0.035), dtype=np.float32)
        stitched: list[np.ndarray] = []
        for i, chunk in enumerate(rendered_chunks):
            stitched.append(chunk)
            if i < len(rendered_chunks) - 1:
                stitched.append(gap)

        master_audio = np.concatenate(stitched, axis=0)
        duration_s = len(master_audio) / float(TARGET_SAMPLE_RATE)

        sd.play(master_audio, samplerate=TARGET_SAMPLE_RATE)
        start_time = time.monotonic()

        if not allow_interrupt:
            try:
                while (time.monotic() - start_time) < duration_s:
                    await asyncio.sleep(0.05)
            except KeyboardInterrupt:
                sd.stop()
                return True
            return False
        # mic listen for me talking over ordis
        vad = webrtcvad.Vad(3)
        frames_ms = 30
        frame_size = int(MIC_SAMPLE_RATE * (frames_ms / 1000.0))
        interrupt_count = 0
        echo_baseline_rms = 0.04 #arbitrary number for now. need to play around with this

        try:
            with sd.InputStream(
                samplerate=MIC_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=frame_size,
            ) as mic_stream:
                #calibrate with first x amount of time ordis talks
                calib_rms = []
                for _ in range(6):
                    if (time.monotonic() - start_time) >= duration_s:
                        break
                    data, _ = mic_stream.read(frame_size)
                    calib_rms.append(float(np.sqrt(np.mean(data**2))))
                if calib_rms:
                    # stuff that gets heard OVER ordis's voice
                    echo_baseline_rms = max(0.045, max(calib_rms) * 1.45)

                while (time.monotonic() - start_time) < duration_s:
                    data, _ = mic_stream.read(frame_size)
                    chunk = data.flatten()
                    rms = float(np.sqrt(np.mean(chunk**2)))
                    #need to change float32 into int16
                    pcm16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                    is_speech = vad.is_speech(pcm16, MIC_SAMPLE_RATE)

                    if is_speech and rms > echo_baseline_rms:
                        interrupt_count += 1
                        # 5 frames (150ms) for now, try different numbers if not desirable
                        if interrupt_count >= 5:
                            sd.stop()
                            return True
                    else:
                        interrupt_count = max(0, interrupt_count -1)
        except KeyboardInterrupt:
            sd.stop()
            return True
        
        sd.wait()
        return False
    
# OLDER ITERATION OF SPEAK FUNCTION THAT DOES NOT ACCOUNT FOR INTERRUPTS AND PASSING THAT STATUS DOWN
#    def speak(self, segments: list[tuple[str, str]]) -> None:
#        """Synchronous wrapper."""
#        if not self.enabled:
#            return
#        try:
#            asyncio.run(self.speak_async(segments))
#
#        except KeyboardInterrupt:
#            sd.stop()

    def speak(self, segments: list[tuple[str, str]]) -> bool:
        if not self.enabled:
            return
        try:
            return asyncio.run(self.speak_async(segments))
        except KeyboardInterrupt:
            sd.stop()