from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import configure_mappers

from app.models.base import Base
from app.models.event import Event
from app.models.order import Order
from app.models.ticket import Ticket, TicketType
from app.models.user import User
from app.models.enums import OrderStatus
from app.models.ticket import TicketStatus
from app.models.user import UserRole
from app.schemas.event import EventCreate, EventResponse
from app.schemas.order import OrderDetailResponse, ReservationResponse
from app.schemas.ticket import TicketTypeCreate, TicketTypeResponse
from app.schemas.user import UserResponse


def test_all_orm_mappers_configure():
    configure_mappers()
    assert {"users", "events", "orders", "ticket_types", "tickets"} <= set(Base.metadata.tables)


def test_order_contains_nullable_historical_snapshots_and_ticket_type_fk():
    order = Order.__table__
    assert order.c.ticket_type_id.nullable
    assert order.c.quantity.nullable
    assert order.c.unit_price.nullable
    assert order.c.currency.nullable
    assert order.c.expires_at.nullable
    assert any(fk.target_fullname == "ticket_types.id" for fk in order.c.ticket_type_id.foreign_keys)


def test_ticket_type_schema_accepts_canonical_and_legacy_capacity_names():
    canonical = TicketTypeCreate.model_validate({"name": "General", "price": "12.50", "capacity": 5})
    legacy = TicketTypeCreate.model_validate({"name": "General", "price": "12.50", "quantity_avaialable": 5})
    assert canonical.capacity == legacy.capacity == 5
    event = EventCreate.model_validate({
        "title": "Show", "location": "Hall", "start_time": "2030-01-01T10:00:00Z",
        "end_time": "2030-01-01T12:00:00Z",
    })
    assert isinstance(event.end_time, datetime)


def test_orm_instances_validate_against_response_schemas():
    now = datetime.now(UTC)
    uid, eid, tid, oid = uuid4(), uuid4(), uuid4(), uuid4()
    event = Event(id=eid, title="Show", location="Hall", start_time=now, end_time=now, organizer_id=uid,
                  created_at=now, updated_at=now, is_published=False, ticket_types=[])
    event.ticket_types = [TicketType(id=tid, event_id=eid, name="General", description=None,
                                     price=Decimal("12.50"), quantity_available=5, quantity_reserved=0,
                                     quantity_sold=0, is_active=True, created_at=now, updated_at=now, tickets=[], orders=[])]
    event_response = EventResponse.model_validate(event)
    type_response = TicketTypeResponse.model_validate(event.ticket_types[0])
    assert event_response.ticket_types[0].capacity == type_response.capacity == 5
    assert type_response.model_dump()["capacity"] == 5

    order = Order(id=oid, user_id=uid, ticket_type_id=tid, quantity=2, unit_price=Decimal("12.50"),
                  currency="KES", expires_at=now, total_amount=Decimal("25.00"), status=OrderStatus.PENDING,
                  payment_reference="ref", created_at=now, updated_at=now, tickets=[])
    assert OrderDetailResponse.model_validate(order).quantity == 2
    assert ReservationResponse.model_validate(order).order_id == oid

    user = User(id=uid, email="a@example.com", hashed_password="hash", full_name="A",
                role=UserRole.ATTENDEE, is_active=True, is_superuser=False, created_at=now, updated_at=now,
                organizer_profile=None)
    assert UserResponse.model_validate(user).role is UserRole.ATTENDEE
    assert TicketStatus.EXPIRED.value == "EXPIRED"


def test_legacy_nulls_remain_readable_in_order_and_ticket_type_responses():
    now = datetime.now(UTC)
    uid, oid, tid = uuid4(), uuid4(), uuid4()
    order = Order(
        id=oid, user_id=uid, ticket_type_id=None, quantity=None, unit_price=None,
        currency=None, expires_at=None, total_amount=Decimal("20.00"),
        status=OrderStatus.SUCCESSFUL, payment_reference="legacy",
        created_at=now, updated_at=now, tickets=[],
    )
    response = OrderDetailResponse.model_validate(order)
    assert response.quantity is None and response.expires_at is None

    ticket_type = TicketType(
        id=tid, event_id=uuid4(), name="Legacy", description=None,
        price=Decimal("20.00"), quantity_available=10, quantity_reserved=None,
        quantity_sold=None, is_active=True, created_at=now, updated_at=now,
        tickets=[], orders=[],
    )
    assert TicketTypeResponse.model_validate(ticket_type).quantity_sold is None
    assert ticket_type.remaining_capacity is None

    event = Event(
        id=uuid4(), title="Legacy", location="Hall", start_time=now, end_time=now,
        organizer_id=uid, is_published=None, created_at=now, updated_at=now,
        ticket_types=[],
    )
    assert EventResponse.model_validate(event).is_published is None


def test_postgresql_enum_names_and_stored_labels_match_models():
    assert Order.status.type.name == "orderstatus"
    assert set(Order.status.type.enums) == {status.name for status in OrderStatus}
    assert Ticket.status.type.name == "ticketstatus"
    assert set(Ticket.status.type.enums) == {status.name for status in TicketStatus}
    assert User.role.type.name == "user_role_enum"
    assert set(User.role.type.enums) == {role.value for role in UserRole}
    assert Event.__table__.c.end_time.type.__class__.__name__ == "DateTime"
