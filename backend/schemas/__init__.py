"""HTTP 輸入資料結構與反序列化契約。"""

from .ncmr import NCMRCreateSchema, NCMRUpdateIdentifierSchema, NCMRUpdateSchema

__all__ = [
    'NCMRCreateSchema',
    'NCMRUpdateIdentifierSchema',
    'NCMRUpdateSchema',
]
