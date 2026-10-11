"""SQLAlchemy models for Document Assistant.

Import ``Base.metadata`` from here in Alembic's ``env.py`` so autogenerate
sees every table.
"""

from app.database.models.base import Base
from app.database.models.chat_messages import ChatMessage
from app.database.models.chat_threads import ChatThread
from app.database.models.document_chunks import DocumentChunk
from app.database.models.message_citations import MessageCitation
from app.database.models.source_documents import SourceDocument
from app.database.models.users import Profile

__all__ = [
    "Base",
    "ChatMessage",
    "ChatThread",
    "DocumentChunk",
    "MessageCitation",
    "Profile",
    "SourceDocument",
]
