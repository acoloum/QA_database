import pytest
from backend.utils import validate_status_transition

def test_ncmr_valid_transition():
    # 不應拋錯
    validate_status_transition('NCMR', '新建', '處理中')
    validate_status_transition('NCMR', '處理中', '已驗證')
    validate_status_transition('NCMR', '已驗證', '已結案')
    validate_status_transition('NCMR', '新建', '已結案')

def test_ncmr_invalid_transition():
    with pytest.raises(ValueError, match='非法狀態轉移'):
        validate_status_transition('NCMR', '已結案', '新建')
    with pytest.raises(ValueError, match='非法狀態轉移'):
        validate_status_transition('NCMR', '已驗證', '新建')

def test_capa_valid_transition():
    validate_status_transition('CAPA', '進行中', '已結案')

def test_capa_invalid_transition():
    with pytest.raises(ValueError):
        validate_status_transition('CAPA', '已結案', '進行中')

def test_rework_valid_transitions():
    validate_status_transition('重工', '申請中', '執行中')
    validate_status_transition('重工', '執行中', '已完成')
    validate_status_transition('重工', '已完成', '已結案')
    validate_status_transition('重工', '申請中', '撤銷')

def test_rework_invalid_transition():
    with pytest.raises(ValueError):
        validate_status_transition('重工', '已結案', '申請中')
