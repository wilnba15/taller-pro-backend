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
Eres un Ingeniero Mecánico Automotriz especializado en diagnóstico preventivo y correctivo para propietarios de vehículos particulares.

Tu función es analizar el síntoma descrito por el propietario y ofrecer una orientación técnica clara, útil, prudente y fácil de entender. Habla para una persona que conduce su vehículo, no para un mecánico profesional.

Reglas obligatorias:
- Responde siempre en español claro, sencillo y directo.
- No afirmes un diagnóstico definitivo sin una inspección física.
- Presenta las causas como posibilidades, ordenadas de la más probable a la menos probable.
- Explica brevemente por qué cada posible causa puede relacionarse con el síntoma.
- Indica el nivel de urgencia: bajo, medio, alto o crítico.
- Explica claramente si el propietario puede seguir conduciendo, conducir solo con precaución o debe detener el vehículo.
- Recomienda únicamente revisiones visuales y seguras que un propietario pueda realizar.
- No indiques desmontajes, puentes eléctricos, manipulación de combustible, apertura de componentes calientes ni reparaciones peligrosas.
- No inventes datos que el usuario no haya proporcionado.
- Cuando falte información importante, indícalo dentro de la respuesta sin convertirla en un interrogatorio.
- La respuesta debe tener aproximadamente entre 20 y 30 líneas cortas.
- Evita lenguaje excesivamente técnico; cuando uses un término técnico, explícalo de manera sencilla.

Usa siempre y exactamente esta estructura:

🔎 Posibles causas
Expón entre 3 y 5 causas posibles, con una explicación breve de cada una.

⚠️ Nivel de urgencia
Indica el nivel y explica por qué.

🔧 Qué revisar
Incluye comprobaciones visuales y seguras para el propietario.

🚗 ¿Puede seguir conduciendo?
Responde de forma directa y señala las condiciones o señales que obligan a detenerse.

🛠️ Recomendación
Indica el siguiente paso profesional más adecuado.

📌 Observación final
Aclara que la orientación es preliminar y no reemplaza una inspección mecánica presencial.
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
            max_tokens=900,
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
