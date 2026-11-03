from typing import Annotated

from fastapi import Depends, Header
from sqlmodel import Session

from tracelume.config import get_settings
from tracelume.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def get_actor(x_examiner: Annotated[str | None, Header()] = None) -> str:
    return (x_examiner or get_settings().examiner).strip()[:100] or "examiner"


ActorDep = Annotated[str, Depends(get_actor)]
