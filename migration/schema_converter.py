# SQL Server 到 PostgreSQL Schema 轉換工具
# 用途：分析 SQL Server DDL 並生成 PostgreSQL 兼容的 CREATE TABLE 語句

import re

def convert_data_type(sql_server_type):
    """轉換 SQL Server 資料型別為 PostgreSQL"""
    type_mapping = {
        'INT': 'INTEGER',
        'BIGINT': 'BIGINT',
        'SMALLINT': 'SMALLINT',
        'TINYINT': 'SMALLINT',  # PostgreSQL 沒有 TINYINT
        'BIT': 'BOOLEAN',
        'DATETIME': 'TIMESTAMP',
        'DATETIME2': 'TIMESTAMP',
        'DATE': 'DATE',
        'TIME': 'TIME',
        'MONEY': 'NUMERIC(19,4)',
        'SMALLMONEY': 'NUMERIC(10,4)',
        'FLOAT': 'DOUBLE PRECISION',
        'REAL': 'REAL',
        'TEXT': 'TEXT',
        'NTEXT': 'TEXT',
        'IMAGE': 'BYTEA',
        'UNIQUEIDENTIFIER': 'UUID',
    }
    
    # 處理帶長度的型別
    if match := re.match(r'NVARCHAR\((\d+|MAX)\)', sql_server_type, re.IGNORECASE):
        length = match.group(1)
        return 'TEXT' if length == 'MAX' else f'VARCHAR({length})'
    
    if match := re.match(r'VARCHAR\((\d+|MAX)\)', sql_server_type, re.IGNORECASE):
        length = match.group(1)
        return 'TEXT' if length == 'MAX' else f'VARCHAR({length})'
    
    if match := re.match(r'CHAR\((\d+)\)', sql_server_type, re.IGNORECASE):
        return f'CHAR({match.group(1)})'
    
    if match := re.match(r'NCHAR\((\d+)\)', sql_server_type, re.IGNORECASE):
        return f'CHAR({match.group(1)})'
    
    if match := re.match(r'DECIMAL\((\d+),\s*(\d+)\)', sql_server_type, re.IGNORECASE):
        return f'NUMERIC({match.group(1)},{match.group(2)})'
    
    if match := re.match(r'NUMERIC\((\d+),\s*(\d+)\)', sql_server_type, re.IGNORECASE):
        return f'NUMERIC({match.group(1)},{match.group(2)})'
    
    # 查表映射
    upper_type = sql_server_type.upper()
    return type_mapping.get(upper_type, sql_server_type)


def convert_identity_to_serial(column_def):
    """將 IDENTITY 轉換為 SERIAL"""
    # 匹配 IDENTITY(1,1) 或 IDENTITY
    if re.search(r'IDENTITY', column_def, re.IGNORECASE):
        # 替換 INT IDENTITY 為 SERIAL
        column_def = re.sub(r'INT\s+IDENTITY.*', 'SERIAL', column_def, flags=re.IGNORECASE)
        column_def = re.sub(r'BIGINT\s+IDENTITY.*', 'BIGSERIAL', column_def, flags=re.IGNORECASE)
    return column_def


def convert_default_value(default_value):
    """轉換預設值"""
    if not default_value:
        return None
    
    conversions = {
        'GETDATE()': 'CURRENT_TIMESTAMP',
        'NEWID()': 'gen_random_uuid()',  # 需要 pgcrypto 擴充
    }
    
    for old, new in conversions.items():
        default_value = default_value.replace(old, new)
    
    return default_value


# 範例使用
if __name__ == '__main__':
    print("SQL Server 到 PostgreSQL 型別轉換範例：")
    print(f"NVARCHAR(100) -> {convert_data_type('NVARCHAR(100)')}")
    print(f"DATETIME -> {convert_data_type('DATETIME')}")
    print(f"BIT -> {convert_data_type('BIT')}")
    print(f"INT IDENTITY(1,1) -> {convert_identity_to_serial('INT IDENTITY(1,1)')}")
