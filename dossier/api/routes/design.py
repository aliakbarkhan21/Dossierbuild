"""The design, and the menu of everything it can be set to.

``/options`` exists so the frontend never hardcodes a template name or an
accent hex. The curated lists live in ``render/design.py``; adding a template
there should put a card in the gallery without a line of frontend work.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ...render import design as dz

router = APIRouter(prefix="/api/design", tags=["design"])


class Option(BaseModel):
    key: str
    name: str
    blurb: str = ""


class TemplateOut(Option):
    ats: bool
    columns: str
    best_for: str
    photo: bool


class PageOut(Option):
    width_mm: float
    height_mm: float


class AccentOut(Option):
    hex: str


class LookOut(Option):
    values: dict[str, object]


class ScaleOut(BaseModel):
    steps: list[int]
    base_pt: float


class Options(BaseModel):
    templates: list[TemplateOut]
    accents: list[AccentOut]
    fonts: list[Option]
    pages: list[PageOut]
    margins: list[Option]
    leading: list[Option]
    looks: list[LookOut]
    sections: list[Option]
    scale: ScaleOut


@router.get("", response_model=dz.Design)
def read_design() -> dz.Design:
    return dz.load_design()


@router.put("", response_model=dz.Design)
def write_design(incoming: dz.Design) -> dz.Design:
    """Store the design. Every field self-repairs, so this cannot 422."""
    dz.save_design(incoming)
    return incoming


@router.get("/options", response_model=Options)
def options() -> Options:
    from ...render.html import BASE_PT

    return Options(
        templates=[
            TemplateOut(
                key=t.key, name=t.name, blurb=t.blurb, ats=t.ats,
                columns=t.columns, best_for=t.best_for, photo=t.photo,
            )
            for t in dz.TEMPLATES.values()
        ],
        accents=[
            AccentOut(key=key, name=name, hex=value)
            for key, (name, value) in dz.ACCENTS.items()
        ],
        fonts=[
            Option(key=p.key, name=p.name, blurb=p.blurb) for p in dz.PAIRINGS.values()
        ],
        pages=[
            PageOut(key=p.key, name=p.name, width_mm=p.width_mm, height_mm=p.height_mm)
            for p in dz.PAGES.values()
        ],
        margins=[
            Option(key=key, name=name, blurb=f"{mm:.0f}mm")
            for key, (name, mm) in dz.MARGINS.items()
        ],
        leading=[
            Option(key=key, name=name, blurb=f"{value:g}")
            for key, (name, value) in dz.LEADING.items()
        ],
        looks=[
            LookOut(key=l.key, name=l.name, blurb=l.blurb, values=dict(l.values))
            for l in dz.LOOKS
        ],
        sections=[Option(key=key, name=label) for key, label in dz.RESUME_SECTIONS],
        scale=ScaleOut(steps=[92, 96, 100, 104, 108], base_pt=BASE_PT),
    )
