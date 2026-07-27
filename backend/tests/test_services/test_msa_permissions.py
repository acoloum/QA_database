"""MSA 權限種子的回歸測試。"""

from backend.seeds.seed_roles import ROLES


def _permissions(role_code: str) -> dict:
    return next(role["permissions"] for role in ROLES if role["code"] == role_code)


def test_msa_permissions_follow_separation_of_duties():
    assert _permissions("inspector")["msa.execute"] is True
    assert _permissions("qa_supervisor")["msa.manage"] is True
    assert "msa.approve" not in _permissions("qa_supervisor")
    assert _permissions("qc_manager")["msa.approve"] is True
    assert _permissions("admin")["msa.approve"] is True
