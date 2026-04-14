import json

from openai import AsyncOpenAI
from bot.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

TG_LIMIT = 4096


def split_message(text: str) -> list[str]:
    """Split text into chunks fitting Telegram's 4096-char limit, breaking on newlines."""
    if len(text) <= TG_LIMIT:
        return [text]
    chunks = []
    while text:
        if len(text) <= TG_LIMIT:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, TG_LIMIT)
        if split_at == -1:
            split_at = TG_LIMIT
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ---------------------------------------------------------------------------
# Student prompt — от заказчика, без оценки произношения
# ---------------------------------------------------------------------------

IELTS_STUDENT_PROMPT = """Evaluate and provide detailed feedback for the following IELTS Speaking performance.
Your evaluation should follow official IELTS Speaking criteria:
Fluency & Coherence
Lexical Resource
Grammatical Range & Accuracy
(Pronunciation if inferable from transcript)

Provide feedback in the following structure:

**Overview**
Give a short but informative summary of the performance

**Fluency & Coherence**
Comment on:
Flow of speech
Use of linking words
Logical organization of ideas

**Grammar**
Identify the 3 most frequent or serious grammar error types (e.g., tense, articles, prepositions, sentence structure). Ignore punctuation/spelling.
Format each as:
❌ [original] → ✅ [corrected]

**Vocabulary**
Provide:
3 examples of incorrect or unnatural word usage (only if present) with better alternatives
Format:
❌ [used] → ✅ [better alternative]
Brief comment on vocabulary range and appropriateness

**Ideas**
Explain how the student can better develop and expand their answers.
Provide specific strategies (e.g., examples, reasons, comparisons, personal experiences) and give sample improvements.

**Improved Version**
Rewrite the response:
Keeping the original meaning as much as possible
Improving grammar, vocabulary, and idea development

Transcript:


# ---------------------------------------------------------------------------
# Teacher prompt — возвращает JSON с 5 секциями
# ---------------------------------------------------------------------------

IELTS_TEACHER_PROMPT = """You are a senior IELTS Speaking examiner reviewing a student's spoken response on behalf of their teacher.
Return a valid JSON object with exactly these 5 keys. No markdown, no explanations — only the JSON.
Ensure:
Scores are in full bands only (e.g., 6.0, 7.0), rounded to nearest band
Overall score is consistent with the four criteria (approximate average) rounded to nearest full band.
Output is valid JSON with properly escaped newlines (\\n) and no trailing commas

"overview": IELTS scores + 2-sentence evaluation summary. Format exactly:
"• F&C: X.X | LR: X.X | GRA: X.X | Pronunciation: X.X\\n• Overall: X.X\\n\\n[2-sentence summary]"

"authenticity": Two verdicts based only on linguistic evidence (do not guess):
"Read from notes/script: Yes/Likely/No — [brief reason]\\nAI-generated text: Yes/Likely/No — [brief reason]"

"grammar": 3 recurring grammar error patterns, not isolated mistakes (e.g., tense, articles, prepositions, sentence structure). Ignore punctuation/spelling. Each on its own line:
"❌ [original] → ✅ [corrected] — [rule in 6 words max]"

"vocabulary": Top 10 word/phrase/collocation misuses (only if present). Each on its own line:
"❌ [used] → ✅ [better] — [reason in 6 words max]"

"ideas": 3–5 sentences evaluating clarity, support, and structure.
If fluency cannot be directly observed, infer cautiously.
End with verdict: Weak / Developing / Adequate / Strong.

Transcript to evaluate:"""


async def transcribe_audio(mp3_path: str) -> str:
    with open(mp3_path, "rb") as f:
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
        )
    return result.text


async def evaluate_ielts(transcript: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": IELTS_STUDENT_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    if not response.choices:
        raise ValueError("OpenAI вернул пустой ответ")
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("OpenAI вернул пустое сообщение")
    return content


async def evaluate_ielts_teacher(transcript: str) -> dict:
    """Returns a dict with keys: overview, authenticity, grammar, vocabulary, ideas."""
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": IELTS_TEACHER_PROMPT},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
    )
    if not response.choices:
        raise ValueError("OpenAI вернул пустой ответ")
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("OpenAI вернул пустое сообщение")
    return json.loads(content)
