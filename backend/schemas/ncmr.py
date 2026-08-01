"""NCMR 建立與更新的正式輸入契約。"""

from marshmallow import (
    INCLUDE,
    RAISE,
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
)


class IntegerWithoutBoolean(fields.Integer):
    """整數欄位，但拒絕 Python 將布林值視為 0／1 的隱式轉換。"""

    def _deserialize(self, value, attr, data, **kwargs):
        if isinstance(value, bool):
            raise ValidationError('不是有效的整數。')
        return super()._deserialize(value, attr, data, **kwargs)


class NCMRFieldsSchema(Schema):
    """NCMR 共用欄位；requiredness 由 create/update schema 各自決定。"""

    class Meta:
        unknown = RAISE

    日期 = fields.Date(allow_none=True)
    建立日期 = fields.Date(allow_none=True)
    來源 = fields.String(allow_none=True, validate=validate.Length(min=1, max=100))
    廠商 = fields.String(allow_none=True, validate=validate.Length(max=200))
    材質 = fields.String(allow_none=True, validate=validate.Length(max=100))
    批號 = fields.String(allow_none=True, validate=validate.Length(max=100))
    產品資訊 = fields.String(allow_none=True, validate=validate.Length(max=500))
    產品數量 = IntegerWithoutBoolean(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    不良描述 = fields.String(allow_none=True, validate=validate.Length(max=5000))
    不合格數量 = IntegerWithoutBoolean(
        allow_none=True,
        validate=validate.Range(min=0),
    )
    發現人員姓名 = fields.String(allow_none=True, validate=validate.Length(max=200))
    判定結果 = fields.String(allow_none=True, validate=validate.Length(max=500))
    狀態 = fields.String(allow_none=True, validate=validate.Length(max=100))
    不良原因大類 = fields.String(allow_none=True, validate=validate.Length(max=200))
    不良原因細項 = fields.String(allow_none=True, validate=validate.Length(max=1000))

    @pre_load
    def normalize_optional_integer_blanks(self, data, **kwargs):
        """相容既有表單的空字串數量，同時不放寬其他型別。"""
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        for key in ('產品數量', '不合格數量'):
            if normalized.get(key) == '':
                normalized[key] = None
        return normalized


class NCMRCreateSchema(NCMRFieldsSchema):
    """建立 NCMR；沿用既有業務要求日期與來源必填。"""

    日期 = fields.Date(required=True)
    來源 = fields.String(required=True, validate=validate.Length(min=1, max=100))


class NCMRUpdateSchema(NCMRFieldsSchema):
    """部分更新 NCMR；僅識別碼必填。"""

    識別碼 = IntegerWithoutBoolean(
        required=True,
        validate=validate.Range(min=1),
    )


class NCMRUpdateIdentifierSchema(Schema):
    """ownership gate 專用：只解析 ID，完整 payload 於授權後驗證。"""

    class Meta:
        unknown = INCLUDE

    識別碼 = IntegerWithoutBoolean(
        required=True,
        validate=validate.Range(min=1),
    )
