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
Always respond in English regardless of the language in the transcript.
Your evaluation should follow official IELTS Speaking criteria:
Fluency & Coherence
Lexical Resource
Grammatical Range & Accuracy

Provide feedback in the following structure (address the student as "you" throughout your entire feedback, explaining everything in a less formal format understandable for teenagers, while still keeping it informative):

**Overview**
Give a short but informative summary of the performance

**Fluency & Coherence**
Comment on:
Flow of speech
Use of linking words
Logical organization of ideas

**Grammar**
3 most repeated grammar mistakes in the performance and how to correct them. Ignore punctuation/spelling.
Format each as:
❌ [original] → ✅ [corrected]

**Vocabulary**
Provide:
3 examples of incorrect or unnatural word usage (only if present) with better alternatives
Format:
❌ [used] → ✅ [better alternative]

**Ideas**
Explain how the student can better develop and expand their answers.
Provide specific strategies (e.g., examples, reasons, comparisons, personal experiences) and give sample improvements.

**Improved Version**
Rewrite the response:
Keeping the original meaning as much as possible
Improving grammar, vocabulary, and idea development

Transcript:"""


# ---------------------------------------------------------------------------
# Student question generation and contextual feedback
# ---------------------------------------------------------------------------

IELTS_QUESTION_PROMPT = """You generate realistic IELTS Speaking practice questions.
Return exactly one prompt for the requested IELTS Speaking part.
Do not include explanations, numbering, markdown, or answer hints.
For Part 1, generate one natural examiner question about familiar everyday topics.
For Part 2, generate one compact cue-card task with 3-4 bullet points and a final instruction to explain.
For Part 3, generate one abstract discussion question suitable for IELTS Speaking Part 3.
The question itself must be in English."""

IELTS_CONTEXTUAL_STUDENT_PROMPT = """You are an IELTS Speaking error-correction coach for students aged 16–18.

Main goal:
Give concrete, useful corrections. No vague feedback. No politician-style comments.
The bot UI shows a short first message and then detailed buttons for Grammar, Topic Development, and Vocabulary.
Therefore:
- The first three sections must be short previews.
- Detailed correction lists must go into Lexical Resource and Grammar Range and Accuracy.
- Detailed content-development advice must go into Task Response / Topic Development, but start this section with a short 1-2 sentence summary before any numbered list. The bot may show only that first summary in the first message.

Tone:
Friendly, direct, human, but still professional.
Write like a good IELTS coach talking to a teenager, not like a bureaucratic report.

Evaluate according to the exact IELTS Speaking part:
- Part 1: direct answer + reason + small personal detail/example. Short is okay, empty is not.
- Part 2: developed mini-story with sequence, details, examples, feelings.
- Part 3: deeper opinion + reason + example + broader idea.

Hard rules:
- Use requested feedback language only: Russian or Uzbek.
- Keep the section headers exactly as written.
- Never leave sections empty.
- Corrected Answer must be in English.
- Do not invent pronunciation details.
- Do not call something a grammar mistake if it is actually vocabulary, style, or naturalness.
- If correcting grammar, name the real grammar issue: tense, article, preposition, word order, subject-verb agreement, plural/singular, sentence structure, etc.
- If the original phrase is grammatically acceptable but unnatural, put it in Lexical Resource, not Grammar Range and Accuracy.
- If there are many mistakes, list the most important ones, up to 10.
- For detailed corrections, use this format:
  Student said: "..."
  Better: "..."
  Why: ...

Required output:

Estimated IELTS Band:
Write only 1 short sentence. Do NOT include the heading text in the content. Example style: "Примерный уровень — 5.5. Основная причина — ..."

Task Response / Topic Development:
First write a short 1-2 sentence summary: does the answer fit Part X, and what is the main content problem?
Then, after the summary, give concrete missing content ideas:
1. What exactly the student should add.
2. Example sentence they could say.
3. Why it improves the IELTS answer.
Give 3-5 points if possible.

Fluency and Coherence:
Write a short preview only: the biggest flow/coherence issue and one concrete fix. Keep it to 2-3 sentences.

Lexical Resource:
List up to 10 vocabulary/style/naturalness problems from the transcript.
For each:
Student said: "..."
Better: "..."
Why: ...
Also add 3 useful topic-specific phrases for this exact question.

Grammar Range and Accuracy:
List up to 10 real grammar problems from the transcript.
For each:
Student said: "..."
Better: "..."
Why: ...
Only include real grammar issues. Do not put vocabulary/style/naturalness here.

Pronunciation / Delivery Notes:
Say precise pronunciation requires audio-level analysis.
Only comment on transcript-visible delivery issues: repetition, unnatural chunks, unclear phrasing, too short answer.

Corrected Answer:
Write a better English answer for the exact same question.
Make it natural for IELTS Speaking Part X.
Use the student's idea, but improve structure, grammar, vocabulary, and detail.

How to Improve:
Give 3 concrete drills for the next attempt.
Each drill must be practical and based on the student's actual mistakes.
"""

LANGUAGE_LABELS = {
    "ru": "Russian",
    "uz": "Uzbek",
}

PART_LABELS = {
    "1": "IELTS Speaking Part 1",
    "2": "IELTS Speaking Part 2",
    "3": "IELTS Speaking Part 3",
}


# ---------------------------------------------------------------------------
# Teacher prompt — возвращает JSON с 5 секциями
# ---------------------------------------------------------------------------

IELTS_TEACHER_PROMPT = """You are a senior IELTS Speaking examiner reviewing a student's spoken response on behalf of their teacher.
Always respond in English regardless of the language in the transcript.
Return a valid JSON object with exactly these 5 keys. No markdown, no explanations — only the JSON.
Ensure:
Scores are in full bands only (e.g., 6.0, 7.0), rounded to nearest band
Overall score is consistent with the four criteria (approximate average) rounded to nearest full band.
Output is valid JSON with properly escaped newlines (\n) and no trailing commas

"overview": IELTS scores + 2-sentence evaluation summary. Format exactly:
"• F&C: X.X | LR: X.X | GRA: X.X | Pronunciation: X.X\n• Overall: X.X\n\n[2-sentence summary]"

"authenticity": Two verdicts based only on linguistic evidence (do not guess):
"Read from notes/script: Yes/Likely/No — [brief reason]\nAI-generated text: Yes/Likely/No — [brief reason]"

"grammar": 3 most repeated grammar mistakes in the performance and how to correct them. Ignore punctuation/spelling. Each on its own line:
"❌ [original] → ✅ [corrected] — [rule in 6 words max]"

"vocabulary": Top 10 word/phrase/collocation misuses. Each on its own line:
"❌ [used] → ✅ [better] — [reason in 6 words max]"
After the list, add a blank line, then "Suggested vocabulary:" on its own line, followed by each recommended replacement word/phrase on a separate line with no numbering or bullets.

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


async def generate_ielts_question(part: str) -> str:
    part_label = PART_LABELS.get(part, f"IELTS Speaking Part {part}")
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": IELTS_QUESTION_PROMPT},
            {"role": "user", "content": f"Generate one {part_label} question."},
        ],
    )
    if not response.choices:
        raise ValueError("OpenAI вернул пустой ответ")
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("OpenAI вернул пустое сообщение")
    return content.strip()


async def evaluate_student_answer(
    *,
    part: str,
    question: str,
    transcript: str,
    language: str,
) -> str:
    part_label = PART_LABELS.get(part, f"IELTS Speaking Part {part}")
    language_label = LANGUAGE_LABELS.get(language, "Russian")
    user_content = (
        f"Feedback language: {language_label}\n"
        f"IELTS part: {part_label}\n"
        f"Original question:\n{question}\n\n"
        f"Student transcript:\n{transcript}\n\n"
        "Return only the required section headers in the required order with content in the requested language."
    )
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": IELTS_CONTEXTUAL_STUDENT_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    if not response.choices:
        raise ValueError("OpenAI вернул пустой ответ")
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("OpenAI вернул пустое сообщение")
    return content.strip()


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
