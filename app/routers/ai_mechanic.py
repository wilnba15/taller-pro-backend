from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI
import os

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class DiagnosticRequest(BaseModel):
    problem: str

PROMPT = """
Eres un experto mecánico automotriz con más de 20 años de experiencia.
Responde con diagnóstico, causas, pruebas y recomendación.
"""

@router.post("/ai/diagnostic")
def diagnostic(data: DiagnosticRequest):
    if not os.getenv("OPENAI_API_KEY"):
        return {"diagnostic": "IA no configurada"}

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": data.problem}
        ]
    )

    return {"diagnostic": response.choices[0].message.content}
