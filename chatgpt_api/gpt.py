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

IELTS_STUDENT_PROMPT = """Evaluate and provide feedback for the following IELTS speaking performance.

Your feedback should be based on IELTS speaking criteria: grammar, lexical resources, how well the ideas are explained and expanded.

Provide the feedback as follows:

**Overview**
Short but informative overview of the performance.

**Grammar**
3 most repeated grammar mistakes in the performance and how to correct them. Format each as:
❌ [original] → ✅ [corrected]

**Vocabulary**
3 examples of words/collocations/phrases used incorrectly and what can be used instead. Format each as:
❌ [used] → ✅ [better alternative]

**Ideas**
Direction on how to better develop ideas to improve the performance. Give examples of what the student can include to do better next time.

**Improved Version**
An improved version of the performance with all mistakes in grammar, vocabulary and idea development corrected.

Now evaluate the following transcript:"""


# ---------------------------------------------------------------------------
# Teacher prompt — возвращает JSON с 5 секциями
# ---------------------------------------------------------------------------

IELTS_TEACHER_PROMPT = """You are a senior IELTS Speaking examiner reviewing a student's spoken response on behalf of their teacher.

Return a valid JSON object with exactly these 5 keys. No markdown wrapping, no extra text — only the JSON.

"overview": IELTS scores + 2-sentence evaluation summary. Format exactly:
"• F&C: X.X | LR: X.X | GRA: X.X | Pronunciation: X.X\\n• Overall: X.X\\n\\n[2-sentence summary]"

"authenticity": Two verdicts:
"Read from notes/script: Yes/Likely/No — [brief reason]\\nAI-generated text: Yes/Likely/No — [brief reason]"

"grammar": Top 3 grammar errors, each on its own line:
"❌ [original] → ✅ [corrected] — [rule in 6 words max]"

"vocabulary": Top 10 word/phrase misuses, each on its own line:
"❌ [used] → ✅ [better] — [reason in 6 words max]"

"ideas": 3–5 sentences: were ideas clear, supported with examples, logically structured? End with verdict: Weak / Developing / Adequate / Strong.

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
