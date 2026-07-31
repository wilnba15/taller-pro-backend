import os

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.swm import SwmAiQuery, SwmVehicle
from app.models.swm_user import SwmUser
from app.routers.swm_auth import get_current_swm_user

router = APIRouter(prefix="/swm-ai", tags=["SWM Care IA"])


class SwmAiAnalyzeRequest(BaseModel):
    problem: str = Field(..., min_length=5, max_length=1200)


class SwmAiAnalyzeResponse(BaseModel):
    analysis: str


SYSTEM_PROMPT = """
Eres el asistente mecánico de SWM Care para propietarios de vehículos.
Responde en español claro, sencillo y directo.
Tu respuesta debe ser breve: máximo 10 líneas cortas.
Incluye únicamente:
1. Posibles causas, sin afirmar un diagnóstico definitivo.
2. Qué puede revisar el usuario de forma visual y segura.
3. Nivel de urgencia: bajo, medio o alto.
4. Si puede conducir con precaución o debe detener el vehículo.
5. Recomendación final de revisión profesional.
No indiques desmontajes, puentes eléctricos ni reparaciones peligrosas.
No inventes datos que el usuario no haya proporcionado.
Finaliza aclarando que la orientación no reemplaza una revisión mecánica.
""".strip()


@router.post("/analyze", response_model=SwmAiAnalyzeResponse)
def analyze_vehicle_problem(
    payload: SwmAiAnalyzeRequest,
    current_user: SwmUser = Depends(get_current_swm_user),
    db: Session = Depends(get_db),
):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="La función de IA no está configurada.")

    problem = payload.problem.strip()
    vehicle = (
        db.query(SwmVehicle)
        .filter(SwmVehicle.user_id == current_user.id)
        .order_by(SwmVehicle.id.asc())
        .first()
    )

    vehicle_context = ""
    if vehicle:
        vehicle_context = (
            f"Vehículo registrado: {vehicle.model}, año {vehicle.year}, "
            f"kilometraje actual {vehicle.current_mileage} km.\n"
        )

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("SWM_AI_MODEL", "gpt-4o-mini"),
            temperature=0.3,
            max_tokens=320,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"{vehicle_context}Problema descrito por el usuario: {problem}",
                },
            ],
        )
        analysis = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="No se pudo analizar el problema en este momento. Intenta nuevamente.",
        ) from exc

    if not analysis:
        raise HTTPException(status_code=503, detail="La IA no generó una respuesta.")

    query = SwmAiQuery(
        vehicle_id=vehicle.id if vehicle else None,
        symptom=problem,
        ai_response=analysis,
    )
    db.add(query)
    db.commit()

    return {"analysis": analysis}
