import os
import sys

# 添加项目根目录到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.backend.app.auth_db.models import Ticket, Company
from services.backend.app.auth_db.session import get_auth_db_session

def migrate():
    db = next(get_auth_db_session())
    try:
        tickets = db.query(Ticket).filter(Ticket.company_id == None).all()
        print(f"Found {len(tickets)} tickets to migrate.")
        
        migrated_count = 0
        for ticket in tickets:
            # 1. 尝试按单位名称匹配
            company = db.query(Company).filter(Company.name == ticket.organization).first()
            
            if not company:
                # 2. 尝试按邮箱域名匹配 (可选，这里仅做单位名称匹配作为演示)
                # 实际生产中可以有域名到公司的映射表
                pass
            
            if company:
                ticket.company_id = company.id
                migrated_count += 1
        
        db.commit()
        print(f"Successfully migrated {migrated_count} tickets.")
    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
