from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, SessionDep
from app.models.event import Event as EventModel
from app.models.ticket import TicketType as TicketTypeModel
from app.schemas.event import (
    EventCreate,
    EventResponse,
    EventUpdate,
)
from app.schemas.ticket import (
    TicketTypeCreate,
    TicketTypeResponse,
    TicketTypeUpdate,
)

router = APIRouter()

def _is_admin(user: Any) -> bool:
    return getattr(user, "role", None) in ("admin", "superuser")

def _is_authorized_organizer_or_admin(event: EventModel, user: Any) -> bool:
    """
    Helper to check if user owns the event or has admin role.
    """
    is_admin = getattr(user, "role", None) in ("admin", "superuser")
    return event.organizer_id == user.id or is_admin

@router.get("/", response_model=list[EventResponse], summary="List events")
async def list_events(
    db: SessionDep,
    current_user: CurrentUser | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    published_only: bool = True,
) -> Any:
    """
    List events with optional pagination.
    """
    stmt = select(EventModel).options(selectinload(EventModel.ticket_types))
    if not published_only:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view draft events",
            )
        if not _is_admin(current_user):
            # Non-admins only see their own drafts
            stmt = stmt.where(
                (EventModel.is_published.is_(True)) | (EventModel.organizer_id == current_user.id)
            )
    else:
        stmt = stmt.where(EventModel.is_published.is_(True))

    stmt = stmt.offset(skip).limit(limit).order_by(EventModel.start_time.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_event(
    event_in: EventCreate,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Create a new event alongside initial ticket tiers.
    """
    event = EventModel(
        title=event_in.title,
        description=event_in.description,
        location=event_in.location,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
        organizer_id=current_user.id,
    )
    db.add(event)
    await db.flush()

    for tt in event_in.ticket_types:
        ticket_type = TicketTypeModel(
            event_id=event.id,
            name=tt.name,
            description=tt.description,
            price=tt.price,
            capacity=tt.capacity if hasattr(tt, "capacity") else getattr(tt, "quantity_available", 0),
        )
        db.add(ticket_type)

    await db.commit()

    # Reload with ticket_types relation
    stmt = select(EventModel).options(selectinload(EventModel.ticket_types)).where(EventModel.id == event.id)
    result = await db.execute(stmt)
    return result.scalar_one()

@router.get(
    "/{event_id}",
    response_model=EventResponse
)
async def get_event(
    event_id: UUID,
    db: SessionDep,
) -> Any:
    """
    Retrieve event details including active ticket tiers.
    """
    stmt = select(EventModel).options(selectinload(EventModel.ticket_types)).where(EventModel.id == event_id)
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )
    return event

@router.patch(
    "/{event_id}",
    response_model=EventResponse,
)
async def update_event(
    event_id: UUID,
    event_in: EventUpdate,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Update event attributes. Restricted to the organizer or superusers.
    """
    stmt = select(EventModel).options(selectinload(EventModel.ticket_types)).where(EventModel.id == event_id)
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )

    if not _is_authorized_organizer_or_admin(event, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to edit this event"
        )
    update_data = event_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    db.add(event)
    await db.commit()

@router.post(
    "/{event_id}/ticket-types",
    response_model=TicketTypeResponse
)
async def add_ticket_type(
    event_id: UUID,
    tt_in: TicketTypeCreate,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Add a new ticket tier to an existing event.
    """
    event = await db.get(EventModel, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )
    if not _is_authorized_organizer_or_admin(event, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    ticket_type = TicketTypeModel(
        event_id=event.id,
        **tt_in.model_dump()
    )
    db.add(ticket_type)
    await db.commit()
    await db.refresh(ticket_type)
    return ticket_type

@router.patch(
    "/{event_id}/ticket-types/{ticket_type_id}",
    response_model=TicketTypeResponse
)
async def update_ticket_type(
    event_id: UUID,
    ticket_type_id: UUID,
    tt_in: TicketTypeUpdate,
    db: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Update an existing ticket tier's price, capacity, or details.
    """
    event = await db.get(EventModel, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found."
        )
    if not _is_authorized_organizer_or_admin(event, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    ticket_type = await db.get(TicketTypeModel, ticket_type_id)
    if not ticket_type or ticket_type.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket type not found for this event."
        )
    update_data = tt_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(ticket_type, field):
            setattr(ticket_type, field, value)

    db.add(ticket_type)
    await db.commit()
    await db.refresh(ticket_type)
    return ticket_type