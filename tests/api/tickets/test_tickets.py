import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.backend.app.auth_db.models import Base, Ticket, TicketStatus, TicketType
from services.backend.app.api.tickets_api import handle_key_request

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
        ticket_type=TicketType.KEY_REQUEST.value,
        status=TicketStatus.PENDING.value,
        email="test@example.com",
        phone="13800138000",
        industry="教育",
        usage_purpose="教学测试",
        key_type="personal_trial"
    )
    session.add(ticket)
    session.commit()
    
    # 测试合法流转
    ticket.status = TicketStatus.APPROVED.value
    session.commit()
    assert ticket.status == TicketStatus.APPROVED.value
    
    # 测试非法流转 (APPROVED -> PENDING)
    ticket.status = TicketStatus.PENDING.value
    with pytest.raises(ValueError, match="不允许的工单状态流转"):
        session.commit()
    session.rollback()
    session.close()
