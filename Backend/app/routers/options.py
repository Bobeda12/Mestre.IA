from fastapi import APIRouter

from app.infra.data_manager import regras
from app.services.adventure import catalogo_aventura

router = APIRouter(prefix="/options", tags=["options"])


@router.get("/aventura")
def get_aventura() -> dict:
    return catalogo_aventura()


@router.get("/races")
def get_races() -> dict:
    return {"opcoes": regras.get_races_list()}


@router.get("/classes")
def get_classes() -> dict:
    return {"opcoes": regras.get_classes_list()}


@router.get("/races/{name}")
def get_race_info(name: str) -> dict:
    return regras.get_race_details(name)


@router.get("/classes/{name}")
def get_class_info(name: str) -> dict:
    return regras.get_class_details(name)
