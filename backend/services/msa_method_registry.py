"""第四版 MSA 受控方法 registry。

正式結果只能由這裡登錄的 method code/version 產生。統計引擎以模組
路徑延遲解析，讓 registry 可以先於個別引擎存在，也避免匯入循環。
"""

from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType

from .msa_errors import MsaValidationError


# 第四版正式研究一律使用 6σ 表示研究變差；5.15σ 只能存在明確 legacy 版本。
FOURTH_EDITION_SIGMA_MULTIPLIER = 6.0
DEFAULT_ALPHA = 0.05


@dataclass(frozen=True)
class MethodDescriptor:
    """單一受控統計方法的版本、設計下限與互動處理政策。"""

    code: str
    version: str
    engine_ref: str
    alpha: float
    study_variation_multiplier: float
    minimum_design: MappingProxyType
    supports_unbalanced: bool
    interaction_policy: str

    @property
    def engine(self):
        """延遲解析統計引擎；引擎必須是不查資料庫的純函式。"""
        module_path, _, function_name = self.engine_ref.partition(":")
        try:
            module = import_module(module_path)
            return getattr(module, function_name)
        except (ImportError, AttributeError) as error:
            raise MsaValidationError(
                "MSA_METHOD_ENGINE_UNAVAILABLE",
                "受控方法尚未提供可用的統計引擎",
                details={"method_code": self.code, "engine": self.engine_ref},
            ) from error

    def as_dict(self) -> dict:
        """納入分析輸入指紋的受控方法描述。"""
        return {
            "code": self.code,
            "version": self.version,
            "engine": self.engine_ref,
            "alpha": self.alpha,
            "study_variation_multiplier": self.study_variation_multiplier,
            "minimum_design": dict(self.minimum_design),
            "supports_unbalanced": self.supports_unbalanced,
            "interaction_policy": self.interaction_policy,
        }

    def design_shortfalls(self, design) -> list[dict]:
        """回傳未達方法設計下限的維度；全部達標時回傳空清單。"""
        values = design or {}
        shortfalls = []
        for dimension, required in self.minimum_design.items():
            actual = values.get(dimension) or 0
            if actual < required:
                shortfalls.append(
                    {
                        "dimension": dimension,
                        "required": required,
                        "actual": actual,
                    }
                )
        return shortfalls


def _descriptor(
    code: str,
    engine_ref: str,
    minimum_design: dict,
    *,
    supports_unbalanced: bool = False,
    interaction_policy: str = "not_applicable",
    version: str = "1.0",
) -> MethodDescriptor:
    return MethodDescriptor(
        code=code,
        version=version,
        engine_ref=engine_ref,
        alpha=DEFAULT_ALPHA,
        study_variation_multiplier=FOURTH_EDITION_SIGMA_MULTIPLIER,
        minimum_design=MappingProxyType(dict(minimum_design)),
        supports_unbalanced=supports_unbalanced,
        interaction_policy=interaction_policy,
    )


METHODS = {
    "MSA4_GRR_RANGE_1_0": _descriptor(
        "MSA4_GRR_RANGE_1_0",
        "backend.services.msa_variable_grr:analyze_range",
        {"parts": 5, "appraisers": 2, "trials": 1},
    ),
    "MSA4_GRR_XBAR_R_1_0": _descriptor(
        "MSA4_GRR_XBAR_R_1_0",
        "backend.services.msa_variable_grr:analyze_xbar_r",
        {"parts": 2, "appraisers": 2, "trials": 2},
    ),
    "MSA4_GRR_ANOVA_1_0": _descriptor(
        "MSA4_GRR_ANOVA_1_0",
        "backend.services.msa_variable_grr:analyze_crossed_anova",
        {"parts": 2, "appraisers": 2, "trials": 2},
        interaction_policy="reduce_when_p_ge_alpha",
    ),
    "MSA4_BIAS_1_0": _descriptor(
        "MSA4_BIAS_1_0",
        "backend.services.msa_bias_linearity:analyze_bias",
        {"parts": 1, "appraisers": 1, "trials": 10},
    ),
    "MSA4_LINEARITY_1_0": _descriptor(
        "MSA4_LINEARITY_1_0",
        "backend.services.msa_bias_linearity:analyze_linearity",
        {"parts": 5, "appraisers": 1, "trials": 2},
    ),
    "MSA4_STABILITY_1_0": _descriptor(
        "MSA4_STABILITY_1_0",
        "backend.services.msa_stability:analyze_stability",
        {"subgroups": 20, "appraisers": 1, "trials": 1},
    ),
    "MSA4_ATTRIBUTE_1_0": _descriptor(
        "MSA4_ATTRIBUTE_1_0",
        "backend.services.msa_attribute:analyze_attribute",
        {"parts": 20, "appraisers": 2, "trials": 2},
    ),
    "MSA4_NONREPEATABLE_1_0": _descriptor(
        "MSA4_NONREPEATABLE_1_0",
        "backend.services.msa_nonrepeatable:analyze_nonrepeatable",
        {"parts": 10, "appraisers": 2, "trials": 1},
        interaction_policy="design_specific",
    ),
}


class MsaMethodRegistry:
    """唯讀查詢受控方法；未登錄的代碼不得產生正式結果。"""

    @staticmethod
    def get(method_code: str) -> MethodDescriptor:
        descriptor = METHODS.get(method_code)
        if descriptor is None:
            raise MsaValidationError(
                "MSA_METHOD_NOT_REGISTERED",
                "不是受控的 MSA 方法代碼",
                details={
                    "method_code": method_code,
                    "allowed": sorted(METHODS),
                },
            )
        return descriptor

    @staticmethod
    def codes() -> tuple[str, ...]:
        return tuple(sorted(METHODS))


# 研究類型與受控方法的對應；一種類型可有多個可選方法。
_STUDY_TYPE_METHODS = {
    "grr_range": ("MSA4_GRR_RANGE_1_0",),
    "grr_xbar_r": ("MSA4_GRR_XBAR_R_1_0",),
    "grr_anova": ("MSA4_GRR_ANOVA_1_0",),
    "bias": ("MSA4_BIAS_1_0",),
    "linearity": ("MSA4_LINEARITY_1_0",),
    "stability": ("MSA4_STABILITY_1_0",),
    "attribute": ("MSA4_ATTRIBUTE_1_0",),
    "nonreplicable": ("MSA4_NONREPEATABLE_1_0",),
}
