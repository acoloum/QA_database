"""MSA 權限名稱的單一來源，供後續 route 與 service 採用。"""

MSA_PERMISSION_CODES = frozenset(
    {
        "msa.execute",
        "msa.manage",
        "msa.approve",
    }
)
