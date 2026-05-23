from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.backend.app.auth_db.models import Base, Ticket, TicketStatus, TicketType

# 使用内存数据库进行测试
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

def test_ticket_creation_validation():
    session = TestingSessionLocal()
    # 测试缺少必填字段
    with pytest.raises(Exception):
        ticket = Ticket(ticket_type=TicketType.KEY_REQUEST.value)
        session.add(ticket)
        session.commit()
    session.rollback()
    session.close()

def test_ticket_status_transition():
    session = TestingSessionLocal()
    ticket = Ticket(
        id=300,
        ticket_id="TICKET-300",
        ticket_type=TicketType.KEY_REQUEST.value,
        status=TicketStatus.PENDING.value,
        email="test@example.com",
        phone="13800138000",
        industry="教育",
        organization="某某大学",
        usage_purpose="这是一个用于空间插值与不确定性分析平台测试的用途说明，确保超过十五个汉字。",
        key_type="personal_trial"
    )
    session.add(ticket)
    session.commit()

    # 测试合法流转
    ticket.status = TicketStatus.APPROVED.value
    ticket.processed_by = 1
    ticket.processed_at = datetime.now(timezone.utc)
    session.commit()
    assert ticket.status == TicketStatus.APPROVED.value

    # 测试非法流转 (APPROVED -> PENDING)
    ticket.status = TicketStatus.PENDING.value
    with pytest.raises(ValueError, match="不允许的工单状态流转"):
        session.commit()
    session.rollback()
    session.close()
