import io
from abc import ABC, abstractmethod
import edge_tts
import httpx
import numpy as np
import soundfile as sf
from src.config import (
    EDGE_VOICE_ID,
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_ID_NORMAL,
    ELEVENLABS_VOICE_ID_GLITCH,
    ELEVENLABS_MODEL_ID,
    TTS_PROVIDER,
    TARGET_SAMPLE_RATE,
)
from src.audio.dsp import ensure_mono_and_resample
import asyncio


class TTSProvider(ABC):
    """Abstract interface for all Ordis Text-to-Speech backends."""

    @abstractmethod
    async def synthesize(self, text: str, mode: str) -> np.ndarray:
        """Synthesizes text and returns a 1D float32 numpy array at TARGET_SAMPLE_RATE."""
        pass


class EdgeTTSProvider(TTSProvider):
    """Free TTS provider for short-term tests."""

    def __init__(self, voice_id: str = EDGE_VOICE_ID) -> None:
        self.voice_id = voice_id

    async def synthesize(self, text: str, mode: str) -> np.ndarray:
        rate = "+8%" if mode == "normal" else "-4%"
        communicate = edge_tts.Communicate(text, self.voice_id, rate=rate)

        audio_bytes = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])

        if not audio_bytes:
            return np.zeros(0, dtype=np.float32)

        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        return ensure_mono_and_resample(data, sr, TARGET_SAMPLE_RATE)

class ElevenLabsProvider(TTSProvider):
    """Production dual-voice TTS provider for Normal & Glitched Cephalon Ordis clones."""

    def __init__(
        self,
        api_key: str = ELEVENLABS_API_KEY,
        voice_id_normal: str = ELEVENLABS_VOICE_ID_NORMAL,
        voice_id_glitch: str = ELEVENLABS_VOICE_ID_GLITCH,
        model_id: str = ELEVENLABS_MODEL_ID,
    ) -> None:
        if not api_key or not voice_id_normal:
            raise ValueError(
                "ElevenLabs requires ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID_NORMAL in .env"
            )
        self.api_key = api_key
        self.voice_id_normal = voice_id_normal
        self.voice_id_glitch = voice_id_glitch or voice_id_normal
        self.model_id = model_id
        self._fallback = EdgeTTSProvider()

    async def synthesize(self, text: str, mode: str) -> np.ndarray:
        active_voice_id = (
            self.voice_id_glitch if mode == "glitch" else self.voice_id_normal
        )
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{active_voice_id}"
            f"?output_format=mp3_44100_128"
        )
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        voice_settings = (
            {"stability": 0.50, "similarity_boost": 0.75}
            if mode == "normal"
            else {"stability": 0.35, "similarity_boost": 0.80}
        )
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": voice_settings,
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            for attempt in range(3):
                resp = await client.post(url, json=payload, headers=headers)

                if resp.status_code == 200:
                    data, sr = sf.read(io.BytesIO(resp.content), dtype="float32")
                    return ensure_mono_and_resample(data, sr, TARGET_SAMPLE_RATE)

                if resp.status_code == 429:
                    err_text = resp.text.lower()
                    if "quota" in err_text or "credit" in err_text:
                        print("\n[ElevenLabs Quota Reached — falling back to EdgeTTS]")
                        return await self._fallback.synthesize(text, mode)

                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue

                print(f"\n[ElevenLabs API Error {resp.status_code}]: {resp.text}")
                resp.raise_for_status()

        return await self._fallback.synthesize(text, mode)
    
def get_tts_provider() -> TTSProvider:
    """Factory function that returns the configured TTS provider."""
    if TTS_PROVIDER == "elevenlabs":
        return ElevenLabsProvider()
    return EdgeTTSProvider()