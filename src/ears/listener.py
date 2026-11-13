import os
import queue
import logging
import numpy as np
import sounddevice as sd
from concurrent.futures import ThreadPoolExecutor
import re
from collections import deque
import webrtcvad

# Whisper's common phonetic spellings when someone says "Ordis" or "Hey Ordis"
ORDIS_WAKE_PATTERNS = re.compile(
    r"^(?:hey\s+|yo\s+|ok\s+|okay\s+)?(ordis|orders|otis|ortiz|artist|horus|hardest|oldest)\b[,.\?!\s]*",
    re.IGNORECASE,
)

# anything but make an account that's too much effort
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("faster_whisper").setLevel(logging.ERROR)

from faster_whisper import WhisperModel
from src.config import MIC_SAMPLE_RATE, WHISPER_MODEL_SIZE
from src.ears.biometrics import OperatorVerifier


class OrdisEars:
    """captures audio, checks if the voice is me, and then transcribes it"""

    def __init__(self) -> None:
        self.verifier = OperatorVerifier()
        self.pool = ThreadPoolExecutor(max_workers=2)
        try:
            self.whisper = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",
                local_files_only=True,
            )
        except Exception:
            self.whisper = WhisperModel(
                WHISPER_MODEL_SIZE, device="cpu", compute_type="int8"
            )

    def record_utterance(
        self,
        silence_threshold: float = 0.020,  
        silence_duration_s: float = 0.6,
        max_duration_s: float = 12.0,
    ) -> np.ndarray:
        """
        Uses Google WebRTC Voice Activity Detection (frequency-based) instead of raw volume,
        so loud laptop fans are ignored and it only records human speech.
        """
        # Aggressiveness mode 3 (0-3) is the strictest at filtering out fan/background noise
        vad = webrtcvad.Vad(3)

        # WebRTC VAD requires 10ms, 20ms, or 30ms frames at 16000Hz (30ms = 480 samples)
        frame_duration_ms = 30
        frame_size = int(MIC_SAMPLE_RATE * (frame_duration_ms / 1000.0))  # 480 samples
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            audio_queue.put(indata.copy().flatten())

        pre_roll: deque[np.ndarray] = deque(maxlen=10)  # 300ms pre-roll before speech starts
        chunks: list[np.ndarray] = []
        has_spoken = False
        speech_streak = 0
        silent_frames = 0

        max_silent_frames = int((silence_duration_s * 1000) / frame_duration_ms)
        max_total_frames = int((max_duration_s * 1000) / frame_duration_ms)

        with sd.InputStream(
            samplerate=MIC_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=frame_size,
            callback=callback,
        ):
            for _ in range(max_total_frames):
                chunk = audio_queue.get()

                # Convert float32 (-1.0 to 1.0) to 16-bit PCM bytes for WebRTC VAD
                pcm16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                is_speech = vad.is_speech(pcm16, MIC_SAMPLE_RATE)

                if not has_spoken:
                    pre_roll.append(chunk)
                    if is_speech:
                        speech_streak += 1
                        # Require 3 consecutive speech frames (90ms) to trigger so clicks don't trip it
                        if speech_streak >= 3:
                            has_spoken = True
                            chunks.extend(pre_roll)
                            silent_frames = 0
                    else:
                        speech_streak = 0
                else:
                    chunks.append(chunk)
                    if is_speech:
                        silent_frames = 0
                    else:
                        silent_frames += 1
                        if silent_frames >= max_silent_frames:
                            break

        if not has_spoken or not chunks:
            return np.zeros(0, dtype=np.float32)

        voiced_chunks = (
            chunks[:-max_silent_frames] if len(chunks) > max_silent_frames else chunks
        )
        return np.concatenate(voiced_chunks, axis=0)

    def _transcribe_only(self, audio: np.ndarray, initial_prompt: str | None = None) -> str:
        segments, _ = self.whisper.transcribe(
            audio,
            beam_size=1,
            language="en",
            vad_filter=True,
            initial_prompt=initial_prompt,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def listen_and_transcribe(self) -> tuple[str, bool, float]:
        """
        Records speech, checks if speaker is the Operator, and transcribes.
        Returns: (transcribed_text, is_operator, biometric_score)
        """
        audio = self.record_utterance()
        if len(audio) == 0:
            return "", False, 0.0

        bio_future = self.pool.submit(self.verifier.verify, audio)
        stt_future = self.pool.submit(self._transcribe_only, audio)

        is_operator, score = bio_future.result()
        text = stt_future.result()

        return text, is_operator, score

    def listen_for_wake_word(self) -> tuple[str, bool, float, bool]:
        """
        blocks until phrase starts with "ordis"
        returns (command_text, is_operator, similarity_score, needs_follow_up_listen)
        """
        while True:
            audio = self.record_utterance(
                silence_threshold=0.020,
                silence_duration_s=0.45,
                max_duration_s=10.0,
            )
            if len(audio) == 0:
                continue

            raw_text = self._transcribe_only(
                audio, initial_prompt="Ordis, Cephalon Ordis, Operator."
            )
            if not raw_text:
                continue

            match = ORDIS_WAKE_PATTERNS.match(raw_text)
            if not match:
                continue

            is_operator, score = self.verifier.verify(audio)

            remainder = raw_text[match.end():].strip()
            if len(remainder) >= 3:
                return f"Ordis, {remainder}", is_operator, score, False
            else:
                return "", is_operator, score, True