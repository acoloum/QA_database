"""植入預設角色。執行方式：cd C:\\QC_Database && python -m backend.seeds.seed_roles"""
import sys
import os

# 確保專案根目錄在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.app import app
from backend.extensions import db
from backend.models import Role

ROLES = [
    {
        'code': 'inspector', 'name': '檢驗員',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit_own': True, 'ncmr.view': True,
            'capa.view': True, 'rework.view': True,
            'shipping.create': True, 'shipping.edit_own': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit_own': True, 'patrol.view': True,
            'pyrometry.edit': True, 'pyrometry.view': True,
            'task.create': True, 'task.edit': True,
        }
    },
    {
        'code': 'qa_supervisor', 'name': 'QA主管',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.view': True,
            'ncmr.disposition': True,
            'capa.create': True, 'capa.edit': True, 'capa.view': True,
            'rework.create': True, 'rework.approve': True, 'rework.view': True,
            'complaint.edit': True, 'complaint.view': True,
            'shipping.create': True, 'shipping.edit': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit': True, 'patrol.view': True,
            'pyrometry.edit': True, 'pyrometry.view': True,
            'task.create': True, 'task.edit': True,
        }
    },
    {
        'code': 'qc_manager', 'name': '品管經理',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.delete': True, 'ncmr.view': True,
            'ncmr.disposition': True,
            'capa.create': True, 'capa.edit': True, 'capa.close': True, 'capa.view': True,
            'rework.create': True, 'rework.approve': True, 'rework.delete': True, 'rework.view': True,
            'complaint.create': True, 'complaint.edit': True, 'complaint.delete': True, 'complaint.view': True,
            'vendor.manage': True, 'report.view': True,
            'tolerance.manage': True,
            'shipping.create': True, 'shipping.edit': True, 'shipping.delete': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit': True, 'patrol.delete': True, 'patrol.view': True,
            'pyrometry.edit': True, 'pyrometry.delete': True, 'pyrometry.view': True,
            'task.create': True, 'task.edit': True, 'task.delete': True,
        }
    },
    {
        'code': 'admin', 'name': '系統管理員',
        'permissions': {
            'ncmr.create': True, 'ncmr.edit': True, 'ncmr.delete': True, 'ncmr.view': True,
            'ncmr.disposition': True,
            'capa.create': True, 'capa.edit': True, 'capa.close': True, 'capa.view': True,
            'rework.create': True, 'rework.approve': True, 'rework.delete': True, 'rework.view': True,
            'complaint.create': True, 'complaint.edit': True, 'complaint.delete': True, 'complaint.view': True,
            'vendor.manage': True, 'report.view': True,
            'tolerance.manage': True,
            'shipping.create': True, 'shipping.edit': True, 'shipping.delete': True, 'shipping.view': True,
            'patrol.create': True, 'patrol.edit': True, 'patrol.delete': True, 'patrol.view': True,
            'pyrometry.edit': True, 'pyrometry.delete': True, 'pyrometry.view': True,
            'task.create': True, 'task.edit': True, 'task.delete': True,
            'user.manage': True,
        }
    },
]


def seed():
    with app.app_context():
        for r in ROLES:
            existing = Role.query.filter_by(code=r['code']).first()
            if existing:
                existing.name = r['name']
                existing.permissions = r['permissions']
            else:
                db.session.add(Role(**r))
        db.session.commit()
        print(f'已植入 {len(ROLES)} 個角色')


if __name__ == '__main__':
    seed()
