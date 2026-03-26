
from datetime import datetime
from .extensions import db
from sqlalchemy.orm import relationship

class User(db.Model):
    __tablename__ = '使用者'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    username = db.Column('使用者名稱', db.String, unique=True, nullable=False)
    password = db.Column('密碼', db.String, nullable=False)
    is_active = db.Column('是否啟用', db.Boolean, default=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Inspector(db.Model):
    __tablename__ = '品管人員'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    name = db.Column('姓名', db.String, nullable=False)

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
    note = db.Column('備註', db.String)
    created_at = db.Column('建立日期', db.Date)

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

    inspector = db.relationship('Inspector', backref='ncmr_list')
    corrective_actions = db.relationship('CorrectiveAction', backref='ncmr', cascade="all, delete-orphan")
    rework_requests = db.relationship('ReworkRequest', backref='ncmr', cascade="all, delete-orphan")

class CorrectiveAction(db.Model):
    __tablename__ = '異常矯正單'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    ncmr_id = db.Column('NCMR_ID', db.Integer, db.ForeignKey('不合格品單.識別碼'))
    car_number = db.Column('CAR單號', db.String, index=True)
    eight_d_number = db.Column('8D單號', db.String, index=True)
    owner_id = db.Column('負責人員', db.Integer, db.ForeignKey('品管人員.識別碼'))
    status = db.Column('狀態', db.String, index=True)
    
    d1 = db.Column('D1_小組成員', db.String)
    d2 = db.Column('D2_問題描述', db.String)
    d3 = db.Column('D3_暫時對策', db.String)
    d4 = db.Column('D4_真因分析', db.String)
    d5 = db.Column('D5_永久對策', db.String)
    d6 = db.Column('D6_成效驗證', db.String)
    d7 = db.Column('D7_預防再發', db.String)
    d8 = db.Column('D8_結案確認', db.String)

    created_at = db.Column('建立時間', db.DateTime, default=datetime.utcnow)
    closed_at = db.Column('結案日期', db.DateTime)

    owner = db.relationship('Inspector', backref='cars')

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
