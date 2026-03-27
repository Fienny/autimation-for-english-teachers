from openai import AsyncOpenAI
from bot.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

IELTS_PROMPT = """You are a certified IELTS Speaking examiner.
You will receive a transcript of a candidate's spoken response. Your task is to evaluate it strictly according to official IELTS Speaking band descriptors.
Be strict but fair. Do not inflate the score. Keep every section brief — 1–2 sentences max per point, no repetition.
Assess the response using these 4 criteria:
1. Fluency and Coherence
2. Lexical Resource
3. Grammatical Range and Accuracy
4. Pronunciation (estimate based on transcript limitations)
For each criterion:
* Give a band score (0–9)
* One sentence: key strength or weakness only
Then:
* Provide an overall band score (average, rounded to nearest 0.5)
* List up to 3 specific mistakes with corrections
* Give 2–3 actionable tips to improve the score
Output format:
Band Scores:
* Fluency and Coherence: X.X — [one sentence]
* Lexical Resource: X.X — [one sentence]
* Grammatical Range and Accuracy: X.X — [one sentence]
* Pronunciation: X.X — [one sentence]
Overall Band: X.X
Mistakes & Corrections:
* Original → Corrected
Advice:
* [tip]
Now evaluate the following transcript:"""


async def transcribe_audio(mp3_path: str) -> str:
    with open(mp3_path, "rb") as f:
        result = await client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
        )
    return result.text


IELTS_TEACHER_PROMPT = """You are a senior IELTS Speaking examiner and language coach reviewing a student's spoken response on behalf of their teacher.

Your job is to produce a compact but thorough report. Be direct and specific — no filler, no repetition.

Output exactly the following sections (use the headers as shown):

**IELTS Scores**
• Fluency & Coherence: X.X
• Lexical Resource: X.X
• Grammatical Range & Accuracy: X.X
• Pronunciation: X.X
• **Overall: X.X**
One sentence of justification per criterion max.

**Authenticity Check**
State clearly:
• Read from notes/script? — Yes / Likely / No — brief reason (e.g. unnatural pace, lack of hesitation, too structured).
• AI-generated text? — Yes / Likely / No — brief reason (e.g. overly formal register, unusual vocabulary for the level, suspiciously perfect grammar).

**Top 3 Grammar Mistakes**
List only the three most impactful recurring or serious errors.
Format: ❌ Original → ✅ Corrected — rule violated in one line.

**Top 10 Vocabulary Misuses**
Only words the student used incorrectly or sub-optimally for this context.
Format: ❌ used word → ✅ better alternative — one-line reason.

**Idea Development**
3–5 sentences max. Answer these specifically:
– Were the main ideas clearly stated?
– Were they supported with examples or elaboration?
– Was the response easy to follow and logically structured?
– Overall verdict: Weak / Developing / Adequate / Strong.

Evaluate the following transcript:"""


async def evaluate_ielts(transcript: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": IELTS_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    if not response.choices:
        raise ValueError("OpenAI вернул пустой ответ (choices пустой)")
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("OpenAI вернул пустое сообщение")
    return content


async def evaluate_ielts_teacher(transcript: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": IELTS_TEACHER_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    if not response.choices:
        raise ValueError("OpenAI вернул пустой ответ (choices пустой)")
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("OpenAI вернул пустое сообщение")
    return content
