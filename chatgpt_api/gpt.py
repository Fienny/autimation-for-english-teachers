from openai import AsyncOpenAI
from bot.config import OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

IELTS_PROMPT = """You are a certified IELTS Speaking examiner.
You will receive a transcript of a candidate's spoken response. Your task is to evaluate it strictly according to official IELTS Speaking band descriptors.
Assess the response using these 4 criteria:
1. Fluency and Coherence
2. Lexical Resource
3. Grammatical Range and Accuracy
4. Pronunciation (estimate based on transcript limitations)
For each criterion:
* Give a band score (0–9)
* Provide a clear explanation of strengths and weaknesses
Then:
* Provide an overall band score (average, rounded to nearest 0.5)
* Highlight specific mistakes with corrections
* Suggest improved versions of sentences where appropriate
* Give actionable advice on how to improve the score
Be strict but fair. Do not inflate the score.
Output format:
Band Scores:
* Fluency and Coherence: X.X
* Lexical Resource: X.X
* Grammatical Range and Accuracy: X.X
* Pronunciation: X.X
Overall Band: X.X
Analysis: [Detailed evaluation]
Mistakes & Corrections:
* Original → Corrected → Explanation
Improved Sample Answer: [Rewrite a better version of the response aiming for Band 7+]
Advice: [Specific actionable tips]
Now evaluate the following transcript:"""


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
            {"role": "system", "content": IELTS_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    return response.choices[0].message.content
