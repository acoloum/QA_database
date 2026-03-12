import os
import sys

sys.path.append(os.path.dirname(__file__))
from backend.app import app
from backend.extensions import db
from backend.models import ShippingData
from backend.services.tolerance_service import ToleranceService

def backfill():
    with app.app_context():
        print("Fetching shipping data to backfill...")
        records = ShippingData.query.all()
        total = len(records)
        print(f"Total records to parse: {total}")
        
        updated = 0
        tolerance_cache = {}
        
        for i, r in enumerate(records):
            key = (r.material, r.spec, r.vendor_id)
            if key not in tolerance_cache:
                res = ToleranceService.check_tolerance({
                    'material': r.material,
                    'spec': r.spec,
                    'vendor_id': r.vendor_id
                })
                if res.get('found'):
                    tolerance_cache[key] = res.get('tolerances', [])
                else:
                    tolerance_cache[key] = []
                    
            tolerances = tolerance_cache[key]
            
            # calculate
            is_ng = False
            if tolerances:
                try:
                    is_ng = r.compute_is_ng(tolerances)
                except Exception as e:
                    pass
            
            if r.is_ng != is_ng:
                r.is_ng = is_ng
                updated += 1
                
            if i > 0 and i % 500 == 0:
                print(f"Processed {i}/{total}...")
                db.session.commit()
                
        db.session.commit()
        print(f"Finished backfilling is_ng. Updated {updated} records.")

if __name__ == '__main__':
    backfill()
