from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from beaver.db.session import get_session
from beaver.services.llm import get_llm
from beaver.services.knowledge import get_knowledge
from beaver.services.embeddings import get_embeddings

DBSession = Annotated[AsyncSession, Depends(get_session)]
LLM = Annotated[object, Depends(get_llm)]
Embeddings = Annotated[object, Depends(get_embeddings)]
Knowledge = Annotated[object, Depends(get_knowledge)]
