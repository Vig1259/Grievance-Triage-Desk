from pydantic import BaseModel, Field
from typing import Literal

class StaffUpdate(BaseModel):
    department: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["pending", "solved", "rejected"] | None = None
    resolution_note: str | None = Field(default=None, max_length=2000)
