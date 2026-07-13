"""Result schema for ``kairos doctor``."""

from __future__ import annotations

from pydantic import BaseModel


class DoctorCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class DoctorReport(BaseModel):
    checks: list[DoctorCheck]

    @property
    def healthy(self) -> bool:
        return all(c.ok for c in self.checks)
