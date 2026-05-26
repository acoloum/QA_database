
from datetime import date, datetime, timezone
from .extensions import db
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

class User(db.Model):
    __tablename__ = '使用者'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    username = db.Column('使用者名稱', db.String, unique=True, nullable=False)
    password = db.Column('密碼', db.String, nullable=False)
    is_active = db.Column('是否啟用', db.Boolean, default=True)
    role = db.Column('角色', db.String(20), nullable=False, default='user', server_default='user')
    created_at = db.Column('建立時間', db.DateTime(timezone=True), nullable=True,
                           default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<User {self.username}>'

class Inspector(db.Model):
    __tablename__ = '品管人員'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    name = db.Column('姓名', db.String, nullable=False)
    group = db.Column('小組', db.String, nullable=True)

class Vendor(db.Model):
    __tablename__ = '廠商資料'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    name = db.Column('廠商名稱', db.String, nullable=False)

class Machine(db.Model):
    __tablename__ = '擠壓機台'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    name = db.Column('擠壓機編號', db.String, nullable=False)

class Operator(db.Model):
    __tablename__ = '擠壓人員'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    name = db.Column('員工姓名', db.String, nullable=False)

class PatrolMain(db.Model):
    __tablename__ = '巡檢主檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    date = db.Column('檢驗日期', db.Date)
    machine_id = db.Column('機台', db.Integer, db.ForeignKey('擠壓機台.識別碼'))
    operator_id = db.Column('主機手', db.Integer, db.ForeignKey('擠壓人員.識別碼'))
    inspector_id = db.Column('檢驗人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    material = db.Column('材質', db.String)
    spec = db.Column('擠壓規格', db.String)
    customer_id = db.Column('客戶名稱', db.Integer, db.ForeignKey('廠商資料.識別碼'))
    batch_num = db.Column('原料批號', db.String)
    is_ng = db.Column('是否超差', db.Boolean, default=False, nullable=True, index=True)

    details = db.relationship('PatrolDetail', backref='main', cascade="all, delete-orphan")

class PatrolDetail(db.Model):
    __tablename__ = '巡檢子檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    main_id = db.Column('主檔ID', db.Integer, db.ForeignKey('巡檢主檔.識別碼'))
    group = db.Column('組別', db.Integer)
    item = db.Column('測量項目', db.String)
    position = db.Column('測量位置', db.String)
    min_val = db.Column('最小值', db.Numeric)
    max_val = db.Column('最大值', db.Numeric)

class ShippingData(db.Model):
    __tablename__ = '出貨檢驗數據'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    date = db.Column('檢驗日期', db.Date, index=True)
    material = db.Column('材質', db.String, index=True)
    spec = db.Column('檢驗規格', db.String)
    order_num = db.Column('訂單號碼', db.String)
    inspector_id = db.Column('檢驗人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    vendor_id = db.Column('廠商名稱', db.Integer, db.ForeignKey('廠商資料.識別碼'))
    group_count = db.Column('組數', db.Integer, default=5)
    
    # Groups 1-10 (expanded from 5 to support variable group counts)
    for i in range(1, 11):
        locals()[f'od{i}_min'] = db.Column(f'外徑{i}-min', db.String)
        locals()[f'od{i}_max'] = db.Column(f'外徑{i}-max', db.String)
        locals()[f'id{i}_min'] = db.Column(f'內徑{i}-min', db.String)
        locals()[f'id{i}_max'] = db.Column(f'內徑{i}-max', db.String)
        locals()[f'th{i}_min'] = db.Column(f'厚度{i}-min', db.String)
        locals()[f'th{i}_max'] = db.Column(f'厚度{i}-max', db.String)
        locals()[f'concentricity{i}'] = db.Column(f'同心度{i}', db.String)
        locals()[f'length{i}'] = db.Column(f'長度{i}', db.String)
        locals()[f'hardness{i}'] = db.Column(f'硬度{i}', db.String)
        locals()[f'vickers{i}'] = db.Column(f'韋伯氏硬度{i}', db.String)
        locals()[f'straightness{i}'] = db.Column(f'真直度{i}', db.String)
        locals()[f'roundness{i}'] = db.Column(f'真圓度{i}', db.String)
    
    # Relationships
    inspector = db.relationship('Inspector', backref='shipping_data')
    vendor = db.relationship('Vendor', backref='shipping_data')

    is_ng = db.Column('是否超差', db.Boolean, default=False, index=True)
    
    def get_measurement(self, attr_prefix, group, is_minmax):
        """Get measurement block for a specific group and prefix"""
        if is_minmax:
            v_min = getattr(self, f"{attr_prefix}{group}_min", None)
            v_max = getattr(self, f"{attr_prefix}{group}_max", None)
            return (v_min, v_max)
        else:
            return getattr(self, f"{attr_prefix}{group}", None)
            
    def compute_is_ng(self, tolerances):
        """Evaluate if record is out of tolerance"""
        if not tolerances:
            return False
            
        from .services.tolerance_service import ToleranceService
        # spec values parsing
        spec_values = ToleranceService.parse_spec_values(self.spec)
        
        std_limits = {}
        for t in tolerances:
            lsl = float('-inf')
            usl = float('inf')
            
            tc_min = t.get('尺寸下限')
            tc_max = t.get('尺寸上限')
            tol_min = t.get('公差下限')
            tol_max = t.get('公差上限')
            t_std = t.get('標準值')
            t_item = t.get('項目')
            
            if tc_min is not None and tc_max is not None:
                lsl = tc_min
                usl = tc_max
            elif tol_min is not None and tol_max is not None:
                std_val = spec_values.get(t_item, 0)
                if std_val == 0 and t_std is not None:
                    std_val = t_std
                if std_val == 0:
                    continue
                lsl = std_val + tol_min
                usl = std_val + tol_max
            elif tc_max is not None:
                lsl = 0
                usl = tc_max
            elif tc_min is not None:
                lsl = tc_min
                usl = float('inf')
            else:
                continue
                
            std_limits[t_item] = {'lsl': lsl, 'usl': usl}

        items_to_check = ["外徑", "內徑", "真圓度", "厚度", "同心度", "長度", "硬度", "真直度"]
        gc = self.group_count or 5

        def safe_float(v):
            try: return float(v)
            except (ValueError, TypeError): return None
            
        attr_map = {
            '外徑': 'od',
            '內徑': 'id',
            '厚度': 'th',
            '同心度': 'concentricity',
            '長度': 'length',
            '硬度': 'hardness',
            '真直度': 'straightness',
            '真圓度': 'roundness'
        }

        for it in items_to_check:
            tol = std_limits.get(it)
            if not tol: continue

            attr_prefix = attr_map[it]
            is_minmax = it in ["外徑", "內徑", "厚度"]
            
            for g in range(1, int(gc) + 1):
                if is_minmax:
                    v_min, v_max = self.get_measurement(attr_prefix, g, True)
                    v_min = safe_float(v_min)
                    v_max = safe_float(v_max)
                    if v_min is not None and (v_min < tol['lsl'] or v_min > tol['usl']): return True
                    if v_max is not None and (v_max < tol['lsl'] or v_max > tol['usl']): return True
                else:
                    v = self.get_measurement(attr_prefix, g, False)
                    v = safe_float(v)
                    if v is not None and (v < tol['lsl'] or v > tol['usl']): return True
                    
        return False

class VendorToleranceMain(db.Model):
    __tablename__ = '廠商公差主檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    vendor_id = db.Column('廠商ID', db.Integer, db.ForeignKey('廠商資料.識別碼'))
    material = db.Column('材質', db.String)
    spec = db.Column('規格', db.String)
    note = db.Column('備註', db.String)
    created_at = db.Column('建立日期', db.DateTime)

    details = db.relationship('VendorToleranceDetail', backref='main', cascade="all, delete-orphan")
    vendor = db.relationship('Vendor', backref='tolerances')

class VendorToleranceDetail(db.Model):
    __tablename__ = '廠商公差明細檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    main_id = db.Column('主檔ID', db.Integer, db.ForeignKey('廠商公差主檔.識別碼'))
    item = db.Column('測量項目', db.String)
    position = db.Column('測量位置', db.String)

    tolerance_min = db.Column('公差下限', db.Float)
    tolerance_max = db.Column('公差上限', db.Float)
    dim_min = db.Column('尺寸下限', db.Float)
    dim_max = db.Column('尺寸上限', db.Float)
    std_val = db.Column('標準值', db.Float)
    unit = db.Column('單位', db.String)
    note = db.Column('備註', db.String)

class ExtrusionToleranceMain(db.Model):
    """擠壓公差主檔"""
    __tablename__ = '擠壓公差主檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    material = db.Column('材質', db.String, nullable=False)
    spec = db.Column('規格', db.String)
    vendor = db.Column('廠商', db.String)
    note = db.Column('備註', db.String)
    created_at = db.Column('建立日期', db.Date, default=date.today)

    details = db.relationship('ExtrusionToleranceDetail', backref='main', cascade="all, delete-orphan")


class ExtrusionToleranceDetail(db.Model):
    """擠壓公差明細檔"""
    __tablename__ = '擠壓公差明細檔'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    main_id = db.Column('主檔ID', db.Integer, db.ForeignKey('擠壓公差主檔.識別碼'), nullable=False)
    item = db.Column('測量項目', db.String, nullable=False)
    position = db.Column('測量位置', db.String)
    tolerance_min = db.Column('公差下限', db.Numeric)
    tolerance_max = db.Column('公差上限', db.Numeric)
    std_val = db.Column('標準值', db.Numeric)
    unit = db.Column('單位', db.String, default='mm')

class NCMR(db.Model):
    __tablename__ = '不合格品單'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    ncmr_number = db.Column('NCMR單號', db.String, index=True)
    date = db.Column('發現日期', db.Date, index=True)
    source = db.Column('來源', db.String)
    product_info = db.Column('產品資訊', db.String)
    quantity = db.Column('產品數量', db.Integer)
    material = db.Column('材質', db.String)
    vendor = db.Column('廠商', db.String)
    batch_num = db.Column('批號', db.String)
    description = db.Column('不良描述', db.String)
    defect_quantity = db.Column('不良數量', db.Integer)
    inspector_id = db.Column('發現人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    result = db.Column('判定結果', db.String)
    status = db.Column('狀態', db.String, index=True)
    defect_category = db.Column('不良原因大類', db.String)
    defect_detail = db.Column('不良原因細項', db.String)
    create_date = db.Column('建立日期', db.Date)

    # 1.4 新增：關聯 CAPA 追溯欄位
    related_capa_id = db.Column('關聯CAPA_ID', db.Integer, nullable=True)
    related_capa_source = db.Column('關聯CAPA來源', db.String(20), nullable=True)

    inspector = db.relationship('Inspector', backref='ncmr_list')
    corrective_actions = db.relationship('CorrectiveAction', backref='ncmr', cascade="all, delete-orphan")
    rework_requests = db.relationship('ReworkRequest', backref='ncmr', cascade="all, delete-orphan")

class CorrectiveAction(db.Model):
    """異常矯正單 — CAPA（我方執行矯正，含 D0-D8 完整 8D 流程）"""
    __tablename__ = '異常矯正單'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    car_number = db.Column('CAR單號', db.String, index=True)
    eight_d_number = db.Column('8D單號', db.String, index=True)
    status = db.Column('狀態', db.String, index=True, default='進行中')

    # --- 1.5 源頭欄位（強制有來源）---
    source_type = db.Column('來源類型', db.String(20), nullable=True)   # 'ncmr' | 'complaint'
    source_id   = db.Column('來源ID',   db.Integer,    nullable=True)
    # 保留舊欄位相容性（遷移後從 source_id 帶入）
    ncmr_id = db.Column('NCMR_ID', db.Integer, db.ForeignKey('不合格品單.識別碼'), nullable=True)

    # --- 嚴格度 ---
    rigor = db.Column('嚴格度', db.String(20), nullable=True, default='完整8D')
    # '完整8D' | '簡化5D'

    # --- D0 立案 ---
    d0_symptom   = db.Column('D0_症狀描述',   db.Text, nullable=True)
    d0_criteria  = db.Column('D0_判斷準則',   JSONB,   nullable=True)   # list of strings
    d0_severity  = db.Column('D0_嚴重度',     db.String(20), nullable=True)  # Critical|Major|Minor
    d0_deadline  = db.Column('D0_客戶要求結案日', db.Date, nullable=True)

    # --- D1 小組（結構化）---
    d1_champion_id = db.Column('D1_Champion', db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    d1_leader_id   = db.Column('D1_Leader',   db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    d1_members     = db.Column('D1_成員',     JSONB, nullable=True)     # list of inspector ids
    # 保留舊欄位相容性
    owner_id = db.Column('負責人員', db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)

    # --- D2 問題描述（5W2H）---
    d2_what      = db.Column('D2_What',      db.Text, nullable=True)
    d2_where     = db.Column('D2_Where',     db.Text, nullable=True)
    d2_when      = db.Column('D2_When',      db.Text, nullable=True)
    d2_who       = db.Column('D2_Who',       db.Text, nullable=True)
    d2_why       = db.Column('D2_Why',       db.Text, nullable=True)
    d2_how       = db.Column('D2_How',       db.Text, nullable=True)
    d2_how_many  = db.Column('D2_HowMany',   db.Text, nullable=True)
    # 保留舊欄位（顯示用，可存舊版純文字）
    d2 = db.Column('D2_問題描述', db.Text, nullable=True)

    # --- D3 暫時對策 ---
    d3_action        = db.Column('D3_對策內容',     db.Text, nullable=True)
    d3_effective_date= db.Column('D3_生效日',       db.Date, nullable=True)
    d3_verification  = db.Column('D3_有效性驗證',   db.Text, nullable=True)
    d3 = db.Column('D3_暫時對策', db.Text, nullable=True)

    # --- D4 真因分析 ---
    d4_tool         = db.Column('D4_工具',        db.String(20), nullable=True)  # '5why'|'fishbone'|'both'
    d4_five_why     = db.Column('D4_5Why資料',    JSONB, nullable=True)  # [{q,a}, ...]
    d4_fishbone     = db.Column('D4_魚骨圖資料',  JSONB, nullable=True)  # {man:[],machine:[],material:[],method:[],measurement:[],environment:[]}
    d4_root_cause   = db.Column('D4_根本原因',    db.Text, nullable=True)
    d4 = db.Column('D4_真因分析', db.Text, nullable=True)

    # --- D5 永久對策 ---
    d5_action       = db.Column('D5_對策內容',     db.Text, nullable=True)
    d5_planned_date = db.Column('D5_預計實施日',   db.Date, nullable=True)
    d5_verify_plan  = db.Column('D5_驗證計畫',     db.Text, nullable=True)
    d5 = db.Column('D5_永久對策', db.Text, nullable=True)

    # --- D6 實施驗證 ---
    d6_implement_date= db.Column('D6_實施日',      db.Date,    nullable=True)
    d6_result        = db.Column('D6_驗證結果',    db.Text,    nullable=True)
    d6_verified      = db.Column('D6_驗證通過',    db.Boolean, nullable=True, default=False)
    d6 = db.Column('D6_成效驗證', db.Text, nullable=True)

    # --- D7 預防再發 ---
    d7_actions = db.Column('D7_橫展類型', JSONB, nullable=True)
    # [{type:'pfmea'|'control_plan'|'sop'|'training'|'cross_part'|'customer_notify'|'other',
    #   task_id:int, assignee_id:int, due_date:'YYYY-MM-DD', part_nos:[str]}]
    d7 = db.Column('D7_預防再發', db.Text, nullable=True)

    # --- D8 結案 ---
    d8_close_date   = db.Column('D8_結案日期',   db.Date, nullable=True)
    d8_confirmation = db.Column('D8_結案確認',   db.Text, nullable=True)
    d8_recognition  = db.Column('D8_團隊表揚',   db.Text, nullable=True)

    # --- 時間戳 ---
    created_at = db.Column('建立時間', db.DateTime, default=datetime.utcnow)
    closed_at  = db.Column('結案日期_舊', db.DateTime, nullable=True)

    # --- 關聯 ---
    owner     = db.relationship('Inspector', foreign_keys=[owner_id],       backref='cars')
    champion  = db.relationship('Inspector', foreign_keys=[d1_champion_id], backref='capa_champion')
    leader    = db.relationship('Inspector', foreign_keys=[d1_leader_id],   backref='capa_leader')
    tasks     = db.relationship('ActionTask', backref='capa',
                                primaryjoin="and_(ActionTask.source_type=='capa', "
                                            "foreign(ActionTask.source_id)==CorrectiveAction.id)",
                                lazy='dynamic')

class ReworkRequest(db.Model):
    __tablename__ = '重工申請單'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    ncmr_id = db.Column('NCMR_ID', db.Integer, db.ForeignKey('不合格品單.識別碼'))
    rework_number = db.Column('申請單號', db.String)
    applicant_id = db.Column('申請人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    department = db.Column('部門', db.String)
    urgency = db.Column('緊急程度', db.String)
    product_info = db.Column('產品資訊', db.String)
    batch_num = db.Column('批號', db.String)
    quantity = db.Column('重工數量', db.Float)
    reason = db.Column('申請原因', db.String)
    expected_date = db.Column('預計完成日期', db.Date)
    status = db.Column('狀態', db.String)
    
    review_status = db.Column('審核狀態', db.String)
    reviewer_id = db.Column('審核人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    review_time = db.Column('審核時間', db.DateTime)
    review_opinion = db.Column('審核意見', db.String)
    
    created_at = db.Column('申請日期', db.DateTime, default=datetime.utcnow)
    actual_finish_date = db.Column('實際完成日期', db.DateTime)
    complaint_id = db.Column('客訴_ID', db.Integer, nullable=True)

    applicant = db.relationship('Inspector', foreign_keys=[applicant_id], backref='rework_requests')
    reviewer = db.relationship('Inspector', foreign_keys=[reviewer_id], backref='rework_reviews')
    executions = db.relationship('ReworkExecution', backref='request', cascade="all, delete-orphan")
    inspections = db.relationship('ReworkInspection', backref='request', cascade="all, delete-orphan")

class ReworkExecution(db.Model):
    __tablename__ = '重工執行記錄'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    rework_id = db.Column('重工單號', db.Integer, db.ForeignKey('重工申請單.識別碼'))
    dept = db.Column('執行部門', db.String)
    owner_id = db.Column('負責人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    participants = db.Column('協同人員', db.String)
    
    start_time = db.Column('開始時間', db.DateTime)
    est_end_time = db.Column('預計完成時間', db.DateTime)
    real_end_time = db.Column('實際完成時間', db.DateTime)
    
    equipment = db.Column('使用設備', db.String)
    method = db.Column('重工方式', db.String)
    sop_num = db.Column('SOP編號', db.String)
    consumables = db.Column('耗材記錄', db.String)
    
    complete_qty = db.Column('完成數量', db.Float)
    defect_qty = db.Column('不良數量', db.Float)
    yield_rate = db.Column('良率', db.Float)
    status = db.Column('執行狀況', db.String)
    abnormal = db.Column('異常狀況', db.String)
    executor_id = db.Column('執行人員', db.Integer, db.ForeignKey('品管人員.識別碼'))

    owner = db.relationship('Inspector', foreign_keys=[owner_id], backref='rework_executions')
    executor = db.relationship('Inspector', foreign_keys=[executor_id], backref='rework_executions_done')

class ReworkInspection(db.Model):
    __tablename__ = '重工品檢記錄'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    rework_id = db.Column('重工單號', db.Integer, db.ForeignKey('重工申請單.識別碼'))
    date = db.Column('檢驗日期', db.Date)
    inspector_id = db.Column('檢驗人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    item = db.Column('檢驗項目', db.String)
    standard = db.Column('檢驗標準', db.String)
    result = db.Column('檢驗結果', db.String)
    defect_qty = db.Column('不良數量', db.Float)
    remark = db.Column('檢驗備註', db.String)
    created_at = db.Column('記錄時間', db.DateTime, default=datetime.utcnow)

    inspector = db.relationship('Inspector', backref='rework_inspections')

class ReworkCost(db.Model):
    __tablename__ = '重工成本分析'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    rework_id = db.Column('重工單號', db.Integer, db.ForeignKey('重工申請單.識別碼'))
    cost_type = db.Column('成本類型', db.String)
    cost_item = db.Column('成本項目', db.String)
    unit_cost = db.Column('單位成本', db.Float)
    quantity = db.Column('數量', db.Float)
    total_cost = db.Column('總成本', db.Float)
    currency = db.Column('成本幣別', db.String, default='TWD')
    recorder_id = db.Column('記錄人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    remark = db.Column('備註', db.String)
    created_at = db.Column('記錄日期', db.DateTime, default=datetime.utcnow)

    recorder = db.relationship('Inspector', backref='rework_costs')
    rework = db.relationship('ReworkRequest', backref='costs')


# ============================================================
# 1.1 客訴模組
# ============================================================
class CustomerComplaint(db.Model):
    """客訴紀錄 — 外部不良（客戶端發現），獨立於 NCMR"""
    __tablename__ = '客訴紀錄'

    id = db.Column('識別碼', db.Integer, primary_key=True)
    complaint_no = db.Column('客訴單號', db.String(50), unique=True, index=True)

    # 基本資訊
    customer       = db.Column('客戶',      db.String(100), nullable=False)
    complaint_date = db.Column('客訴日期',  db.Date,        nullable=False, index=True)
    product_no     = db.Column('料號',      db.String(100), nullable=False)
    description    = db.Column('不良描述',  db.Text,        nullable=False)
    contact_person = db.Column('客戶聯絡人', db.String(100), nullable=True)
    severity       = db.Column('嚴重度',    db.String(20),  nullable=True)
    defect_category= db.Column('不良類別',  db.String(100), nullable=True)

    # 客訴類型：'quality' | 'warranty' | 'field_failure'
    complaint_type = db.Column('客訴類型', db.String(30), nullable=False, default='quality')

    # Warranty / Field Failure 額外欄位
    device_serial = db.Column('失效裝置序號', db.String(100), nullable=True)
    usage_env     = db.Column('使用環境',     db.Text,        nullable=True)
    failure_hours = db.Column('失效時數',     db.Float,       nullable=True)

    # 應答時效
    initial_reply_deadline = db.Column('初步回覆期限', db.Date, nullable=True)
    final_reply_deadline   = db.Column('最終回覆期限', db.Date, nullable=True)

    # 回覆內容
    initial_reply      = db.Column('初步回覆內容', db.Text,     nullable=True)
    initial_reply_date = db.Column('初步回覆日期', db.DateTime, nullable=True)
    final_reply        = db.Column('最終回覆內容', db.Text,     nullable=True)
    final_reply_date   = db.Column('最終回覆日期', db.DateTime, nullable=True)

    # 客戶滿意度（1-5）
    satisfaction      = db.Column('客戶滿意度', db.Integer, nullable=True)
    satisfaction_note = db.Column('滿意度備註', db.Text,    nullable=True)

    # 重複客訴警示
    is_repeat   = db.Column('是否重複客訴',   db.Boolean, default=False)
    repeat_refs = db.Column('重複客訴參考單號', JSONB,      nullable=True)

    # 關聯單據
    related_capa_id   = db.Column('關聯CAPA_ID',  db.Integer, nullable=True)
    related_cara_id   = db.Column('關聯CARA_ID',  db.Integer, nullable=True)
    related_rework_id = db.Column('關聯重工_ID',  db.Integer, nullable=True)

    # 狀態：'待處理' | '處理中' | '已結案'
    status = db.Column('狀態', db.String(20), default='待處理', index=True)

    # 時間戳
    created_by = db.Column('建立人員', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    created_at = db.Column('建立時間', db.DateTime, default=datetime.utcnow)
    updated_at = db.Column('更新時間', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = db.relationship('User', backref='complaints', foreign_keys=[created_by])


# ============================================================
# 1.2 任務模組（跨模組共用）
# ============================================================
class ActionTask(db.Model):
    """橫展任務 — 跨模組共用，初期與 CAPA D7 連動"""
    __tablename__ = '橫展任務'

    id = db.Column('識別碼', db.Integer, primary_key=True)
    task_no = db.Column('任務單號', db.String(50), unique=True, index=True)

    # 多型來源
    source_type = db.Column('來源類型', db.String(30), nullable=False, index=True)
    source_id   = db.Column('來源ID',   db.Integer,    nullable=False, index=True)

    # 任務內容
    category    = db.Column('類別', db.String(50), nullable=False)
    # 'pfmea'|'control_plan'|'sop'|'training'|'cross_part'|'customer_notify'|'other'
    title       = db.Column('標題',    db.String(200), nullable=False)
    description = db.Column('描述',    db.Text,        nullable=True)
    part_nos    = db.Column('相關料號', JSONB,          nullable=True)

    # 指派
    assignee_id = db.Column('負責人', db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)

    # 期限與狀態：'pending'|'in_progress'|'completed'|'waived'
    due_date = db.Column('應完成日', db.Date,      nullable=True)
    status   = db.Column('狀態',    db.String(20), default='pending', index=True)

    # 完成資訊
    completion_proof = db.Column('完成證明', db.Text,     nullable=True)
    waiver_reason    = db.Column('豁免理由', db.Text,     nullable=True)
    completed_at     = db.Column('完成時間', db.DateTime, nullable=True)

    # 時間戳
    created_at = db.Column('建立時間', db.DateTime, default=datetime.utcnow)
    updated_at = db.Column('更新時間', db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignee = db.relationship('Inspector', backref='assigned_tasks')


# ============================================================
# 1.3 附件模組（跨模組共用）
# ============================================================
class Attachment(db.Model):
    """共用附件 — 依 entity_type + entity_id + d_step 分類"""
    __tablename__ = '附件'

    id = db.Column('識別碼', db.Integer, primary_key=True)

    # 所屬實體（多型）：'capa'|'cara'|'task'|'complaint'
    entity_type = db.Column('實體類型', db.String(30), nullable=False, index=True)
    entity_id   = db.Column('實體ID',   db.Integer,    nullable=False, index=True)
    d_step      = db.Column('D步驟',    db.Integer,    nullable=True)

    # 檔案資訊
    file_name = db.Column('檔案名稱', db.String(255), nullable=False)
    file_path = db.Column('檔案路徑', db.String(500), nullable=False)
    mime_type = db.Column('MIME類型', db.String(100), nullable=True)
    file_size = db.Column('檔案大小', db.Integer,    nullable=True)   # bytes

    # 上傳資訊
    uploaded_by = db.Column('上傳人員', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    uploaded_at = db.Column('上傳時間', db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', backref='attachments', foreign_keys=[uploaded_by])


# ============================================================
# 1.6 CARARecord（矯正措施要求，對外發給供應商）
# ============================================================
class CARARecord(db.Model):
    """矯正措施要求 — 對供應商發出，簡化流程 D2/D3/D4/D6/D8"""
    __tablename__ = '矯正措施要求'

    id      = db.Column('識別碼',  db.Integer,   primary_key=True)
    cara_no = db.Column('CARA單號', db.String(50), unique=True, index=True)
    status  = db.Column('狀態',    db.String(20), default='進行中', index=True)

    # 來源（來料異常 NCMR）
    ncmr_id = db.Column('NCMR_ID', db.Integer, db.ForeignKey('不合格品單.識別碼'), nullable=True)
    vendor  = db.Column('廠商',    db.String(100), nullable=True)

    # D2 問題描述（5W2H）
    d2_what     = db.Column('D2_What',    db.Text, nullable=True)
    d2_where    = db.Column('D2_Where',   db.Text, nullable=True)
    d2_when     = db.Column('D2_When',    db.Text, nullable=True)
    d2_who      = db.Column('D2_Who',     db.Text, nullable=True)
    d2_why      = db.Column('D2_Why',     db.Text, nullable=True)
    d2_how      = db.Column('D2_How',     db.Text, nullable=True)
    d2_how_many = db.Column('D2_HowMany', db.Text, nullable=True)
    d2          = db.Column('D2_問題描述', db.Text, nullable=True)  # 舊版相容

    # D3 暫時對策（供應商回覆）
    d3_action         = db.Column('D3_對策內容',   db.Text, nullable=True)
    d3_effective_date = db.Column('D3_生效日',     db.Date, nullable=True)
    d3_verification   = db.Column('D3_有效性驗證', db.Text, nullable=True)
    d3                = db.Column('D3_暫時對策',   db.Text, nullable=True)

    # D4 真因分析（供應商回覆）
    d4_tool       = db.Column('D4_工具',      db.String(20), nullable=True)
    d4_five_why   = db.Column('D4_5Why資料',  JSONB, nullable=True)
    d4_fishbone   = db.Column('D4_魚骨圖資料', JSONB, nullable=True)
    d4_root_cause = db.Column('D4_根本原因',  db.Text, nullable=True)
    d4            = db.Column('D4_真因分析',   db.Text, nullable=True)

    # D6 實施驗證
    d6_implement_date = db.Column('D6_實施日',   db.Date,    nullable=True)
    d6_result         = db.Column('D6_驗證結果', db.Text,    nullable=True)
    d6_verified       = db.Column('D6_驗證通過', db.Boolean, nullable=True, default=False)
    d6                = db.Column('D6_成效驗證', db.Text,    nullable=True)

    # D8 結案
    d8_close_date   = db.Column('D8_結案日期', db.Date, nullable=True)
    d8_confirmation = db.Column('D8_結案確認', db.Text, nullable=True)
    d8              = db.Column('D8_結案確認_舊', db.Text, nullable=True)

    # 負責人（舊版相容回填）
    owner_id     = db.Column('負責人員',  db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    d1_leader_id = db.Column('D1_Leader', db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)

    # 時間戳
    created_at = db.Column('建立時間', db.DateTime, default=datetime.utcnow)
    closed_at  = db.Column('結案時間', db.DateTime, nullable=True)

    ncmr   = db.relationship('NCMR', backref='cara_records')
    owner  = db.relationship('Inspector', foreign_keys=[owner_id],     backref='cara_owned')
    leader = db.relationship('Inspector', foreign_keys=[d1_leader_id], backref='cara_led')
