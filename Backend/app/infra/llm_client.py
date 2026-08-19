from groq import Groq

from app.infra.settings import settings

MODEL_NAME = settings.model_name


def _build_client() -> Groq | None:
    if not settings.groq_api_key:
        return None
    return Groq(api_key=settings.groq_api_key)


client = _build_client()
