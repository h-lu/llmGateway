from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models.
    
    Inherits from AsyncAttrs to support asynchronous attribute loading
    in SQLAlchemy 2.0 async ORM.
    """
    pass
