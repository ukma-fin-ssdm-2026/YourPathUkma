"""
Ресурс «Система» (System): публічна конфігурація для фронтенду (GET /api/v1/config).

Без автентифікації. Ліміти тут мають збігатися з контрактом (docs/api/contract.md, §2.2 і §3.0),
щоб фронтенд брав їх звідси, а не дублював у власному коді.
"""

import os
from typing import Dict, Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["System"])

API_VERSION = "1.0.0"


class Limits(BaseModel):
    total_credits: int = Field(240, description="Кредитів за всю програму (4 роки)")
    free_choice_credits: int = Field(25, description="Ліміт вільного вибору за всі роки")
    professional_credits: int = Field(54, description="Орієнтир профорієнтовних кредитів")
    min_year_credits: int = Field(57, description="Мінімум кредитів на рік")
    max_directions: int = Field(3, description="Максимум напрямків розвитку")
    max_plan_items: int = Field(30, description="Максимум дисциплін у плані")
    max_item_credits: int = Field(30, description="Максимум кредитів однієї дисципліни")
    academic_year_min: int = Field(2024, description="Мінімальний навчальний рік")
    academic_year_max: int = Field(2030, description="Максимальний навчальний рік")
    max_upload_bytes: int = Field(10 * 1024 * 1024, description="Максимальний розмір документа деканату")


class LoadLevelHours(BaseModel):
    min_hours_per_week: Optional[int] = Field(None, description="Нижня межа годин на тиждень")
    max_hours_per_week: int = Field(..., description="Верхня межа годин на тиждень")


class Features(BaseModel):
    ai_generation: bool = Field(False, description="AI-генерація плану (етап 2)")
    certificate_programs: bool = Field(False, description="Сертифікатні програми (етап 2)")
    saz_sync: bool = Field(False, description="Синхронізація з САЗ (заблоковано, R14)")
    plan_export: bool = Field(True, description="Експорт плану в PDF")


class ConfigResponse(BaseModel):
    api_version: str = Field(API_VERSION, description="Версія API")
    google_client_id: str = Field(..., description="Публічний client_id для входу через Google")
    allowed_email_domain: str = Field("ukma.edu.ua", description="Дозволений домен пошти")
    reviews_url: str = Field(..., description="Посилання «Почитати відгуки»")
    limits: Limits
    load_levels: Dict[str, LoadLevelHours] = Field(..., description="Межі годин на тиждень для рівнів навантаження")
    features: Features


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Публічна конфігурація для фронтенду",
    description="Ліміти нормативів і прапорці функцій. Без автентифікації, відповідь можна кешувати.",
    responses={200: {"description": "Конфігурацію отримано"}},
)
async def get_config(response: Response):
    response.headers["Cache-Control"] = "max-age=300"
    return ConfigResponse(
        google_client_id=os.getenv("GOOGLE_CLIENT_ID", "dev-client-id.apps.googleusercontent.com"),
        reviews_url=os.getenv("REVIEWS_URL", "https://example.ukma.edu.ua/reviews"),
        limits=Limits(),
        load_levels={
            "low": LoadLevelHours(max_hours_per_week=20),
            "medium": LoadLevelHours(min_hours_per_week=20, max_hours_per_week=23),
            "high": LoadLevelHours(min_hours_per_week=23, max_hours_per_week=25),
        },
        features=Features(),
    )
