from typing import Optional
from sqlmodel import SQLModel, Field, Relationship

class QRItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    data_content: str
    category: str = "General"
    style: str = "cuadrado"
    shape: str = "ninguna"
    color: str = "#111827"
    ref_image: Optional[str] = None
    qr_file: Optional[str] = None
    
    user_id: int = Field(foreign_key="user.id")
    owner: Optional["User"] = Relationship(back_populates="qr_items")