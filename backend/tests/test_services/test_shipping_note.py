"""出貨檢驗備註欄位：儲存、回傳、清空與長度上限。"""
import pytest

from backend.models import ShippingData
from backend.services.shipping_service import ShippingService


def _base_payload(note=None):
    payload = {
        '檢驗日期': '2026-07-09',
        '檢驗人員姓名': 'Test Inspector',
        '廠商中文名稱': 'Test Vendor',
        '檢驗規格': '10*2',
        '材質': '6061',
        '訂單號碼': 'SO-1',
        '組數': 1,
        'measurements': {'1': {'外徑': {'value_min': 9.8, 'value_max': 10.2}}},
    }
    if note is not None:
        payload['備註'] = note
    return payload


def test_note_saved_and_returned(db_session, setup_data):
    """備註寫入後可由單筆查詢原樣取回，前後空白會被去除"""
    ShippingService.save_data(_base_payload('  外觀有輕微刮痕，經客戶同意特採  '))

    record = ShippingData.query.one()
    assert record.note == '外觀有輕微刮痕，經客戶同意特採'
    assert ShippingService.get_by_id(record.id)['備註'] == '外觀有輕微刮痕，經客戶同意特採'


@pytest.mark.parametrize('note', [None, '', '   '])
def test_blank_note_stored_as_null(db_session, setup_data, note):
    """未填或全空白的備註一律存 None，回傳空字串"""
    ShippingService.save_data(_base_payload(note))

    record = ShippingData.query.one()
    assert record.note is None
    assert ShippingService.get_by_id(record.id)['備註'] == ''


def test_note_can_be_cleared_on_update(db_session, setup_data):
    """更新時清空備註應真的寫回 None，而非保留舊值"""
    ShippingService.save_data(_base_payload('先前的說明'))
    record = ShippingData.query.one()

    update_payload = _base_payload(None)
    update_payload['識別碼'] = record.id
    ShippingService.save_data(update_payload, is_update=True)

    assert db_session.get(ShippingData, record.id).note is None


def test_note_length_limit(db_session, setup_data):
    """超過上限的備註應被拒絕，避免單筆寫入無界長度的文字"""
    over_limit = '長' * (ShippingService.NOTE_MAX_LENGTH + 1)
    with pytest.raises(ValueError, match='備註長度'):
        ShippingService.save_data(_base_payload(over_limit))
