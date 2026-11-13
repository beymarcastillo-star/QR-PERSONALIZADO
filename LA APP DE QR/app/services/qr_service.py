import base64
import uuid
from typing import List, Optional

from sqlmodel import Session

from app.core.config import settings
from app.models.qritem import QRItem
from app.repositories.qr_repository import QRRepository
from app.services.qr_renderer import COLOR_POR_DEFECTO, QROptions, cargar_referencia, render_png


class QRService:
    def __init__(self, session: Session):
        self.repo = QRRepository(session)

    def get_user_qrs(self, user_id: int) -> List[QRItem]:
        return self.repo.get_by_user(user_id)

    def create_qr(self, title: str, data_content: str, category: str, user_id: int,
                  style: str = "cuadrado", shape: str = "ninguna", color: str = COLOR_POR_DEFECTO,
                  ref_image: Optional[bytes] = None) -> QRItem:
        """Genera el QR (clásico, con estilo, silueta o imagen de referencia) y lo guarda."""
        opciones = QROptions(style=style, shape=shape, color=color, ref_image=ref_image)
        png = render_png(data_content, opciones)           # valida contenido e imagen antes de guardar nada

        ref_name = None
        if ref_image:
            ref_name = f"refs/{uuid.uuid4().hex}.png"
            cargar_referencia(ref_image).save(settings.ASSETS_DIR / ref_name, format="PNG")
        qr_name = f"{uuid.uuid4().hex}.png"
        (settings.ASSETS_DIR / qr_name).write_bytes(png)

        item = QRItem(title=title, data_content=data_content, category=category, user_id=user_id,
                      style=style, shape=shape, color=color, ref_image=ref_name, qr_file=qr_name)
        return self.repo.create(item)

    def remove_qr(self, item_id: int) -> None:
        item = self.repo.get_by_id(item_id)
        if item:
            for nombre in (item.qr_file, item.ref_image):
                if nombre:
                    (settings.ASSETS_DIR / nombre).unlink(missing_ok=True)
        self.repo.delete(item_id)

    @staticmethod
    def preview_base64(data: str, style: str = "cuadrado", shape: str = "ninguna",
                       color: str = COLOR_POR_DEFECTO, ref_image: Optional[bytes] = None) -> str:
        """Vista previa sin guardar nada."""
        png = render_png(data, QROptions(style=style, shape=shape, color=color, ref_image=ref_image))
        return "data:image/png;base64," + base64.b64encode(png).decode("utf-8")

    @staticmethod
    def generate_qr_base64(data: str) -> str:
        """QR clásico (se usa para los registros creados antes de la personalización)."""
        return QRService.preview_base64(data)
