"""CARA 服務 — 對外矯正措施要求，簡化 5 步驟（D2/D3/D4/D6/D8），僅限 IQC 來料異常"""
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from ..extensions import db
from ..models import CARARecord, NCMR

# IQC 來料類型（NCMR.source 欄位值）
IQC_SOURCES = {'IQC', '來料', '進料', '進料檢驗', 'incoming', 'Incoming'}

# CARA 簡化步驟
CARA_STEPS = ['D2', 'D3', 'D4', 'D6', 'D8']


class CARAService:

    # ── 序號產生 ─────────────────────────────────────────────
    @staticmethod
    def _gen_no() -> str:
        today = date.today().strftime('%Y%m%d')
        count = CARARecord.query.filter(
            CARARecord.cara_no.like(f'CARA-{today}-%')
        ).count()
        return f'CARA-{today}-{count + 1:03d}'

    # ── 開立 CARA ────────────────────────────────────────────
    @staticmethod
    def create(data: Dict[str, Any]) -> Dict[str, Any]:
        """從 IQC 來料異常 NCMR 開立 CARA

        必填：ncmr_id
        選填：d1_leader_id（承辦人員）
        """
        ncmr_id = data.get('ncmr_id')
        if not ncmr_id:
            raise ValueError('CARA 必須關聯 NCMR')

        ncmr = NCMR.query.get(ncmr_id)
        if not ncmr:
            raise ValueError(f'NCMR #{ncmr_id} 不存在')

        # 僅允許 IQC 來料異常開立 CARA
        if ncmr.source not in IQC_SOURCES:
            raise ValueError(
                f'CARA 僅限來料品質異常（IQC）使用，此 NCMR 來源為「{ncmr.source}」'
            )

        # 避免重複開立
        exist = CARARecord.query.filter_by(ncmr_id=ncmr_id).first()
        if exist:
            raise ValueError(f'此 NCMR 已開立 CARA（{exist.cara_no}），不可重複開立')

        cara = CARARecord(
            cara_no      = CARAService._gen_no(),
            ncmr_id      = ncmr_id,
            vendor       = ncmr.vendor,
            status       = '進行中',
            d1_leader_id = data.get('d1_leader_id'),
        )
        db.session.add(cara)
        db.session.commit()
        return CARAService._to_dict(cara)

    # ── 查詢列表 ─────────────────────────────────────────────
    @staticmethod
    def list_caras(
        status: Optional[str] = None,
        vendor: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        q = CARARecord.query
        if status:
            q = q.filter_by(status=status)
        if vendor:
            q = q.filter(CARARecord.vendor.ilike(f'%{vendor}%'))
        if date_from:
            q = q.filter(CARARecord.created_at >= date_from + 'T00:00:00')
        if date_to:
            q = q.filter(CARARecord.created_at <= date_to + 'T23:59:59')

        total = q.count()
        items = q.order_by(CARARecord.id.desc())\
                  .offset((page - 1) * per_page).limit(per_page).all()
        return {
            'data':     [CARAService._to_list_dict(c) for c in items],
            'total':    total,
            'page':     page,
            'per_page': per_page,
        }

    # ── 取得明細 ─────────────────────────────────────────────
    @staticmethod
    def get_detail(cara_id: int) -> Optional[Dict[str, Any]]:
        c = CARARecord.query.get(cara_id)
        return CARAService._to_dict(c) if c else None

    # ── 步驟更新 ─────────────────────────────────────────────
    @staticmethod
    def update_step(cara_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """更新 D2/D3/D4/D6/D8 任一步驟欄位"""
        c = CARARecord.query.get(cara_id)
        if not c:
            raise ValueError('CARA 不存在')
        if c.status == '已結案':
            raise ValueError('已結案的 CARA 不可修改')

        # D2
        for fld in ('what', 'where', 'when', 'who', 'why', 'how', 'how_many'):
            _setif(c, f'd2_{fld}', data, f'D2_{fld}')

        # D3
        _setif(c, 'd3_action',        data, 'D3_action')
        _setif(c, 'd3_effective_date', data, 'D3_effective_date', _parse_date)
        _setif(c, 'd3_verification',   data, 'D3_verification')

        # D4
        _setif(c, 'd4_tool',       data, 'D4_tool')
        _setif(c, 'd4_five_why',   data, 'D4_five_why')
        _setif(c, 'd4_fishbone',   data, 'D4_fishbone')
        _setif(c, 'd4_root_cause', data, 'D4_root_cause')

        # D6
        if 'D6_verified' in data:
            c.d6_verified = bool(data['D6_verified'])
        _setif(c, 'd6_implement_date', data, 'D6_implement_date', _parse_date)
        _setif(c, 'd6_result',         data, 'D6_result')

        # D8 資訊（由 close() 正式寫入，此處允許草稿）
        _setif(c, 'd8_confirmation', data, 'D8_confirmation')

        # 承辦人
        _setif(c, 'd1_leader_id', data, 'D1_leader_id')

        db.session.commit()
        return CARAService._to_dict(c)

    # ── 結案 ─────────────────────────────────────────────────
    @staticmethod
    def close(cara_id: int, confirmation: str) -> Dict[str, Any]:
        """D8 結案（需 D6 verified）"""
        c = CARARecord.query.get(cara_id)
        if not c:
            raise ValueError('CARA 不存在')
        if c.status == '已結案':
            raise ValueError('此 CARA 已結案')
        if not c.d6_verified:
            raise ValueError('D6 驗證尚未通過，無法結案')
        if not confirmation or not confirmation.strip():
            raise ValueError('D8 結案確認聲明為必填')

        c.status          = '已結案'
        c.d8_confirmation = confirmation
        c.d8_close_date   = date.today()
        c.closed_at       = datetime.utcnow()
        db.session.commit()
        return CARAService._to_dict(c)

    # ── 刪除 ─────────────────────────────────────────────────
    @staticmethod
    def delete(cara_id: int) -> bool:
        c = CARARecord.query.get(cara_id)
        if not c:
            raise ValueError('CARA 不存在')
        if c.status == '已結案':
            raise ValueError('已結案的 CARA 不可刪除')
        db.session.delete(c)
        db.session.commit()
        return True

    # ── 進度計算 ─────────────────────────────────────────────
    @staticmethod
    def _calc_progress(c: CARARecord) -> Dict[str, Any]:
        status = {}
        status['D2'] = bool(c.d2_what or c.d2)
        status['D3'] = bool(c.d3_action or c.d3)
        status['D4'] = bool(c.d4_root_cause or c.d4)
        status['D6'] = bool(c.d6_verified)
        status['D8'] = bool(c.d8_confirmation)
        done = sum(1 for v in status.values() if v)
        return {
            'total_steps':     len(CARA_STEPS),
            'completed_steps': done,
            'percent':         round(done / len(CARA_STEPS) * 100),
            'step_status':     status,
        }

    # ── 序列化（列表用）─────────────────────────────────────
    @staticmethod
    def _to_list_dict(c: CARARecord) -> Dict[str, Any]:
        n = c.ncmr
        return {
            'id':       c.id,
            'no':       c.cara_no,
            'vendor':   c.vendor,
            'status':   c.status,
            'ncmr_id':  c.ncmr_id,
            'ncmr_no':  n.ncmr_number if n else None,
            'source':   n.source if n else None,
            'material': n.material if n else None,
            'product':  n.product_info if n else None,
            'owner':    c.leader.name if c.leader else None,
            'progress_percent': CARAService._calc_progress(c)['percent'],
            'created_at': c.created_at.isoformat() if c.created_at else None,
        }

    # ── 序列化（明細用）─────────────────────────────────────
    @staticmethod
    def _to_dict(c: CARARecord) -> Dict[str, Any]:
        progress = CARAService._calc_progress(c)
        # 取得 NCMR 資訊
        ncmr_info = {}
        if c.ncmr and c.ncmr_id:
            n = c.ncmr
            ncmr_info = {
                'ncmr_no':  n.ncmr_number,
                'vendor':   n.vendor,
                'material': n.material,
                'defect':   n.description,
                'source':   n.source,
            }

        return {
            'id':       c.id,
            'no':       c.cara_no,
            'vendor':   c.vendor,
            'status':   c.status,
            'ncmr_id':  c.ncmr_id,
            'ncmr_info': ncmr_info,
            'progress': progress,
            # D1
            'D1_leader_id':   c.d1_leader_id,
            'D1_leader_name': c.leader.name if c.leader else None,
            # D2
            'D2_what':     c.d2_what, 'D2_where': c.d2_where,
            'D2_when':     c.d2_when, 'D2_who':   c.d2_who,
            'D2_why':      c.d2_why,  'D2_how':   c.d2_how,
            'D2_how_many': c.d2_how_many,
            # D3
            'D3_action':         c.d3_action,
            'D3_effective_date': c.d3_effective_date.isoformat() if c.d3_effective_date else None,
            'D3_verification':   c.d3_verification,
            # D4
            'D4_tool':       c.d4_tool,
            'D4_five_why':   c.d4_five_why,
            'D4_fishbone':   c.d4_fishbone,
            'D4_root_cause': c.d4_root_cause,
            # D6
            'D6_implement_date': c.d6_implement_date.isoformat() if c.d6_implement_date else None,
            'D6_result':         c.d6_result,
            'D6_verified':       c.d6_verified,
            # D8
            'D8_close_date':   c.d8_close_date.isoformat() if c.d8_close_date else None,
            'D8_confirmation': c.d8_confirmation,
            # 時間戳
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'closed_at':  c.closed_at.isoformat() if c.closed_at else None,
        }


# ── 工具函數 ─────────────────────────────────────────────────
def _setif(obj, attr: str, data: dict, key: str, transform=None) -> None:
    if key in data:
        val = data[key]
        if transform and val is not None:
            val = transform(val)
        setattr(obj, attr, val)


def _parse_date(val) -> Optional[date]:
    if not val:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))
