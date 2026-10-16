from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Stage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z][a-z0-9_]{0,30}$')
    name: str = Field(min_length=2, max_length=50)
    role: str = Field(min_length=2, max_length=60)
    human_minutes: float = Field(gt=0, le=240)
    ai_minutes: float = Field(gt=0, le=60)
    workers: int = Field(ge=1, le=20)
    requires_human: bool = False


DEFAULT_STAGES = [
    Stage(id='intake', name='Receive & classify', role='Intake specialist', human_minutes=8, ai_minutes=1.5, workers=2),
    Stage(id='evidence', name='Prepare evidence', role='Claims analyst', human_minutes=25, ai_minutes=3, workers=3),
    Stage(id='decision', name='Review & decide', role='Claims reviewer', human_minutes=16, ai_minutes=1, workers=2, requires_human=True),
    Stage(id='notify', name='Notify & close', role='Case coordinator', human_minutes=6, ai_minutes=1, workers=1),
]


class ExperimentConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(default='Claims, reimagined', min_length=2, max_length=100)
    days: int = Field(default=20, ge=5, le=40)
    daily_cases: int = Field(default=64, ge=5, le=160)
    work_hours: float = Field(default=8, ge=4, le=10)
    learning_hours: float = Field(default=2, ge=0, le=3)
    complex_share: float = Field(default=.25, ge=0, le=.8)
    ai_speed: float = Field(default=1, ge=.25, le=20)
    exception_rate: float = Field(default=.15, ge=0, le=.6)
    assist_multiplier: float = Field(default=.55, ge=.2, le=1)
    hourly_cost: float = Field(default=30, ge=0, le=250)
    ai_case_cost: float = Field(default=.04, ge=0, le=5)
    sla_hours: float = Field(default=48, ge=1, le=240)
    repetitions: int = Field(default=12, ge=3, le=30)
    seed: int = Field(default=42, ge=0, le=1000000)
    disruption: Literal['none', 'surge', 'outage', 'absence', 'exceptions'] = 'none'
    stages: list[Stage] = Field(default_factory=lambda: [s.model_copy() for s in DEFAULT_STAGES], min_length=2, max_length=8)

    def model_post_init(self, __context):
        ids = [s.id for s in self.stages]
        if len(ids) != len(set(ids)):
            raise ValueError('Stage identifiers must be unique')
        if not any(s.requires_human for s in self.stages):
            raise ValueError('At least one stage must retain human decision authority')


class AIRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=3000)
    config: ExperimentConfig


class BriefRequest(BaseModel):
    experiment_id: str = Field(pattern=r'^[a-f0-9]{32}$')
