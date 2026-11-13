import re
from google import genai
from google.genai import types
from src.config import GEMINI_API_KEY, GEMINI_MODEL, TEMPERATURE, ORDIS_SYSTEM_PROMPT
from src.tools import ORDIS_TOOLS

GLITCH_PATTERN = re.compile(r"<glitch>(.*?)</glitch>", re.IGNORECASE | re.DOTALL)

def parse_ordis_response(raw_text: str) -> list[tuple[str, str]]:
    """
    Splits Ordis's output into ('normal', text) and ('glitch', text) tuples.
    'normal' chunks go to clean TTS and 'glitch' chunks get pitch/bitcrush DSP.
    """
    segments: list[tuple[str, str]] = []
    last_index = 0

    for match in GLITCH_PATTERN.finditer(raw_text):
        if match.start() > last_index:
            normal_chunk = raw_text[last_index:match.start()].strip()
            if normal_chunk:
                segments.append(("normal", normal_chunk))
        glitch_chunk = match.group(1).strip()
        if glitch_chunk:
            segments.append(("glitch", glitch_chunk))
        last_index = match.end()

    if last_index < len(raw_text):
        tail_chunk = raw_text[last_index:].strip()
        if tail_chunk:
            segments.append(("normal", tail_chunk))

    return segments


class OrdisBrain:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise ValueError("API key missing or invalid")

        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.chat = self.client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction = ORDIS_SYSTEM_PROMPT,
                tools = ORDIS_TOOLS,
                temperature = TEMPERATURE,
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ],
            ),
        )

    def send(self, user_input: str) -> list[tuple[str, str]]:
        """Sends message to Ordis and returns parsed ('normal'|'glitch', text) segments."""
        response = self.chat.send_message(user_input)
        return parse_ordis_response(response.text or "")
