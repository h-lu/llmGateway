"""Rule CRUD operations."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import Rule


async def get_all_rules(
    session: AsyncSession,
    enabled_only: bool = False
) -> List[Rule]:
    """Get all rules from the database.
    
    Args:
        session: Database session from FastAPI dependency
        enabled_only: If True, return only enabled rules
        
    Returns:
        List of rules
    """
    query = select(Rule)
    if enabled_only:
        query = query.where(Rule.enabled == True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_rule_by_id(
    session: AsyncSession,
    rule_id: int
) -> Optional[Rule]:
    """Get a rule by ID.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID
        
    Returns:
        Rule object if found, None otherwise
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def create_rule(
    session: AsyncSession,
    pattern: str,
    rule_type: str,
    message: str,
    active_weeks: str = "1-16",
    enabled: bool = True,
    auto_commit: bool = True
) -> Rule:
    """Create a new rule.
    
    Args:
        session: Database session from FastAPI dependency
        pattern: The regex pattern to match
        rule_type: Type of rule (block | guide)
        message: Message to return when rule matches
        active_weeks: Weeks when rule is active (e.g., "1-2" or "3-6")
        enabled: Whether the rule is enabled
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        The created Rule object
    """
    rule = Rule(
        pattern=pattern,
        rule_type=rule_type,
        message=message,
        active_weeks=active_weeks,
        enabled=enabled
    )
    session.add(rule)
    if auto_commit:
        await session.commit()
        await session.refresh(rule)
    return rule


async def update_rule(
    session: AsyncSession,
    rule_id: int,
    auto_commit: bool = True,
    **kwargs
) -> bool:
    """Update a rule by ID.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID to update
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        **kwargs: Fields to update
        
    Returns:
        True if updated successfully, False if rule not found
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        return False
    
    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    
    if auto_commit:
        await session.commit()
    return True


async def delete_rule(
    session: AsyncSession,
    rule_id: int,
    auto_commit: bool = True
) -> bool:
    """Delete a rule by ID.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID to delete
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        True if deleted successfully, False if rule not found
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        return False
    
    await session.delete(rule)
    if auto_commit:
        await session.commit()
    return True


async def toggle_rule_enabled(
    session: AsyncSession,
    rule_id: int,
    auto_commit: bool = True
) -> Optional[bool]:
    """Toggle the enabled status of a rule.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID to toggle
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        New enabled status (True/False), or None if rule not found
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        return None
    
    rule.enabled = not rule.enabled
    if auto_commit:
        await session.commit()
    return rule.enabled
