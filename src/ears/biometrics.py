import os
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from src.config import MIC_SAMPLE_RATE, VOICEPRINT_PATH, SPEAKER_VERIFICATION_THRESHOLD

class OperatorVerifier:
    """checks whether spoken audio is my voice or not"""
    def __init__(self, voiceprint_path: str = VOICEPRINT_PATH) -> None:
        self.voiceprint_path = voiceprint_path

        self.encoder = VoiceEncoder(verbose=False)
        self.operator_embedding: np.ndarray | None = None

        if os.path.exists(self.voiceprint_path):
            self.operator_embedding = np.load(self.voiceprint_path)

    @property
    def is_enrolled(self) -> bool:
        return self.operator_embedding is not None

    def compute_embedding(self, audio_16k: np.ndarray) -> np.ndarray:
        """convert float32 array into 256d vector for resemblyzer to use"""
        wav = preprocess_wav(audio_16k, source_sr = MIC_SAMPLE_RATE)
        if len(wav) < MIC_SAMPLE_RATE * 0.6:
            #too short for resemblyzer to work
            return np.zeros(256, dtype=np.float32)
        return self.encoder.embed_utterance(wav)

    def enroll_from_samples(self, recordings: list[np.ndarray]) -> None:
        """averages multiple smaller recordings into one big one"""
        embeddings = [self.compute_embedding(r) for r in recordings]
        valid = [e for e in embeddings if np.linalg.norm(e) > 0]
        if not valid:
            raise ValueError("Recordings too short or quiet to build voiceprint")

        master = np.mean(valid, axis=0)
        master = master / np.linalg.norm(master) #normalized

        os.makedirs(os.path.dirname(self.voiceprint_path), exist_ok=True)
        np.save(self.voiceprint_path, master)

    def verify(self, audio_16k: np.ndarray) -> tuple[bool, float]:
        """
        basically i want this to return (is_me, similarity_score)
        default is true so i dont get locked out of my own thing when i inevitably mess this up
        """
        if not self.is_enrolled:
            return True, 1.0

        live_embed = self.compute_embedding(audio_16k)
        if np.linalg.norm(live_embed) == 0:
            return False, 0.0

        op_norm = self.operator_embedding / np.linalg.norm(self.operator_embedding)
        score = float(np.dot(op_norm, live_embed))
        return score >= SPEAKER_VERIFICATION_THRESHOLD, score
