
import sys
import os
from datetime import date

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import app
from backend.services.patrol_service import PatrolService
from backend.extensions import db

def test_add_patrol():
    with app.app_context():
        # Mock payload similar to what PatrolModal sends
        # Case 1: Minimal valid data with empty optional fields
        payload = {
            "檢驗日期": str(date.today()),
            "機台": "1",          # Assuming ID 1 exists. If not, this might fail with FK error.
            "主機手": "1",        # Assuming ID 1 exists
            "檢驗人員": "1",      # Assuming ID 1 exists
            "材質": "TestMaterial",
            "擠壓規格": "TestSpec",
            "客戶名稱": "",       # Empty string (should be handled by _parse_id -> None)
            "原料批號": "Batch123",
            "details": [
                {
                    "group": "1",
                    "item": "外徑",
                    "pos": "前段",
                    "min": "10.5",
                    "max": "10.6"
                }
            ]
        }
        
        print(f"Testing Payload: {payload}")
        
        try:
            # We need valid IDs for FKs. 
            # Let's verify if IDs exist first essentially inside the try block implicitly.
            # But let's check machines first to be sure request is valid.
            from backend.models import Machine, Operator, Inspector
            m = Machine.query.first()
            o = Operator.query.first()
            i = Inspector.query.first()
            
            if not m or not o or not i:
                 print("Cannot run test: Missing basic seed data (Machine/Operator/Inspector)")
                 return

            payload["機台"] = str(m.id)
            payload["主機手"] = str(o.id)
            payload["檢驗人員"] = str(i.id)
            print(f"Updated Payload with real IDs: Machine={m.id}, Op={o.id}, Insp={i.id}")

            new_id = PatrolService.add_patrol(payload)
            print(f"Success! New Patrol ID: {new_id}")
            
            # Clean up?
            # PatrolService.delete_patrol(new_id)

        except Exception as e:
            print("Caught Exception:")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_add_patrol()
