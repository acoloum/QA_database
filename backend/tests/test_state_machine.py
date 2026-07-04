import pytest
from backend.utils import validate_status_transition

def test_ncmr_valid_transition():
    # 使用實際的 NCMR 狀態名稱：待處理 → 矯正中 → 矯正完成 → 已結案
    validate_status_transition('NCMR', '待處理', '矯正中')
    validate_status_transition('NCMR', '矯正中', '矯正完成')
    validate_status_transition('NCMR', '矯正完成', '已結案')
    validate_status_transition('NCMR', '待處理', '已結案')
    validate_status_transition('NCMR', '矯正中', '已結案')

def test_ncmr_legacy_car_status_transition():
    # 「CAR處理中」是舊版流程遺留的狀態值，語意等同「矯正中」，須能繼續轉移
    validate_status_transition('NCMR', 'CAR處理中', '矯正完成')
    validate_status_transition('NCMR', 'CAR處理中', '已結案')

def test_ncmr_invalid_transition():
    with pytest.raises(ValueError, match='非法狀態轉移'):
        validate_status_transition('NCMR', '已結案', '待處理')
    with pytest.raises(ValueError, match='非法狀態轉移'):
        validate_status_transition('NCMR', '矯正完成', '矯正中')

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
