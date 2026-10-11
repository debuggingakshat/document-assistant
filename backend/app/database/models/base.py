from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models.

    Using MappedAsDataclass so model classes get __init__, __repr__, etc. for
    free without manual boilerplate.
    """

