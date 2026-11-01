"""
Роздача зібраного фронтенду (`frontend/dist`) тим самим процесом, що й API.

Навіщо: refresh-cookie видається з SameSite=strict, Secure і шляхом /api/v1/auth, а фронтенд ходить на відносний
`/api/v1`. На одному origin усе працює без CORS і без окремого nginx, тож у Docker достатньо одного контейнера.

Режим вмикається, лише якщо є `index.html` у теці з `FRONTEND_DIST` (за замовчуванням `frontend/dist`). У
розробці й тестах теки немає, тож нічого не змінюється: фронтенд там роздає Vite.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_frontend_site.py і збірка
Docker-образу з запуском контейнера.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class SinglePageApp(StaticFiles):
    """
    Файли зі збірки віддаються як є, а будь-який інший шлях (наприклад, `/path/create`) отримує `index.html`:
    маршрутизацію далі робить react-router у браузері. Шляхи `/api/...` сюди не потрапляють як сторінки:
    невідомий API-маршрут лишається справжньою 404, а не HTML.
    """

    async def get_response(self, path: str, scope):
        # Starlette нормалізує шлях через os.path: на Windows це `api\v1\x`, тож розділювачі зводимо до «/».
        normalized = path.replace("\\", "/")
        if normalized == "api" or normalized.startswith("api/"):
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or normalized.startswith("assets/"):
                # Відсутній файл збірки (наприклад, застарілий хеш у кеші браузера) це справжня 404, а не HTML
                raise
            return await super().get_response("index.html", scope)


def frontend_dist() -> Optional[Path]:
    """Тека зі збіркою фронтенду або None, якщо збірки немає."""
    configured = os.getenv("FRONTEND_DIST", "").strip()
    dist = Path(configured) if configured else DEFAULT_DIST
    return dist if (dist / "index.html").is_file() else None


def mount_frontend(app: FastAPI, dist: Optional[Path] = None) -> bool:
    """
    Підключає збірку фронтенду в корінь. Викликати ПІСЛЯ реєстрації всіх API-маршрутів: маршрути застосунку
    мають пріоритет над змонтованим застосунком, а він обробляє лише решту шляхів.
    """
    dist = dist or frontend_dist()
    if dist is None:
        return False
    app.mount("/", SinglePageApp(directory=str(dist)), name="frontend")
    return True
