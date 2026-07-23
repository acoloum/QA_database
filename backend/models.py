
from datetime import date, datetime, timezone
from .extensions import db
from sqlalchemy import event, inspect
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB


def utc_now():
    """回傳 timezone-aware UTC 時間，供 SQLAlchemy default/onupdate 使用。"""
    return datetime.now(timezone.utc)


class SoftDeleteMixin:
    """軟刪除 Mixin：加入 deleted_at 欄位，刪除時設時間戳而非真正 DELETE"""
    deleted_at = db.Column('刪除時間', db.DateTime(timezone=True), nullable=True, index=True)

    def soft_delete(self):
        self.deleted_at = datetime.now(timezone.utc)

    @classmethod
    def active_query(cls):
        return cls.query.filter(cls.deleted_at.is_(None))


JsonType = JSONB().with_variant(db.JSON(), 'sqlite')

class User(db.Model):
    __tablename__ = '使用者'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    username = db.Column('使用者名稱', db.String, unique=True, nullable=False)
    password = db.Column('密碼', db.String, nullable=False)
    inspector_id = db.Column('品管人員ID', db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    is_active = db.Column('是否啟用', db.Boolean, default=True)
    role = db.Column('角色', db.String(20), nullable=False, default='user', server_default='user')
    created_at = db.Column('建立時間', db.DateTime(timezone=True), nullable=True,
                           default=lambda: datetime.now(timezone.utc))
    inspector = db.relationship('Inspector', foreign_keys=[inspector_id], backref='users')

    def __repr__(self):
        return f'<User {self.username}>'


class Role(db.Model):
    __tablename__ = '角色'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    code = db.Column('角色代碼', db.String(30), unique=True, nullable=False)
    name = db.Column('角色名稱', db.String(50), nullable=False)
    permissions = db.Column('權限', JsonType, nullable=False, default=dict)

    def has_permission(self, perm: str) -> bool:
        return bool(self.permissions.get(perm))

    def __repr__(self):
        return f'<Role {self.code}>'


class AuditLog(db.Model):
    __tablename__ = '操作日誌'
    __table_args__ = (
        db.Index('idx_auditlog_module_record', '模組', '資料ID'),
        db.Index('idx_auditlog_user_created', '使用者ID', '建立時間'),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    user_id = db.Column('使用者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    action = db.Column('操作類型', db.String(20), nullable=False)
    module = db.Column('模組', db.String(30), nullable=False)
    record_id = db.Column('資料ID', db.Integer, nullable=True)
    old_value = db.Column('操作前', JsonType, nullable=True)
    new_value = db.Column('操作後', JsonType, nullable=True)
    created_at = db.Column('建立時間', db.DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AuditLog {self.module} {self.action} {self.record_id}>'


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
    # §6.6 離群值：標示無效並保留追溯，不得刪除；排除於統計計算之外
    excluded         = db.Column('排除統計', db.Boolean, default=False, nullable=False)
    exclusion_reason = db.Column('排除原因', db.String(200), nullable=True)
    exclusion_user_id = db.Column(
        '排除者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    excluded_at = db.Column('排除時間', db.DateTime(timezone=True), nullable=True)

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

    # 量測值已全面改存子表 ShippingMeasurement（出貨巡檢量測明細），
    # 原扁平欄位（外徑1-min … 真圓度10）已於 migration 19 移除。

    # Relationships
    inspector = db.relationship('Inspector', backref='shipping_data')
    vendor = db.relationship('Vendor', backref='shipping_data')
    measurements = db.relationship('ShippingMeasurement', backref='shipping',
                                   cascade='all, delete-orphan',
                                   order_by='ShippingMeasurement.group_num, ShippingMeasurement.item')

    is_ng = db.Column('是否超差', db.Boolean, default=False, index=True)

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

        # 限定要判定的量測項目（與舊版一致；不含韋伯氏硬度）
        items_to_check = {"外徑", "內徑", "真圓度", "厚度", "同心度", "長度", "硬度", "真直度"}
        # 以下項目量測值為 0 代表「未量測」（空白被存成 0），非真實量測，須跳過：
        #   尺寸(外徑/內徑/厚度/長度) 幾何上不可能為 0；硬度實測最小為 1.0，0 為未量測哨兵值。
        # 真圓度/同心度/真直度的 0 是理想值(真實好值)，不可跳過，故不列入。
        zero_means_unmeasured = {"外徑", "內徑", "厚度", "長度", "硬度", "韋伯氏硬度"}
        gc = int(self.group_count or 5)

        def safe_float(v):
            try: return float(v)
            except (ValueError, TypeError): return None

        # 改讀子表明細（ShippingMeasurement）取代舊的扁平欄位
        for m in self.measurements:
            if m.group_num > gc:
                continue
            if m.item not in items_to_check:
                continue
            tol = std_limits.get(m.item)
            if not tol:
                continue
            for raw in (m.value_min, m.value_max, m.value_single):
                v = safe_float(raw)
                if v is None:
                    continue
                # 值為 0 視為未量測，跳過（避免空白 0 造成假性超差）
                if v == 0 and m.item in zero_means_unmeasured:
                    continue
                if v < tol['lsl'] or v > tol['usl']:
                    return True

        return False

class ShippingMeasurement(db.Model):
    """出貨巡檢量測明細 — 每筆對應一個組別的一個量測項目(可含測量位置)"""
    __tablename__ = '出貨巡檢量測明細'
    __table_args__ = (
        db.UniqueConstraint('出貨檢驗_ID', '組別', '量測項目', '測量位置',
                            name='uq_shipping_group_item'),
        db.Index('idx_shipping_meas_shipping_id', '出貨檢驗_ID'),
    )

    id          = db.Column('識別碼',      db.Integer, primary_key=True)
    shipping_id = db.Column('出貨檢驗_ID', db.Integer, db.ForeignKey('出貨檢驗數據.識別碼'), nullable=False)
    group_num   = db.Column('組別',        db.Integer, nullable=False)
    item        = db.Column('量測項目',    db.String(30), nullable=False)
    # 空字串 = 未分段（刻意不用 NULL：PostgreSQL 唯一鍵不比較 NULL，會使重複防護失效）
    position    = db.Column('測量位置',    db.String(10), nullable=False, default='', server_default='')
    lower_limit = db.Column('下限', db.Numeric(12, 4), nullable=True)
    upper_limit = db.Column('上限', db.Numeric(12, 4), nullable=True)
    value_min   = db.Column('量測最小值', db.Numeric(12, 4), nullable=True)
    value_max   = db.Column('量測最大值', db.Numeric(12, 4), nullable=True)
    value_single= db.Column('量測值',     db.Numeric(12, 4), nullable=True)
    is_ng       = db.Column('是否超差',   db.Boolean, default=False, nullable=False)
    # §6.6 離群值：標示無效並保留追溯，不得刪除；排除於統計計算之外
    excluded         = db.Column('排除統計', db.Boolean, default=False, nullable=False)
    exclusion_reason = db.Column('排除原因', db.String(200), nullable=True)
    exclusion_user_id = db.Column(
        '排除者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    excluded_at = db.Column('排除時間', db.DateTime(timezone=True), nullable=True)


class SPCCache(db.Model):
    """SPC 計算快取"""
    __tablename__ = 'SPC快取'
    __table_args__ = (
        db.Index('idx_spc_cache_key', '快取鍵'),
    )

    id         = db.Column('識別碼', db.Integer, primary_key=True)
    cache_key  = db.Column('快取鍵',  db.String(255), unique=True, nullable=False)
    result     = db.Column('計算結果', JsonType, nullable=False)
    created_at = db.Column('建立時間', db.DateTime, default=utc_now)
    expires_at = db.Column('過期時間', db.DateTime, nullable=False)


class SpcControlLimit(db.Model):
    """SPC 管制界限凍結檔 — §9.4 界限經確認後凍結，重算須留紀錄
    此表由出貨與巡檢共用，以 source（資料來源）與 position（位置，巡檢前/中/後段）區分；出貨無位置維度恆為空字串"""
    __tablename__ = 'SPC管制界限'
    __table_args__ = (
        db.UniqueConstraint('資料來源', '廠商', '材質', '規格', '量測項目', '位置', name='uq_spc_limits'),
    )
    id         = db.Column('識別碼', db.Integer, primary_key=True)
    source     = db.Column('資料來源', db.String(20), nullable=False, default='shipping')
    vendor     = db.Column('廠商', db.String(100), nullable=False, default='')
    material   = db.Column('材質', db.String(100), nullable=False, default='')
    spec       = db.Column('規格', db.String(100), nullable=False, default='')
    field      = db.Column('量測項目', db.String(30), nullable=False)
    # 巡檢特有的位置維度（前/中/後段）；出貨無此維度，恆為空字串
    position   = db.Column('位置', db.String(20), nullable=False, default='')
    x_cl       = db.Column('X中心線', db.Numeric(14, 6), nullable=False)
    x_ucl      = db.Column('X上限', db.Numeric(14, 6), nullable=False)
    x_lcl      = db.Column('X下限', db.Numeric(14, 6), nullable=False)
    r_cl       = db.Column('R中心線', db.Numeric(14, 6), nullable=False)
    r_ucl      = db.Column('R上限', db.Numeric(14, 6), nullable=False)
    r_lcl      = db.Column('R下限', db.Numeric(14, 6), nullable=False, default=0)
    avg_n      = db.Column('子組大小', db.Integer, nullable=False, default=5)
    note       = db.Column('備註', db.String(200))
    created_at = db.Column('建立時間', db.DateTime, default=utc_now)
    updated_at = db.Column('更新時間', db.DateTime, default=utc_now, onupdate=utc_now)


class SpcStudy(db.Model):
    """SPC 研究主檔：保存研究範圍與來源，不覆寫歷史版本。"""

    __tablename__ = 'SPC研究'
    __table_args__ = (
        db.UniqueConstraint(
            '資料來源', '研究類型', '分析族別', '製程流識別鍵', '品質特性',
            name='uq_spc_study_identity',
        ),
        db.Index(
            'idx_spc_study_stream_characteristic',
            '分析族別', '製程流識別鍵', '品質特性',
        ),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    source = db.Column('資料來源', db.String(20), nullable=False)
    study_type = db.Column('研究類型', db.String(30), nullable=False)
    analysis_family = db.Column('分析族別', db.String(20), nullable=False, default='variable')
    process_stream_key = db.Column('製程流識別鍵', db.String(128), nullable=False)
    characteristic = db.Column('品質特性', db.String(50), nullable=False)
    filters = db.Column('篩選條件', JsonType, nullable=False, default=dict)
    msa_status = db.Column('MSA狀態', db.String(30), nullable=True)
    sampling_note = db.Column('抽樣說明', db.Text, nullable=True)
    status = db.Column('狀態', db.String(30), nullable=False, default='draft')
    legacy_limit_id = db.Column(
        '舊界限ID', db.Integer, db.ForeignKey('SPC管制界限.識別碼'),
        nullable=True, unique=True,
    )
    created_by = db.Column(
        '建立者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    created_at = db.Column(
        '建立時間', db.DateTime(timezone=True), nullable=False, default=utc_now
    )

    versions = db.relationship(
        'SpcStudyVersion', back_populates='study', cascade='all, delete-orphan',
        order_by='SpcStudyVersion.version_no',
    )


class SpcStudyVersion(db.Model):
    """SPC 不可變研究版本：保存輸入雜湊、方法版本與完整計算快照。"""

    __tablename__ = 'SPC研究版本'
    __table_args__ = (
        db.UniqueConstraint('研究ID', '版本號', name='uq_spc_study_version'),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    study_id = db.Column(
        '研究ID', db.Integer, db.ForeignKey('SPC研究.識別碼'), nullable=False
    )
    version_no = db.Column('版本號', db.Integer, nullable=False)
    method_version = db.Column('方法版本', db.String(30), nullable=False)
    code_version = db.Column('程式版本', db.String(80), nullable=True)
    data_hash = db.Column('資料雜湊', db.String(64), nullable=True)
    analysis_options = db.Column('分析選項快照', JsonType, nullable=False, default=dict)
    specification_snapshot = db.Column('規格快照', JsonType, nullable=True)
    chart_result = db.Column('管制圖結果', JsonType, nullable=True)
    stability_result = db.Column('穩定性結果', JsonType, nullable=True)
    distribution_result = db.Column('分布結果', JsonType, nullable=True)
    time_model_result = db.Column('時間模型結果', JsonType, nullable=True)
    capability_result = db.Column('能力結果', JsonType, nullable=True)
    applicability_result = db.Column('適用性結果', JsonType, nullable=True)
    status = db.Column('狀態', db.String(30), nullable=False, default='draft')
    audit_incomplete = db.Column('稽核不完整', db.Boolean, nullable=False, default=False)
    created_by = db.Column(
        '建立者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    created_at = db.Column(
        '建立時間', db.DateTime(timezone=True), nullable=False, default=utc_now
    )

    study = db.relationship('SpcStudy', back_populates='versions')
    samples = db.relationship(
        'SpcStudySample', back_populates='version', cascade='all, delete-orphan',
        order_by='SpcStudySample.subgroup_order',
    )
    limit_versions = db.relationship(
        'SpcLimitVersion', back_populates='study_version',
        cascade='all, delete-orphan', order_by='SpcLimitVersion.revision',
    )


class SpcStudySample(db.Model):
    """研究版本的樣本快照，保留來源、子組與當時的排除狀態。"""

    __tablename__ = 'SPC研究樣本'
    __table_args__ = (
        db.Index('idx_spc_sample_version_order', '研究版本ID', '子組順序'),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    version_id = db.Column(
        '研究版本ID', db.Integer, db.ForeignKey('SPC研究版本.識別碼'), nullable=False
    )
    source_record_type = db.Column('來源紀錄類型', db.String(50), nullable=False)
    source_record_id = db.Column('來源紀錄ID', db.Integer, nullable=False)
    source_measurement_id = db.Column('來源量測ID', db.Integer, nullable=True)
    source_record_ids = db.Column('來源紀錄ID清單', JsonType, nullable=False, default=list)
    source_measurement_ids = db.Column('來源量測ID清單', JsonType, nullable=False, default=list)
    sample_timestamp = db.Column('樣本時間', db.String(40), nullable=True)
    subgroup_key = db.Column('子組識別鍵', db.String(128), nullable=False)
    subgroup_order = db.Column('子組順序', db.Integer, nullable=False)
    values = db.Column('量測值', JsonType, nullable=False)
    distribution_values = db.Column('分布分析值', JsonType, nullable=False, default=list)
    excluded = db.Column('排除統計', db.Boolean, nullable=False, default=False)
    exclusion_reason = db.Column('排除原因', db.String(200), nullable=True)
    exclusion_snapshot = db.Column('排除快照', JsonType, nullable=False, default=list)

    version = db.relationship('SpcStudyVersion', back_populates='samples')


class SpcLimitVersion(db.Model):
    """經核准的 SPC 界限版本；同一製程流與特性只能有一個啟用版本。"""

    __tablename__ = 'SPC界限版本'
    __table_args__ = (
        db.UniqueConstraint('研究版本ID', '修訂版次', name='uq_spc_limit_revision'),
        db.Index(
            'uq_spc_one_active_limit',
            '分析族別', '製程流識別鍵', '品質特性', unique=True,
            postgresql_where=db.text('"狀態" = \'active\''),
            sqlite_where=db.text('"狀態" = \'active\''),
        ),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    study_version_id = db.Column(
        '研究版本ID', db.Integer, db.ForeignKey('SPC研究版本.識別碼'), nullable=False
    )
    analysis_family = db.Column('分析族別', db.String(20), nullable=False, default='variable')
    process_stream_key = db.Column('製程流識別鍵', db.String(128), nullable=False)
    characteristic = db.Column('品質特性', db.String(50), nullable=False)
    revision = db.Column('修訂版次', db.Integer, nullable=False)
    chart_type = db.Column('管制圖類型', db.String(20), nullable=False)
    limits = db.Column('界限內容', JsonType, nullable=False)
    status = db.Column('狀態', db.String(30), nullable=False, default='draft')
    note = db.Column('備註', db.Text, nullable=True)
    reason = db.Column('變更原因', db.Text, nullable=True)
    legacy_limit_id = db.Column(
        '舊界限ID', db.Integer, db.ForeignKey('SPC管制界限.識別碼'),
        nullable=True, unique=True,
    )
    audit_incomplete = db.Column('稽核不完整', db.Boolean, nullable=False, default=False)
    created_by = db.Column(
        '建立者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    created_at = db.Column(
        '建立時間', db.DateTime(timezone=True), nullable=False, default=utc_now
    )
    approved_by = db.Column(
        '核准者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    approved_at = db.Column('核准時間', db.DateTime(timezone=True), nullable=True)
    effective_at = db.Column('生效時間', db.DateTime(timezone=True), nullable=True)
    retired_by = db.Column(
        '停用者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    retired_at = db.Column('停用時間', db.DateTime(timezone=True), nullable=True)

    study_version = db.relationship('SpcStudyVersion', back_populates='limit_versions')
    events = db.relationship(
        'SpcEvent', back_populates='limit_version', cascade='all, delete-orphan',
        order_by='SpcEvent.id',
    )


class SpcEvent(db.Model):
    """SPC 規則觸發事件，供後續 OCAP 調查與結案追蹤。"""

    __tablename__ = 'SPC事件'
    __table_args__ = (
        db.UniqueConstraint(
            '界限版本ID', '來源資料點鍵', '圖別', '規則代碼',
            name='uq_spc_event_source_rule',
        ),
        db.CheckConstraint(
            '"狀態" IN (\'open\', \'investigating\', \'closed\')',
            name='ck_spc_event_status',
        ),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    limit_version_id = db.Column(
        '界限版本ID', db.Integer, db.ForeignKey('SPC界限版本.識別碼'), nullable=False
    )
    study_version_id = db.Column(
        '研究版本ID', db.Integer, db.ForeignKey('SPC研究版本.識別碼'), nullable=False
    )
    sample_id = db.Column(
        '研究樣本ID', db.Integer, db.ForeignKey('SPC研究樣本.識別碼'), nullable=True
    )
    chart_kind = db.Column('圖別', db.String(20), nullable=False)
    rule_code = db.Column('規則代碼', db.String(50), nullable=False)
    point_index = db.Column('點序號', db.Integer, nullable=False)
    source_point_key = db.Column('來源資料點鍵', db.String(256), nullable=True)
    observed_value = db.Column('觀測值', db.Numeric(18, 8), nullable=True)
    status = db.Column('狀態', db.String(30), nullable=False, default='open')
    created_at = db.Column(
        '建立時間', db.DateTime(timezone=True), nullable=False, default=utc_now
    )

    limit_version = db.relationship('SpcLimitVersion', back_populates='events')
    ocap = db.relationship(
        'SpcOcap', back_populates='event', uselist=False,
        cascade='all, delete-orphan',
    )


class SpcOcap(db.Model):
    """失控反應計畫（OCAP）的調查、處置與效果確認紀錄。"""

    __tablename__ = 'SPC異常處置'
    __table_args__ = (
        db.CheckConstraint(
            '"狀態" IN (\'open\', \'closed\')',
            name='ck_spc_ocap_status',
        ),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    event_id = db.Column(
        '事件ID', db.Integer, db.ForeignKey('SPC事件.識別碼'),
        nullable=False, unique=True,
    )
    investigation_6m = db.Column('6M調查', JsonType, nullable=True)
    remeasurement = db.Column('重新量測', JsonType, nullable=True)
    process_adjustment = db.Column('製程調整', db.Text, nullable=True)
    product_disposition = db.Column('產品處置', db.Text, nullable=True)
    owner_id = db.Column(
        '負責人ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    effectiveness = db.Column('效果確認', db.Text, nullable=True)
    status = db.Column('狀態', db.String(30), nullable=False, default='open')
    created_by = db.Column(
        '建立者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    updated_by = db.Column(
        '更新者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    created_at = db.Column(
        '建立時間', db.DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at = db.Column(
        '更新時間', db.DateTime(timezone=True), nullable=False,
        default=utc_now, onupdate=utc_now,
    )

    event = db.relationship('SpcEvent', back_populates='ocap')


class SpcValidationRun(db.Model):
    """SPC 軟體確效執行結果，保存基準資料與容許誤差以供稽核。"""

    __tablename__ = 'SPC軟體確效執行'
    __table_args__ = (
        db.CheckConstraint(
            '"執行結果" IN (\'PASS\', \'FAIL\')',
            name='ck_spc_validation_result',
        ),
    )

    id = db.Column('識別碼', db.Integer, primary_key=True)
    dataset_version = db.Column('基準資料版本', db.String(80), nullable=False)
    method_version = db.Column('方法版本', db.String(30), nullable=False)
    code_version = db.Column('程式版本', db.String(80), nullable=False)
    expected = db.Column('預期結果', JsonType, nullable=False)
    actual = db.Column('實際結果', JsonType, nullable=False)
    tolerances = db.Column('容許誤差', JsonType, nullable=False)
    result = db.Column('執行結果', db.String(20), nullable=False)
    details = db.Column('差異明細', JsonType, nullable=False, default=list)
    executed_by = db.Column(
        '執行者ID', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True
    )
    executed_at = db.Column(
        '執行時間', db.DateTime(timezone=True), nullable=False, default=utc_now
    )


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
    # AIAG-VDA SPC 2026 表 8-3：特性重要度（關鍵/主要/次要/其他）決定能力指數目標值
    characteristic_class = db.Column('特性重要度', db.String(10), default='其他')

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
    # AIAG-VDA SPC 2026 表 8-3：特性重要度（關鍵/主要/次要/其他）決定能力指數目標值
    characteristic_class = db.Column('特性重要度', db.String(10), default='其他')

class NCMR(SoftDeleteMixin, db.Model):
    __tablename__ = '不合格品單'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    ncmr_number = db.Column('NCMR單號', db.String, unique=True, index=True)
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

    __table_args__ = (
        db.Index('idx_ncmr_status_date', '狀態', '發現日期'),
    )

    inspector = db.relationship('Inspector', backref='ncmr_list')
    corrective_actions = db.relationship('CorrectiveAction', backref='ncmr', cascade="all, delete-orphan")
    rework_requests = db.relationship('ReworkRequest', backref='ncmr', cascade="all, delete-orphan")
    dispositions = db.relationship('NcmrDisposition', backref='ncmr',
                                   cascade="all, delete-orphan")

class NcmrDisposition(db.Model):
    """不合格品處置明細 — 一張 NCMR 可有多筆處置（IATF 16949 §8.7）"""
    __tablename__ = '不合格品處置明細'
    __table_args__ = (
        db.Index('idx_ncmr_disp_ncmr', 'NCMR_ID'),
        db.Index('idx_ncmr_disp_risk', '是否風險項'),
    )

    id          = db.Column('識別碼',   db.Integer, primary_key=True)
    ncmr_id     = db.Column('NCMR_ID', db.Integer, db.ForeignKey('不合格品單.識別碼'), nullable=False)
    disposition_type = db.Column('處置類型', db.String(20), nullable=False)
    # '矯正重工' | '報廢' | '挑選全檢' | '讓步放行'
    quantity    = db.Column('處置數量', db.Integer, nullable=False)
    handler_id  = db.Column('處置人',   db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    handled_at  = db.Column('處置時間', db.DateTime, default=utc_now)
    note        = db.Column('備註',     db.Text, nullable=True)

    # 矯正重工專屬
    rework_id   = db.Column('關聯重工單ID', db.Integer, db.ForeignKey('重工申請單.識別碼'), nullable=True)

    # 挑選全檢專屬
    pass_qty    = db.Column('合格數',   db.Integer, nullable=True)
    fail_qty    = db.Column('不合格數', db.Integer, nullable=True)

    # 讓步放行專屬
    exceed_customer_spec = db.Column('是否超出客戶規格', db.Boolean, default=False)
    auth_status     = db.Column('授權狀態',       db.String(10), nullable=True)  # '已取得' | '未取得'
    auth_doc_no     = db.Column('授權文號',       db.String(100), nullable=True)
    auth_valid_until= db.Column('授權有效期',     db.Date, nullable=True)
    auth_max_qty    = db.Column('授權數量上限',   db.Integer, nullable=True)
    unauth_reason   = db.Column('未授權放行理由', db.Text, nullable=True)
    is_risk         = db.Column('是否風險項',     db.Boolean, default=False, nullable=False)

    handler = db.relationship('Inspector', foreign_keys=[handler_id])
    rework  = db.relationship('ReworkRequest', foreign_keys=[rework_id])

class CorrectiveAction(SoftDeleteMixin, db.Model):
    """異常矯正單 — CAPA（我方執行矯正，含 D0-D8 完整 8D 流程）"""
    __tablename__ = '異常矯正單'

    def __init__(self, **kwargs):
        # 舊版 CAR 欄位已移除；保留建構參數相容，避免舊匯入/測試資料建立時中斷。
        kwargs.pop('car_number', None)
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise TypeError(f"'{key}' is an invalid keyword argument for CorrectiveAction")
            setattr(self, key, value)

    id = db.Column('識別碼', db.Integer, primary_key=True)
    eight_d_number = db.Column('8D單號', db.String, unique=True, index=True)
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
    d0_criteria  = db.Column('D0_判斷準則',   JsonType,   nullable=True)   # list of strings
    d0_severity  = db.Column('D0_嚴重度',     db.String(20), nullable=True)  # Critical|Major|Minor
    d0_deadline  = db.Column('D0_客戶要求結案日', db.Date, nullable=True)

    # --- D1 小組（結構化）---
    d1_champion_id = db.Column('D1_Champion', db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    d1_leader_id   = db.Column('D1_Leader',   db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    d1_members     = db.Column('D1_成員',     JsonType, nullable=True)     # list of inspector ids
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
    d4_five_why     = db.Column('D4_5Why資料',    JsonType, nullable=True)  # [{q,a}, ...]
    d4_fishbone     = db.Column('D4_魚骨圖資料',  JsonType, nullable=True)  # {man:[],machine:[],material:[],method:[],measurement:[],environment:[]}
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
    d7_actions = db.Column('D7_橫展類型', JsonType, nullable=True)
    # [{type:'pfmea'|'control_plan'|'sop'|'training'|'cross_part'|'customer_notify'|'other',
    #   task_id:int, assignee_id:int, due_date:'YYYY-MM-DD', part_nos:[str]}]
    d7 = db.Column('D7_預防再發', db.Text, nullable=True)

    # --- D8 結案 ---
    d8_close_date   = db.Column('D8_結案日期',   db.Date, nullable=True)
    d8_confirmation = db.Column('D8_結案確認',   db.Text, nullable=True)
    d8_recognition  = db.Column('D8_團隊表揚',   db.Text, nullable=True)

    # --- 時間戳 ---
    created_at = db.Column('建立時間', db.DateTime, default=utc_now)
    closed_at  = db.Column('結案日期_舊', db.DateTime, nullable=True)

    __table_args__ = (
        db.Index('idx_capa_source', '來源類型', '來源ID'),
        db.Index('idx_capa_status_deadline', '狀態', 'D0_客戶要求結案日'),
    )

    # --- 關聯 ---
    owner     = db.relationship('Inspector', foreign_keys=[owner_id],       backref='cars')
    champion  = db.relationship('Inspector', foreign_keys=[d1_champion_id], backref='capa_champion')
    leader    = db.relationship('Inspector', foreign_keys=[d1_leader_id],   backref='capa_leader')
    tasks     = db.relationship('ActionTask', backref='capa',
                                primaryjoin="and_(ActionTask.source_type=='capa', "
                                            "foreign(ActionTask.source_id)==CorrectiveAction.id)",
                                lazy='dynamic')

class ReworkRequest(SoftDeleteMixin, db.Model):
    __tablename__ = '重工申請單'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    ncmr_id = db.Column('NCMR_ID', db.Integer, db.ForeignKey('不合格品單.識別碼'))
    rework_number = db.Column('申請單號', db.String, unique=True)
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
    
    created_at = db.Column('申請日期', db.DateTime, default=utc_now)
    actual_finish_date = db.Column('實際完成日期', db.DateTime)
    complaint_id = db.Column('客訴_ID', db.Integer, nullable=True)
    vendor = db.Column('廠商', db.String, nullable=True)
    material = db.Column('材質', db.String, nullable=True)

    __table_args__ = (
        db.Index('idx_rework_status_created', '狀態', '申請日期'),
    )

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
    created_at = db.Column('記錄時間', db.DateTime, default=utc_now)

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
    created_at = db.Column('記錄日期', db.DateTime, default=utc_now)

    recorder = db.relationship('Inspector', backref='rework_costs')
    rework = db.relationship('ReworkRequest', backref='costs')


# ============================================================
# 1.1 客訴模組
# ============================================================
class CustomerComplaint(SoftDeleteMixin, db.Model):
    """客訴紀錄 — 外部不良（客戶端發現），獨立於 NCMR"""
    __tablename__ = '客訴紀錄'

    id = db.Column('識別碼', db.Integer, primary_key=True)
    complaint_no = db.Column('客訴單號', db.String(50), unique=True, index=True)

    # 基本資訊
    customer        = db.Column('客戶',      db.String(100), nullable=False)
    complaint_date  = db.Column('客訴日期',  db.Date,        nullable=False, index=True)
    material        = db.Column('材質',      db.String(100), nullable=True)
    spec            = db.Column('規格',      db.String(200), nullable=True)
    extrusion_nos   = db.Column('擠製編號',  JsonType,       nullable=True)  # list[str]
    description     = db.Column('不良描述',  db.Text,        nullable=False)
    severity        = db.Column('嚴重度',    db.String(20),  nullable=True)
    defect_category = db.Column('不良類別',  db.String(100), nullable=True)

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

    # 重複客訴警示
    is_repeat   = db.Column('是否重複客訴',   db.Boolean, default=False)
    repeat_refs = db.Column('重複客訴參考單號', JsonType,      nullable=True)

    # 關聯單據
    related_capa_id   = db.Column('關聯CAPA_ID',  db.Integer, nullable=True)
    related_rework_id = db.Column('關聯重工_ID',  db.Integer, nullable=True)

    # 狀態：'待處理' | '處理中' | '已結案'
    status = db.Column('狀態', db.String(20), default='待處理', index=True)

    # 時間戳
    created_by = db.Column('建立人員', db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    created_at = db.Column('建立時間', db.DateTime, default=utc_now)
    updated_at = db.Column('更新時間', db.DateTime, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        db.Index('idx_complaint_repeat_date', '是否重複客訴', '客訴日期'),
    )

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
    part_nos    = db.Column('相關料號', JsonType,          nullable=True)

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
    created_at = db.Column('建立時間', db.DateTime, default=utc_now)
    updated_at = db.Column('更新時間', db.DateTime, default=utc_now, onupdate=utc_now)

    assignee = db.relationship('Inspector', backref='assigned_tasks')


# ============================================================
# 1.3 附件模組（跨模組共用）
# ============================================================
class Attachment(db.Model):
    """共用附件 — 依 entity_type + entity_id + d_step 分類"""
    __tablename__ = '附件'

    id = db.Column('識別碼', db.Integer, primary_key=True)

    # 所屬實體（多型）：'capa'|'task'|'complaint'
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
    purpose     = db.Column('用途',     db.String(30), nullable=True)  # test_data|furnace_data|scan|cert|other
    uploaded_at = db.Column('上傳時間', db.DateTime, default=utc_now)

    uploader = db.relationship('User', backref='attachments', foreign_keys=[uploaded_by])


# ============================================================
# 1.4 廠商績效模組
# ============================================================
class VendorPerformance(db.Model):
    """廠商績效 — 每月計算一次，可重複覆蓋"""
    __tablename__ = '廠商績效'
    __table_args__ = (
        db.UniqueConstraint('廠商_ID', '期間', name='uq_vendor_period'),
    )

    id               = db.Column('識別碼',          db.Integer, primary_key=True)
    vendor_id        = db.Column('廠商_ID',          db.Integer, db.ForeignKey('廠商資料.識別碼'), nullable=False)
    period           = db.Column('期間',             db.String(7),  nullable=False)
    inspection_count = db.Column('檢驗批次數',       db.Integer, default=0)
    defect_count     = db.Column('不良批次數',       db.Integer, default=0)
    defect_rate      = db.Column('缺陷率',           db.Float,   default=0.0)
    capa_count       = db.Column('CAPA件數',         db.Integer, default=0)
    avg_capa_days    = db.Column('平均CAPA結案天數', db.Float,   nullable=True)
    complaint_count  = db.Column('客訴件數',         db.Integer, default=0)
    score            = db.Column('績效評分',         db.Float,   default=100.0)
    calculated_at    = db.Column('計算時間',         db.DateTime, default=utc_now)

    vendor = db.relationship('Vendor', backref='performances')


# ============================================================
# CQI-9 爐溫測試模組
# ============================================================
class Furnace(db.Model):
    """爐子設備主檔 — CQI-9 納管的熱處理爐"""
    __tablename__ = '爐子設備'

    id              = db.Column('識別碼',   db.Integer, primary_key=True)
    code            = db.Column('爐號',     db.String(50), unique=True, nullable=False)
    name            = db.Column('名稱',     db.String(100), nullable=False)
    process_type    = db.Column('製程類型', db.String(20), nullable=True)   # T6時效/T4/退火
    tus_points      = db.Column('TUS點數',  db.Integer, default=12)
    sat_points      = db.Column('SAT點數',  db.Integer, default=2)
    tus_freq_months = db.Column('TUS頻率_月', db.Integer, default=3)        # 每季=3
    sat_freq_months = db.Column('SAT頻率_月', db.Integer, default=3)
    tus_tolerance   = db.Column('TUS允許公差', db.Numeric(6, 2), nullable=True)  # ±°C
    sat_tolerance   = db.Column('SAT允許誤差', db.Numeric(6, 2), nullable=True)  # ±°C
    work_zone       = db.Column('有效加熱區尺寸', db.String(100), nullable=True)
    instrument_type = db.Column('儀器型式', db.String(10), nullable=True)   # CQI-9 A~E
    cqi9_class      = db.Column('CQI9等級', db.String(10), nullable=True)   # 1~6
    is_active       = db.Column('啟用狀態', db.Boolean, default=True, nullable=False)
    note            = db.Column('備註',     db.Text, nullable=True)
    created_at      = db.Column('建立時間', db.DateTime(timezone=True), default=utc_now)
    updated_at      = db.Column('更新時間', db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f'<Furnace {self.code}>'


class PyrometryTest(SoftDeleteMixin, db.Model):
    """爐溫測試主檔 — 每次 TUS 或 SAT 一筆"""
    __tablename__ = '爐溫測試'

    id              = db.Column('識別碼',       db.Integer, primary_key=True)
    furnace_id      = db.Column('爐子ID',       db.Integer, db.ForeignKey('爐子設備.識別碼'), nullable=False)
    test_type       = db.Column('測試類型',     db.String(10), nullable=False)   # TUS / SAT
    quarter         = db.Column('季別',         db.String(10), nullable=True)    # 2026Q2
    test_date       = db.Column('測試日期',     db.Date, nullable=False, index=True)
    setpoint        = db.Column('設定溫度',     db.Numeric(8, 2), nullable=False)
    tolerance       = db.Column('允許公差',     db.Numeric(6, 2), nullable=True)
    tester_id       = db.Column('測試人員',     db.Integer, db.ForeignKey('品管人員.識別碼'), nullable=True)
    test_instrument = db.Column('測試儀器編號', db.String(100), nullable=True)
    std_instrument  = db.Column('標準校正儀器編號', db.String(100), nullable=True)
    cal_due_date    = db.Column('儀器校正到期日', db.Date, nullable=True)
    is_pass         = db.Column('是否合格',     db.Boolean, default=False, index=True)
    tus_range       = db.Column('TUS均勻度極差', db.Numeric(8, 2), nullable=True)
    tus_max_pos     = db.Column('TUS最大正偏差', db.Numeric(8, 2), nullable=True)
    tus_max_neg     = db.Column('TUS最大負偏差', db.Numeric(8, 2), nullable=True)
    chart_data      = db.Column('曲線資料',     db.JSON, nullable=True)   # 時間序列原始數據（供曲線/詳細表重現）
    report_meta     = db.Column('報告欄位',     db.JSON, nullable=True)   # QRA073/074 報告表頭欄位（客戶/料號/核准等）
    note            = db.Column('備註',         db.Text, nullable=True)
    created_by      = db.Column('建立人',       db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    created_at      = db.Column('建立時間',     db.DateTime(timezone=True), default=utc_now)
    updated_at      = db.Column('更新時間',     db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        db.Index('idx_pyro_furnace_type_date', '爐子ID', '測試類型', '測試日期'),
    )

    furnace    = db.relationship('Furnace', backref='tests')
    tester     = db.relationship('Inspector', foreign_keys=[tester_id])
    tus_points = db.relationship('TusPoint', backref='test', cascade='all, delete-orphan')
    sat_points = db.relationship('SatPoint', backref='test', cascade='all, delete-orphan')


class TusPoint(db.Model):
    """TUS 量測點明細 — 每筆=一支熱電偶"""
    __tablename__ = 'TUS量測點明細'

    id         = db.Column('識別碼',   db.Integer, primary_key=True)
    test_id    = db.Column('測試ID',   db.Integer, db.ForeignKey('爐溫測試.識別碼'), nullable=False)
    position   = db.Column('點位',     db.String(20), nullable=True)
    tc_no      = db.Column('熱電偶編號', db.String(50), nullable=True)
    channel    = db.Column('頻道',     db.SmallInteger, nullable=True)   # 記錄器頻道編號
    correction = db.Column('修正值',   db.Numeric(8, 2), nullable=True)
    temp_max   = db.Column('最高溫',   db.Numeric(8, 2), nullable=True)
    temp_min   = db.Column('最低溫',   db.Numeric(8, 2), nullable=True)
    max_dev    = db.Column('最大偏差', db.Numeric(8, 2), nullable=True)
    is_pass    = db.Column('是否合格', db.Boolean, default=True)
    excluded       = db.Column('已排除',   db.Boolean, nullable=False, default=False)
    exclude_reason = db.Column('排除原因', db.Text, nullable=True)


class SatPoint(db.Model):
    """SAT 量測點明細 — 每筆=一個控溫區，包含多筆取樣讀值"""
    __tablename__ = 'SAT量測點明細'

    id           = db.Column('識別碼',         db.Integer, primary_key=True)
    test_id      = db.Column('測試ID',         db.Integer, db.ForeignKey('爐溫測試.識別碼'), nullable=False)
    zone          = db.Column('控溫區',         db.String(20), nullable=True)
    channel       = db.Column('頻道',           db.SmallInteger, nullable=True)   # 記錄器頻道編號
    control_read  = db.Column('控制儀表讀值',   db.Numeric(8, 2), nullable=True)  # 舊格式相容保留
    test_read     = db.Column('校正測試讀值',   db.Numeric(8, 2), nullable=True)  # 舊格式相容保留
    readings      = db.Column('量測讀值',       JsonType, nullable=True)          # 新格式：多讀值陣列
    diff          = db.Column('差值',           db.Numeric(8, 2), nullable=True)
    correction    = db.Column('修正值',         db.Numeric(8, 2), nullable=True)
    deviation     = db.Column('偏差',           db.Numeric(8, 2), nullable=True)
    is_pass       = db.Column('是否合格',       db.Boolean, default=True)
    excluded       = db.Column('已排除',   db.Boolean, nullable=False, default=False)
    exclude_reason = db.Column('排除原因', db.Text, nullable=True)


class Recorder(db.Model):
    """溫度記錄器主檔 — 18 頻道無紙記錄器，含熱電偶線補正值與校正資料"""
    __tablename__ = '記錄器'

    id             = db.Column('識別碼',     db.Integer, primary_key=True)
    serial         = db.Column('編號',       db.String(50), unique=True, nullable=False)  # 序號
    cal_date       = db.Column('校正日期',   db.Date, nullable=True)
    cal_due_date   = db.Column('到期日',     db.Date, nullable=True)
    tc_correction  = db.Column('熱電偶補正值', db.Numeric(6, 2), default=0)   # 熱電偶線補正，預設 -1.15
    is_active      = db.Column('啟用狀態',   db.Boolean, default=True, nullable=False)
    note           = db.Column('備註',       db.Text, nullable=True)
    created_at     = db.Column('建立時間',   db.DateTime(timezone=True), default=utc_now)
    updated_at     = db.Column('更新時間',   db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    cal_points = db.relationship('RecorderCalPoint', backref='recorder', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Recorder {self.serial}>'


class RecorderCalPoint(db.Model):
    """記錄器校正點 — 每筆=某頻道在某標準溫度下的器差值（器示值−標準值）"""
    __tablename__ = '記錄器校正點'

    id          = db.Column('識別碼',   db.Integer, primary_key=True)
    recorder_id = db.Column('記錄器ID', db.Integer, db.ForeignKey('記錄器.識別碼'), nullable=False)
    channel     = db.Column('頻道',     db.Integer, nullable=False)        # 1~18
    std_temp    = db.Column('標準溫度', db.Numeric(8, 2), nullable=False)  # 100~600
    error       = db.Column('器差值',   db.Numeric(8, 2), nullable=False)  # 器示值−標準值

    __table_args__ = (
        db.Index('idx_recorder_cal', '記錄器ID', '頻道', '標準溫度'),
    )


class Thermocouple(db.Model):
    """熱電偶線主檔 — 作為量測基準的熱電偶，含一條校正曲線（隨溫度內插）"""
    __tablename__ = '熱電偶'

    id           = db.Column('識別碼',   db.Integer, primary_key=True)
    serial       = db.Column('編號',     db.String(50), unique=True, nullable=False)  # 序號
    tc_type      = db.Column('型式',     db.String(20), nullable=True)    # TYPE K 等
    cal_date     = db.Column('校正日期', db.Date, nullable=True)
    cal_due_date = db.Column('到期日',   db.Date, nullable=True)
    is_active    = db.Column('啟用狀態', db.Boolean, default=True, nullable=False)
    note         = db.Column('備註',     db.Text, nullable=True)
    created_at   = db.Column('建立時間', db.DateTime(timezone=True), default=utc_now)
    updated_at   = db.Column('更新時間', db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    cal_points = db.relationship('ThermocoupleCalPoint', backref='thermocouple', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Thermocouple {self.serial}>'


class ThermocoupleCalPoint(db.Model):
    """熱電偶校正點 — 每筆=某標準溫度下的器差值（器示值−標準值）"""
    __tablename__ = '熱電偶校正點'

    id              = db.Column('識別碼',     db.Integer, primary_key=True)
    thermocouple_id = db.Column('熱電偶ID',   db.Integer, db.ForeignKey('熱電偶.識別碼'), nullable=False)
    std_temp        = db.Column('標準溫度',   db.Numeric(8, 2), nullable=False)
    error           = db.Column('器差值',     db.Numeric(8, 2), nullable=False)

    __table_args__ = (
        db.Index('idx_thermocouple_cal', '熱電偶ID', '標準溫度'),
    )


# SPC 計算證據採 append-only。狀態欄位可依生命週期轉換，但已保存的輸入、
# 計算結果、界限與事件識別內容不得由 ORM 原地覆寫或刪除。
_SPC_MUTABLE_FIELDS = {
    SpcStudyVersion: {"status"},
    SpcStudySample: set(),
    SpcLimitVersion: {"status", "retired_by", "retired_at"},
    SpcEvent: {"status"},
}


def _block_spc_immutable_update(_mapper, _connection, target):
    state = inspect(target)
    allowed = _SPC_MUTABLE_FIELDS[type(target)]
    changed = {
        attribute.key
        for attribute in state.mapper.column_attrs
        if attribute.key not in allowed
        and state.attrs[attribute.key].history.has_changes()
    }
    if changed:
        names = "、".join(sorted(changed))
        raise ValueError(f"SPC 不可變證據禁止原地修改：{names}")


def _block_spc_immutable_delete(_mapper, _connection, target):
    raise ValueError(f"SPC 不可變證據禁止刪除：{type(target).__name__}")


for _spc_model in _SPC_MUTABLE_FIELDS:
    event.listen(_spc_model, "before_update", _block_spc_immutable_update)
    event.listen(_spc_model, "before_delete", _block_spc_immutable_delete)

# OCAP 內容允許由受控服務逐步補充，但既有處置證據不得刪除。
event.listen(SpcOcap, "before_delete", _block_spc_immutable_delete)


class MechanicalTest(db.Model):
    """機械性質檢驗 — 一筆對應原 Excel 一欄測試紀錄"""
    __tablename__ = '機械性質檢驗'

    id            = db.Column('識別碼',      db.Integer, primary_key=True)
    product_size  = db.Column('產品尺寸',    db.String(50), nullable=False, index=True)
    material      = db.Column('材質',        db.String(50), nullable=False, index=True)
    vendor_id     = db.Column('廠商ID',      db.Integer, db.ForeignKey('廠商資料.識別碼'), nullable=True)
    test_date     = db.Column('測試日期',    db.Date, nullable=True, index=True)
    t4_temp_time  = db.Column('T4溫度時間',  db.String(100), nullable=True)
    t6_temp_time  = db.Column('T6溫度時間',  db.String(100), nullable=True)
    note          = db.Column('備註',        db.String, nullable=True)
    is_ng         = db.Column('是否NG',      db.Boolean, default=False, nullable=False)
    created_at    = db.Column('建立日期',    db.DateTime(timezone=True), default=utc_now)
    created_by    = db.Column('建立者ID',    db.Integer, db.ForeignKey('使用者.識別碼'), nullable=True)
    updated_at    = db.Column('更新日期',    db.DateTime(timezone=True), onupdate=utc_now)

    trace_numbers = db.relationship(
        "MechanicalTraceNumber",
        backref="test",
        cascade="all, delete-orphan",
        order_by="MechanicalTraceNumber.trace_type, MechanicalTraceNumber.seq",
    )
    # Task 2 完成 service 切換前，暫留舊配對關聯以維持過渡期間可執行。
    batches = db.relationship(
        'MechanicalBatch', backref='test', cascade="all, delete-orphan"
    )
    measurements = db.relationship(
        'MechanicalMeasurement', backref='test', cascade="all, delete-orphan"
    )
    vendor = db.relationship('Vendor')


class MechanicalTraceNumber(db.Model):
    """機械性質追溯編號；兩種類型各自排序，不保存彼此配對。"""

    __tablename__ = "機械性質追溯編號"
    __table_args__ = (
        db.UniqueConstraint(
            "機械性質檢驗_ID", "類型", "序號", name="uq_mech_trace_seq"
        ),
        db.UniqueConstraint(
            "機械性質檢驗_ID", "類型", "編號", name="uq_mech_trace_value"
        ),
        db.CheckConstraint(
            "\"類型\" IN ('擠製編號', 'T4爐號')",
            name="ck_mech_trace_type",
        ),
        db.CheckConstraint(
            "\"序號\" >= 1",
            name="ck_mech_trace_seq_positive",
        ),
        db.CheckConstraint(
            "length(trim(\"編號\")) BETWEEN 1 AND 100",
            name="ck_mech_trace_number",
        ),
        db.Index("ix_mech_trace_test_id", "機械性質檢驗_ID"),
    )

    id = db.Column("識別碼", db.Integer, primary_key=True)
    test_id = db.Column(
        "機械性質檢驗_ID",
        db.Integer,
        db.ForeignKey("機械性質檢驗.識別碼", ondelete="CASCADE"),
        nullable=False,
    )
    trace_type = db.Column("類型", db.String(20), nullable=False)
    seq = db.Column("序號", db.Integer, nullable=False)
    number = db.Column("編號", db.String(100), nullable=False)


class MechanicalBatch(db.Model):
    """機械性質批次 — 一列對應一組（擠製編號 + 爐具編號），可多組"""
    __tablename__ = '機械性質批次'
    __table_args__ = (
        db.UniqueConstraint('機械性質檢驗_ID', '序號', name='uq_mech_batch_seq'),
        db.CheckConstraint('"序號" >= 1', name='ck_mech_batch_seq_positive'),
        db.Index('idx_mech_batch_test_id', '機械性質檢驗_ID'),
    )

    id           = db.Column('識別碼',        db.Integer, primary_key=True)
    test_id      = db.Column('機械性質檢驗_ID', db.Integer,
                             db.ForeignKey('機械性質檢驗.識別碼', ondelete='CASCADE'), nullable=False)
    seq          = db.Column('序號',          db.Integer, nullable=False, default=1)
    extrusion_no = db.Column('擠製編號',      db.String(100), nullable=True)
    furnace_no   = db.Column('爐具編號',      db.String(100), nullable=True)


class MechanicalMeasurement(db.Model):
    """機械性質量測明細 — 一列對應一個（項目×位置×取樣序）量測值"""
    __tablename__ = '機械性質量測明細'
    __table_args__ = (
        db.UniqueConstraint('機械性質檢驗_ID', '量測項目', '測量位置', '取樣序',
                            name='uq_mech_group_item'),
        db.CheckConstraint(
            '"量測項目" IN (\'EC值\', \'硬度\', \'抗拉強度\', \'降伏強度\', \'伸長率\')',
            name='ck_mech_measurement_item',
        ),
        db.CheckConstraint('"測量位置" IN (\'爐門\', \'爐頂\')', name='ck_mech_measurement_location'),
        db.CheckConstraint('"取樣序" IN (1, 2)', name='ck_mech_measurement_sample'),
        db.Index('idx_mech_meas_test_id', '機械性質檢驗_ID'),
    )

    id          = db.Column('識別碼',        db.Integer, primary_key=True)
    test_id     = db.Column('機械性質檢驗_ID', db.Integer,
                            db.ForeignKey('機械性質檢驗.識別碼', ondelete='CASCADE'), nullable=False)
    item        = db.Column('量測項目',      db.String(20), nullable=False)
    location    = db.Column('測量位置',      db.String(10), nullable=False)
    sample_no   = db.Column('取樣序',        db.Integer, nullable=False)
    value       = db.Column('量測值',        db.Numeric(12, 4), nullable=True)
    lower_limit = db.Column('下限',          db.Numeric(12, 4), nullable=True)
    is_ng       = db.Column('是否超差',      db.Boolean, default=False, nullable=False)
    # §6.6 離群值：標示無效並保留追溯，不得刪除；排除於統計計算之外
    excluded          = db.Column('排除統計', db.Boolean, default=False, nullable=False)
    exclusion_reason  = db.Column('排除原因', db.String(200), nullable=True)
    exclusion_user_id = db.Column('排除者ID', db.Integer,
                                  db.ForeignKey('使用者.識別碼'), nullable=True)
    excluded_at       = db.Column('排除時間', db.DateTime(timezone=True), nullable=True)
