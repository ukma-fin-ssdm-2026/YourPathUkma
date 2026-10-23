from fastapi import APIRouter, Depends

from . import audit, catalog, certificates, sync, users
from .common import require_admin

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"], dependencies=[Depends(require_admin)])
router.include_router(users.router)
router.include_router(catalog.router)
router.include_router(sync.router)
router.include_router(audit.router)
router.include_router(certificates.router)
