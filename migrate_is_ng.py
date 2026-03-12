import os
import sys
sys.path.append(os.path.dirname(__file__))

from backend.app import app
from backend.extensions import db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE "出貨檢驗數據" ADD COLUMN "是否超差" BOOLEAN DEFAULT FALSE;'))
        db.session.commit()
        print("Column added successfully or it already exists.")
    except Exception as e:
        db.session.rollback()
        print("Error during migration:", e)
