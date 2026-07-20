# 巡檢即時量測示警 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 巡檢表單新增「即時模式」，逐格輸入量測值時立即用生效中的 SPC 管制界限判讀是否異常，並提供擠壓模具調整提示；存檔後沿用既有的持續監控流程自動建立正式 OCAP 事件。

**Architecture:** 新增一支唯讀後端 API（`GET /api/patrol/live-limits`）查詢生效中的 `SpcLimitVersion` 與最近歷史值；前端在量測格失焦時，把歷史值＋本次表單已填值組成序列，重用既有的 `spcAnalysis.ts`（`analyzeWECO`/`analyzeRChartWECO`）在瀏覽器內即時判讀（純提示，不寫入資料庫）。存檔成功後，若曾觸發提示，呼叫既有的 `POST /api/spc/studies/analyze`（`study_type=ongoing`，完全不修改）建立正式 `SpcEvent`，並開啟既有的 `SpcOcapOffcanvas`。

**Tech Stack:** Flask + SQLAlchemy（後端）、React + TypeScript + React Query + react-bootstrap（前端）、pytest（後端測試）、vitest + @testing-library/react（前端測試）。

**參考規格文件：** [docs/superpowers/specs/2026-07-20-patrol-realtime-spc-alert-design.md](../specs/2026-07-20-patrol-realtime-spc-alert-design.md)

**與規格文件的差異（撰寫本計畫時確認的實作細節，非範圍變更）：**
1. 規格文件描述的參數是 `machine_id, material, spec, item, position`；實際上「製程流」身分（`process_stream_key`）是由 `canonical_process_stream()` 對 `PATROL_FILTERS = (m_id, op_id, cust_id, mat, spec, item, pos, s_date, e_date)` 做正規化雜湊決定的（見 `backend/services/spc_adapters/common.py`），因此新端點必須額外接受 `op_id`（主機手）與 `cust_id`（客戶），否則查不到既有核准流程建立的界限。這兩個欄位巡檢表單本來就有（主機手、客戶名稱下拉選單），前端直接帶入即可。
2. 規格文件假設界限是扁平的 `x_cl/x_ucl/...` 欄位；實際上 `SpcLimitVersion.limits` 是巢狀 JSON：`{"location": {"cl","ucl","lcl"}, "variation": {"cl","ucl","lcl"}, "scale": "original"|"transformed", ...}`。若 `scale == "transformed"`（分布轉換尺度），本次不支援即時比對，端點回傳 `found: false`（避免對原始量測值套用錯誤尺度的界限）。
3. 每個「組別」在 `PatrolDetail` 是以 `min_val`／`max_val` 兩個觀測值構成一個 n=2 子組（既有 `build_patrol_study_input` 的作法），管制界限是對子組平均數（X̄，即 `(min+max)/2`）與全距（R，即 `max-min`）判讀，不是對單一原始量測值直接判讀。因此即時判讀在「該組同一 item/position 的 min 與 max 都已填入」才會觸發，不是每個欄位各自獨立判讀。

---

## File Structure

**後端：**
- Modify: `backend/services/patrol_service.py` — 新增 `get_live_limits()` 服務方法
- Modify: `backend/routes/patrol.py` — 新增 `GET /api/patrol/live-limits` 路由
- Modify: `backend/tests/test_services/test_patrol.py` — 新增服務層測試
- Create: `backend/tests/test_patrol_live_limits_route.py` — 新增路由層測試（比照 `backend/tests/test_spc_study_routes.py` 的 `_user`/`_headers` 慣例）

**前端：**
- Modify: `src_frontend/src/hooks/usePatrol.ts` — 新增 `usePatrolLiveLimits` 查詢 hook
- Modify: `src_frontend/src/components/patrol/patrolFormUtils.ts` — 新增即時序列組裝、規則提示對照
- Modify: `src_frontend/src/components/patrol/patrolFormUtils.test.ts` — 新增對應測試
- Modify: `src_frontend/src/components/patrol/PatrolMeasurementTable.tsx` — 接受並顯示即時違規標記
- Modify: `src_frontend/src/components/patrol/PatrolMeasurementTable.test.tsx` — 新增對應測試
- Modify: `src_frontend/src/components/patrol/PatrolModal.tsx` — 即時模式開關、失焦判讀、存檔後觸發正式 OCAP 事件
- Modify: `src_frontend/src/components/patrol/PatrolModal.test.tsx` — 新增對應測試

不新增資料表、不修改 `spc_stability.py`、`spc_study_service.py`、`spc_ocap_service.py`、`SpcOcapOffcanvas.tsx`。

---

## Task 1: 後端服務 `PatrolService.get_live_limits()`

**Files:**
- Modify: `backend/services/patrol_service.py`
- Test: `backend/tests/test_services/test_patrol.py`

- [ ] **Step 1: 寫失敗測試 — 找不到生效界限時回傳 `found: false`**

在 `backend/tests/test_services/test_patrol.py` 檔案末尾新增：

```python
def test_get_live_limits_not_found_without_active_limit(app, db_session):
    """該製程流尚未有生效核准界限時，回傳 found=False，不擅自估算界限"""
    with app.app_context():
        result = PatrolService.get_live_limits({
            'mat': 'SUS304', 'spec': '10*2', 'item': '外徑', 'pos': '前段',
        })
        assert result == {'found': False}
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && python -m pytest tests/test_services/test_patrol.py::test_get_live_limits_not_found_without_active_limit -v`
Expected: FAIL，`AttributeError: type object 'PatrolService' has no attribute 'get_live_limits'`

- [ ] **Step 3: 實作 `get_live_limits`（先處理找不到界限的分支）**

在 `backend/services/patrol_service.py` 檔案開頭的 import 區塊，把第 9 行：

```python
from ..models import PatrolMain, PatrolDetail, Machine, Operator, Inspector, Vendor, SPCCache
```

改成：

```python
from ..models import (
    PatrolMain, PatrolDetail, Machine, Operator, Inspector, Vendor, SPCCache,
    SpcLimitVersion,
)
```

在 `class PatrolService:` 內，緊接在既有的 `get_spc`（第 77-81 行）之後新增：

```python
    @staticmethod
    def get_live_limits(args: Dict[str, Any]) -> Dict[str, Any]:
        """巡檢即時模式：查詢生效中的管制界限與最近歷史值（唯讀，不建立稽核紀錄）。

        僅供前端即時提示使用，非正式判定；正式判定仍由存檔後的
        POST /api/spc/studies/analyze（ongoing）產生。
        """
        from collections import OrderedDict
        from .spc_adapters.common import canonical_process_stream

        filters = {
            'm_id': args.get('m_id') or None,
            'op_id': args.get('op_id') or None,
            'cust_id': args.get('cust_id') or None,
            'mat': args.get('mat') or '',
            'spec': args.get('spec') or '',
            'item': args.get('item') or '',
            'pos': args.get('pos') or '',
            's_date': '',
            'e_date': '',
        }
        stream = canonical_process_stream('patrol', filters)
        item = stream.filters['item']

        limit = SpcLimitVersion.query.filter_by(
            analysis_family='variable',
            process_stream_key=stream.key,
            characteristic=item,
            status='active',
        ).first()
        if limit is None:
            return {'found': False}

        limits = limit.limits or {}
        if limits.get('scale') == 'transformed':
            return {'found': False, 'reason': 'transformed_scale_unsupported'}

        location = limits.get('location') or {}
        variation = limits.get('variation') or {}

        query = (
            PatrolDetail.query.join(PatrolMain)
            .filter(PatrolDetail.item == item, PatrolDetail.excluded.is_(False))
        )
        if stream.filters['pos']:
            query = query.filter(PatrolDetail.position == stream.filters['pos'])
        if stream.filters['m_id'] is not None:
            query = query.filter(PatrolMain.machine_id == stream.filters['m_id'])
        if stream.filters['mat']:
            query = query.filter(PatrolMain.material.contains(stream.filters['mat']))
        if stream.filters['spec']:
            query = query.filter(PatrolMain.spec.contains(stream.filters['spec']))
        exclude_main_id = args.get('exclude_main_id')
        if exclude_main_id:
            query = query.filter(PatrolMain.id != int(exclude_main_id))
        details = query.order_by(
            PatrolMain.date.asc(), PatrolDetail.main_id.asc(),
            PatrolDetail.group.asc(), PatrolDetail.id.asc(),
        ).all()

        grouped: 'OrderedDict[tuple, list]' = OrderedDict()
        for detail in details:
            grouped.setdefault((detail.main_id, detail.group), []).append(detail)

        recent_values = []
        for group_details in list(grouped.values())[-14:]:
            values = [
                float(v) for v in (
                    group_details[0].min_val, group_details[0].max_val,
                )
                if v is not None
            ]
            if len(values) == 2:
                recent_values.append({'min': min(values), 'max': max(values)})

        return {
            'found': True,
            'x_cl': float(location['cl']) if location.get('cl') is not None else None,
            'x_ucl': float(location['ucl']) if location.get('ucl') is not None else None,
            'x_lcl': float(location['lcl']) if location.get('lcl') is not None else None,
            'r_cl': float(variation['cl']) if variation.get('cl') is not None else None,
            'r_ucl': float(variation['ucl']) if variation.get('ucl') is not None else None,
            'r_lcl': float(variation['lcl']) if variation.get('lcl') is not None else None,
            'recent_values': recent_values,
        }
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && python -m pytest tests/test_services/test_patrol.py::test_get_live_limits_not_found_without_active_limit -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/services/patrol_service.py backend/tests/test_services/test_patrol.py
git commit -m "$(cat <<'EOF'
新增：巡檢即時模式界限查詢（無生效界限分支）

get_live_limits 先處理找不到生效 SpcLimitVersion 時回傳
found=False，不擅自估算管制界限。
EOF
)"
```

- [ ] **Step 6: 寫失敗測試 — 有生效界限時回傳界限與最近歷史值**

在 `backend/tests/test_services/test_patrol.py` 開頭 import 區塊新增（若尚未匯入）：

```python
from backend.models import SpcStudy, SpcStudyVersion, SpcLimitVersion
from backend.services.spc_adapters.common import canonical_process_stream
```

新增測試：

```python
def _approved_patrol_limit(db_session, *, mat, spec, item, pos):
    """建立一組生效中的巡檢管制界限（比照 approve_study 產出的資料形狀）。"""
    filters = {
        'm_id': None, 'op_id': None, 'cust_id': None,
        'mat': mat, 'spec': spec, 'item': item, 'pos': pos,
        's_date': '', 'e_date': '',
    }
    stream = canonical_process_stream('patrol', filters)
    study = SpcStudy(
        source='patrol', study_type='ongoing', analysis_family='variable',
        process_stream_key=stream.key, characteristic=item, filters={},
        status='active',
    )
    db_session.add(study)
    db_session.flush()
    version = SpcStudyVersion(
        study_id=study.id, version_no=1, method_version='2026.2',
        analysis_options={}, specification_snapshot={}, chart_result={},
        stability_result={}, distribution_result={}, capability_result={},
        applicability_result={}, time_model_result={}, status='active',
    )
    db_session.add(version)
    db_session.flush()
    limit = SpcLimitVersion(
        study_version_id=version.id, analysis_family='variable',
        process_stream_key=stream.key, characteristic=item, revision=1,
        chart_type='xbar_r',
        limits={
            'location': {'cl': 85.0, 'ucl': 85.6, 'lcl': 84.4},
            'variation': {'cl': 0.3, 'ucl': 0.7, 'lcl': 0.0},
            'subgroup_sizes': [2], 'scale': 'original',
        },
        status='active',
    )
    db_session.add(limit)
    db_session.commit()
    return limit


def test_get_live_limits_found_returns_limits_and_recent_values(app, db_session):
    """有生效核准界限時，回傳巢狀界限攤平後的數值與最近歷史 min/max 配對"""
    with app.app_context():
        _approved_patrol_limit(db_session, mat='SUS304', spec='10*2', item='外徑', pos='前段')

        patrol = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*2')
        db_session.add(patrol)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=patrol.id, group=1, item='外徑', position='前段',
            min_val=84.9, max_val=85.3,
        ))
        db_session.commit()

        result = PatrolService.get_live_limits({
            'mat': 'SUS304', 'spec': '10*2', 'item': '外徑', 'pos': '前段',
        })

        assert result['found'] is True
        assert result['x_cl'] == 85.0
        assert result['x_ucl'] == 85.6
        assert result['x_lcl'] == 84.4
        assert result['r_cl'] == 0.3
        assert result['r_ucl'] == 0.7
        assert result['recent_values'] == [{'min': 84.9, 'max': 85.3}]


def test_get_live_limits_transformed_scale_not_supported(app, db_session):
    """轉換尺度界限不支援即時比對，回傳 found=False 而非套用錯誤尺度"""
    with app.app_context():
        limit = _approved_patrol_limit(db_session, mat='SUS304', spec='10*2', item='厚度', pos='前段')
        limit.limits = {**limit.limits, 'scale': 'transformed'}
        db_session.commit()

        result = PatrolService.get_live_limits({
            'mat': 'SUS304', 'spec': '10*2', 'item': '厚度', 'pos': '前段',
        })

        assert result == {'found': False, 'reason': 'transformed_scale_unsupported'}


def test_get_live_limits_excludes_main_id_when_editing(app, db_session):
    """編輯既有記錄時排除自己，避免歷史序列納入編輯前的舊值"""
    with app.app_context():
        _approved_patrol_limit(db_session, mat='SUS304', spec='10*2', item='外徑', pos='前段')

        editing = PatrolMain(date=date(2026, 1, 1), material='SUS304', spec='10*2')
        db_session.add(editing)
        db_session.flush()
        db_session.add(PatrolDetail(
            main_id=editing.id, group=1, item='外徑', position='前段',
            min_val=99.0, max_val=99.0,
        ))
        db_session.commit()

        result = PatrolService.get_live_limits({
            'mat': 'SUS304', 'spec': '10*2', 'item': '外徑', 'pos': '前段',
            'exclude_main_id': editing.id,
        })

        assert result['recent_values'] == []
```

- [ ] **Step 7: 執行測試確認新增的三個測試失敗**

Run: `cd backend && python -m pytest tests/test_services/test_patrol.py -k "get_live_limits" -v`
Expected: `test_get_live_limits_not_found_without_active_limit` PASS（已實作）；其餘三個因 `location`/`variation` 分支與 `recent_values` 查詢邏輯已經在 Step 3 一併寫好，預期應直接 PASS。若失敗，依錯誤訊息修正 Step 3 的實作（例如欄位名稱、型別轉換）。

- [ ] **Step 8: 確認全部 4 個測試通過**

Run: `cd backend && python -m pytest tests/test_services/test_patrol.py -k "get_live_limits" -v`
Expected: 4 passed

- [ ] **Step 9: 提交**

```bash
git add backend/tests/test_services/test_patrol.py
git commit -m "$(cat <<'EOF'
測試：巡檢即時界限查詢的生效界限、轉換尺度與編輯排除情境

補齊 get_live_limits 在有生效界限、轉換尺度界限、編輯既有
記錄時排除自身歷史三種情境下的行為驗證。
EOF
)"
```

---

## Task 2: 後端路由 `GET /api/patrol/live-limits`

**Files:**
- Modify: `backend/routes/patrol.py`
- Create: `backend/tests/test_patrol_live_limits_route.py`

- [ ] **Step 1: 寫失敗測試 — 無權限角色被拒絕**

建立 `backend/tests/test_patrol_live_limits_route.py`：

```python
"""巡檢即時界限查詢路由的權限與契約測試。"""
import pytest
from backend.models import Role, User
from backend.utils import hash_password, generate_token


def _user(db_session, username, role_code):
    user = User(username=username, password=hash_password('pw12345678'),
                role=role_code, is_active=True)
    db_session.add(user)
    db_session.commit()
    return user


def _headers(user):
    token = generate_token(user.id, user.username, user.role)
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


@pytest.fixture
def spc_view_roles(db_session):
    db_session.add_all([
        Role(code='spc_viewer', name='SPC檢視', permissions={'spc.view': True}),
        Role(code='no_spc', name='無SPC權限', permissions={}),
    ])
    db_session.commit()


def test_live_limits_route_requires_spc_view(client, db_session, spc_view_roles):
    user = _user(db_session, 'no_spc_user', 'no_spc')
    resp = client.get(
        '/api/patrol/live-limits?mat=SUS304&spec=10*2&item=外徑&pos=前段',
        headers=_headers(user),
    )
    assert resp.status_code == 403


def test_live_limits_route_allows_spc_view_and_returns_not_found(client, db_session, spc_view_roles):
    user = _user(db_session, 'viewer_user', 'spc_viewer')
    resp = client.get(
        '/api/patrol/live-limits?mat=SUS304&spec=10*2&item=外徑&pos=前段',
        headers=_headers(user),
    )
    assert resp.status_code == 200
    assert resp.get_json() == {'found': False}
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd backend && python -m pytest tests/test_patrol_live_limits_route.py -v`
Expected: FAIL，`404 Not Found`（路由尚未存在）

- [ ] **Step 3: 新增路由**

在 `backend/routes/patrol.py`，緊接在既有的 `patrol_spc`（第 16-23 行）之後新增：

```python
@patrol_bp.route('/api/patrol/live-limits')
@auth_required
@require_perm('spc.view')
def patrol_live_limits():
    """巡檢即時模式：查詢生效中的 SPC 管制界限與最近歷史值（唯讀，供前端即時提示）"""
    try:
        data = PatrolService.get_live_limits(request.args)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd backend && python -m pytest tests/test_patrol_live_limits_route.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add backend/routes/patrol.py backend/tests/test_patrol_live_limits_route.py
git commit -m "$(cat <<'EOF'
新增：巡檢即時模式界限查詢路由 GET /api/patrol/live-limits

唯讀端點，需 spc.view 權限；供前端即時模式在量測格失焦時
查詢生效中的管制界限與最近歷史值，純提示用途不建立稽核紀錄。
EOF
)"
```

---

## Task 3: 前端 `usePatrolLiveLimits` 查詢 hook

**Files:**
- Modify: `src_frontend/src/hooks/usePatrol.ts`

- [ ] **Step 1: 新增型別與 hook**

在 `src_frontend/src/hooks/usePatrol.ts`，於 `PatrolOptions` 介面（第 33-38 行）之後新增型別，並於檔案的 `// --- Queries ---` 區塊（`usePatrolStats` 之後、`useExportPatrolSpcReport` 之前）新增 hook：

```typescript
export interface PatrolLiveLimitsParams {
    m_id?: string;
    op_id?: string;
    cust_id?: string;
    mat: string;
    spec: string;
    item: string;
    pos: string;
    exclude_main_id?: number;
}

export interface PatrolLiveLimits {
    found: boolean;
    reason?: string;
    x_cl?: number;
    x_ucl?: number;
    x_lcl?: number;
    r_cl?: number;
    r_ucl?: number;
    r_lcl?: number;
    recent_values?: { min: number; max: number }[];
}

export const usePatrolLiveLimits = (params: PatrolLiveLimitsParams, enabled: boolean) => {
    return useQuery({
        queryKey: ['patrolLiveLimits', params],
        queryFn: async () => {
            const queryParams = new URLSearchParams();
            if (params.m_id) queryParams.append('m_id', params.m_id);
            if (params.op_id) queryParams.append('op_id', params.op_id);
            if (params.cust_id) queryParams.append('cust_id', params.cust_id);
            queryParams.append('mat', params.mat);
            queryParams.append('spec', params.spec);
            queryParams.append('item', params.item);
            queryParams.append('pos', params.pos);
            if (params.exclude_main_id) queryParams.append('exclude_main_id', params.exclude_main_id.toString());

            const res = await api.get<PatrolLiveLimits>(`/patrol/live-limits?${queryParams.toString()}`);
            return res.data;
        },
        enabled: enabled && !!params.mat && !!params.item,
        staleTime: 60 * 1000,
    });
};
```

沒有自動化測試（純資料抓取 hook，行為由 Task 6 的 `PatrolModal` 整合測試間接覆蓋）。

- [ ] **Step 2: 型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 無錯誤

- [ ] **Step 3: 提交**

```bash
git add src_frontend/src/hooks/usePatrol.ts
git commit -m "$(cat <<'EOF'
新增：巡檢即時界限查詢 hook usePatrolLiveLimits

供即時模式在量測格失焦時查詢生效中的管制界限與最近歷史值。
EOF
)"
```

---

## Task 4: `patrolFormUtils.ts` 即時序列組裝與提示對照

**Files:**
- Modify: `src_frontend/src/components/patrol/patrolFormUtils.ts`
- Test: `src_frontend/src/components/patrol/patrolFormUtils.test.ts`

- [ ] **Step 1: 寫失敗測試**

在 `src_frontend/src/components/patrol/patrolFormUtils.test.ts` 檔案開頭的 import 新增 `buildLiveGroupSeries, evaluatePatrolLiveStability`，並在 `describe('patrolFormUtils', ...)` 區塊內新增：

```typescript
  it('組裝即時序列：歷史值 + 本次表單已填完整（min 與 max 皆有值）的組別，依組別順序排列', () => {
    const liveDetails: PatrolDetailInput[] = [
      { group: '第1組', pos: '前段', item: '外徑', min: '85.0', max: '85.4' },
      { group: '第2組', pos: '前段', item: '外徑', min: '85.1', max: '' }, // 尚未填完整，排除
      { group: '第2組', pos: '中段', item: '外徑', min: '90', max: '90' }, // 不同 position，排除
    ];

    const series = buildLiveGroupSeries({
      recentValues: [{ min: 84.8, max: 85.2 }],
      details: liveDetails,
      pos: '前段',
      item: '外徑',
      groupCount: 2,
    });

    expect(series.means).toEqual([85.0, 85.2]);
    expect(series.ranges).toEqual([0.4, 0.4]);
  });

  it('即時穩定性判讀：組合序列違反規則時回傳對應圖別的提示', () => {
    const result = evaluatePatrolLiveStability({
      means: [85, 85.1, 85.2, 85.3, 85.4, 85.5],
      ranges: [0.2, 0.2, 0.2, 0.2, 0.2, 0.2],
      xCl: 85, xUcl: 86, xLcl: 84,
      rCl: 0.3, rUcl: 0.7, rLcl: 0,
    });

    expect(result).not.toBeNull();
    expect(result?.chartKind).toBe('location');
    expect(result?.hint).toContain('模具間隙');
  });

  it('即時穩定性判讀：序列在界限內時回傳 null（不示警）', () => {
    const result = evaluatePatrolLiveStability({
      means: [85, 85, 85, 85, 85, 85],
      ranges: [0.2, 0.2, 0.2, 0.2, 0.2, 0.2],
      xCl: 85, xUcl: 86, xLcl: 84,
      rCl: 0.3, rUcl: 0.7, rLcl: 0,
    });

    expect(result).toBeNull();
  });
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run patrolFormUtils.test.ts`
Expected: FAIL，`buildLiveGroupSeries is not a function` / `evaluatePatrolLiveStability is not a function`

- [ ] **Step 3: 實作**

在 `src_frontend/src/components/patrol/patrolFormUtils.ts` 檔案開頭新增 import：

```typescript
import { analyzeWECO, analyzeRChartWECO } from '../../utils/spcAnalysis';
```

在檔案末尾新增：

```typescript
const GROUP_LABELS = (count: number) => Array.from({ length: count }, (_, i) => `第${i + 1}組`);

interface BuildLiveGroupSeriesParams {
  recentValues: { min: number; max: number }[];
  details: PatrolDetailInput[];
  pos: string;
  item: string;
  groupCount: number;
}

export const buildLiveGroupSeries = ({
  recentValues, details, pos, item, groupCount,
}: BuildLiveGroupSeriesParams): { means: number[]; ranges: number[] } => {
  const history = recentValues.map(({ min, max }) => ({ min, max }));

  const currentGroups = GROUP_LABELS(groupCount)
    .map(group => {
      const minText = getPatrolDetailValue(details, group, pos, item, 'min');
      const maxText = getPatrolDetailValue(details, group, pos, item, 'max');
      if (minText === '' || maxText === '') return null;
      const min = parsePatrolMeasurement(minText);
      const max = parsePatrolMeasurement(maxText);
      if (min === null || max === null) return null;
      return { min, max };
    })
    .filter((pair): pair is { min: number; max: number } => pair !== null);

  const combined = [...history, ...currentGroups];
  return {
    means: combined.map(({ min, max }) => (min + max) / 2),
    ranges: combined.map(({ min, max }) => Math.abs(max - min)),
  };
};

export interface PatrolLiveViolation {
  chartKind: 'location' | 'variation';
  label: string;
  hint: string;
}

const LOCATION_HINTS: Record<string, string> = {
  'Rule 1: 超出控制限': '單點急劇偏移，先重量一次確認非量測失誤；屬實則檢查機頭壓力/料溫瞬間波動',
  'Rule 2: 連續9點同側': '製程中心已偏移，非單純波動，建議依 5M（人機料法環）排查後調整模具定位',
  'Rule 3: 連續6點趨勢': '持續漂移，典型成因是模具磨耗或螺桿轉速緩慢飄移，建議檢查/微調模具間隙與牽引速度',
};

const VARIATION_HINT = '量測值波動變大，較可能是設備穩定度或原料問題，非模具位置問題';

interface EvaluatePatrolLiveStabilityParams {
  means: number[];
  ranges: number[];
  xCl: number;
  xUcl: number;
  xLcl: number;
  rCl: number;
  rUcl: number;
  rLcl: number;
}

export const evaluatePatrolLiveStability = ({
  means, ranges, xCl, xUcl, xLcl, rCl, rUcl, rLcl,
}: EvaluatePatrolLiveStabilityParams): PatrolLiveViolation | null => {
  if (means.length === 0) return null;
  const lastIndex = means.length - 1;
  const labels = means.map((_, i) => String(i));

  const location = analyzeWECO(means, xCl, xUcl, xLcl, labels);
  const lastLocationViolation = location.violations.find(v => v.label === labels[lastIndex]);
  if (lastLocationViolation) {
    const reason = lastLocationViolation.reasons[0];
    return {
      chartKind: 'location',
      label: reason,
      hint: LOCATION_HINTS[reason] ?? LOCATION_HINTS['Rule 1: 超出控制限'],
    };
  }

  const variation = analyzeRChartWECO(ranges, rCl, rUcl, labels);
  const lastVariationViolation = variation.violations.find(v => v.label === labels[lastIndex]);
  if (lastVariationViolation) {
    return {
      chartKind: 'variation',
      label: lastVariationViolation.reasons[0],
      hint: VARIATION_HINT,
    };
  }

  return null;
};
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd src_frontend && npx vitest run patrolFormUtils.test.ts`
Expected: 全部 PASS（含既有測試）

- [ ] **Step 5: 提交**

```bash
git add src_frontend/src/components/patrol/patrolFormUtils.ts src_frontend/src/components/patrol/patrolFormUtils.test.ts
git commit -m "$(cat <<'EOF'
新增：巡檢即時模式的序列組裝與穩定性提示對照

buildLiveGroupSeries 把最近歷史值與本次表單已填完整的組別
組成 X̄/R 序列；evaluatePatrolLiveStability 重用既有
spcAnalysis.ts 規則引擎，只針對最新一點違規時回傳依圖別
（位置/變異）區分的擠壓製程調整提示。
EOF
)"
```

---

## Task 5: `PatrolMeasurementTable.tsx` 顯示即時違規標記

**Files:**
- Modify: `src_frontend/src/components/patrol/PatrolMeasurementTable.tsx`
- Test: `src_frontend/src/components/patrol/PatrolMeasurementTable.test.tsx`

- [ ] **Step 1: 寫失敗測試**

在 `src_frontend/src/components/patrol/PatrolMeasurementTable.test.tsx` 新增測試（於既有 `it` 之後）：

```typescript
  it('即時模式有違規時，標記黃框並顯示提示文字；沒有違規的儲存格不受影響', () => {
    const details: PatrolDetailInput[] = [
      { group: '第1組', pos: '前段', item: '外徑', min: '85', max: '85.4' },
    ];

    render(
      <PatrolMeasurementTable
        groupCount={1}
        showInner={false}
        details={details}
        tolerances={[]}
        specStdValues={{}}
        onDetailChange={vi.fn()}
        liveViolations={{
          '前段|外徑|第1組': { chartKind: 'location', label: 'Rule 1: 超出控制限', hint: '單點急劇偏移，先重量一次確認非量測失誤' },
        }}
      />,
    );

    expect(screen.getByDisplayValue('85')).toHaveClass('patrol-live-warning');
    expect(screen.getByText(/單點急劇偏移/)).toBeInTheDocument();
  });
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run PatrolMeasurementTable.test.tsx`
Expected: FAIL，`liveViolations` 不是合法 prop（TypeScript 編譯錯誤）或找不到提示文字

- [ ] **Step 3: 實作**

修改 `src_frontend/src/components/patrol/PatrolMeasurementTable.tsx`：

在 import 區塊新增 `type PatrolLiveViolation`：

```typescript
import {
    getPatrolDetailValue,
    isPatrolCellNG,
    isPatrolConcentricityNG,
    type PatrolDetailInput,
    type PatrolLiveViolation,
    type PatrolTolerance,
} from './patrolFormUtils';
```

在 `PatrolMeasurementTableProps` 介面新增欄位：

```typescript
interface PatrolMeasurementTableProps {
    groupCount: number;
    showInner: boolean;
    details: PatrolDetailInput[];
    tolerances: PatrolTolerance[];
    specStdValues: Record<string, number>;
    onDetailChange: (group: string, pos: string, item: string, type: 'min' | 'max', value: string) => void;
    liveViolations?: Record<string, PatrolLiveViolation>;
}
```

在元件參數解構新增 `liveViolations = {}`：

```typescript
const PatrolMeasurementTable = ({
    groupCount,
    showInner,
    details,
    tolerances,
    specStdValues,
    onDetailChange,
    liveViolations = {},
}: PatrolMeasurementTableProps) => {
```

在 `isConcentricityNG` 定義之後新增：

```typescript
    const getLiveViolation = (pos: string, item: string, group: string) =>
        liveViolations[`${pos}|${item}|${group}`];
```

修改 `tbody` 內每個儲存格的 render（把 Fragment 內容改成使用 `getLiveViolation`）：

```typescript
                                {POSITIONS.map(pos =>
                                    ITEMS.map(item => {
                                        if (item === '內徑' && !showInner) return null;
                                        const minNG = isCellNG(pos, item, 'min', group) || (item === '厚度' && isConcentricityNG(pos, group));
                                        const maxNG = isCellNG(pos, item, 'max', group) || (item === '厚度' && isConcentricityNG(pos, group));
                                        const liveViolation = getLiveViolation(pos, item, group);
                                        return (
                                            <Fragment key={`${pos}-${item}`}>
                                                <td style={{ padding: '2px' }}>
                                                    <Form.Control
                                                        size="sm"
                                                        type="number"
                                                        step="0.01"
                                                        value={getPatrolDetailValue(details, group, pos, item, 'min')}
                                                        onChange={e => onDetailChange(group, pos, item, 'min', e.target.value)}
                                                        className={`patrol-input${minNG ? ' is-invalid-breathing' : ''}${liveViolation ? ' patrol-live-warning' : ''}`}
                                                    />
                                                </td>
                                                <td style={{ padding: '2px' }}>
                                                    <Form.Control
                                                        size="sm"
                                                        type="number"
                                                        step="0.01"
                                                        value={getPatrolDetailValue(details, group, pos, item, 'max')}
                                                        onChange={e => onDetailChange(group, pos, item, 'max', e.target.value)}
                                                        className={`patrol-input${maxNG ? ' is-invalid-breathing' : ''}${liveViolation ? ' patrol-live-warning' : ''}`}
                                                    />
                                                    {liveViolation && (
                                                        <div className="small text-warning-emphasis" style={{ whiteSpace: 'normal', maxWidth: '160px' }}>
                                                            ⚠️ {liveViolation.hint}
                                                        </div>
                                                    )}
                                                </td>
                                            </Fragment>
                                        );
                                    })
                                )}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `cd src_frontend && npx vitest run PatrolMeasurementTable.test.tsx`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src_frontend/src/components/patrol/PatrolMeasurementTable.tsx src_frontend/src/components/patrol/PatrolMeasurementTable.test.tsx
git commit -m "$(cat <<'EOF'
新增：巡檢量測表格顯示即時穩定性違規標記

liveViolations 依 position|item|group 對應到儲存格，標記
patrol-live-warning 樣式並在儲存格下方顯示模具調整提示文字，
與既有超規格的 is-invalid-breathing 視覺區分。
EOF
)"
```

- [ ] **Step 6: 新增 CSS 樣式**

檢查 `src_frontend/src/components/patrol/` 或 `src_frontend/src/` 底下既有的 `is-invalid-breathing` 樣式定義位置：

Run: `grep -rn "is-invalid-breathing" src_frontend/src --include=*.css`

在同一個 CSS 檔案裡，緊接在 `is-invalid-breathing` 規則之後新增：

```css
.patrol-live-warning {
    border-color: #ffc107 !important;
    background-color: #fff8e1 !important;
}
```

- [ ] **Step 7: 提交**

```bash
git add -u
git commit -m "$(cat <<'EOF'
樣式：巡檢即時違規標記使用黃框，與超規格紅框區分
EOF
)"
```

---

## Task 6: `PatrolModal.tsx` 即時模式開關與失焦判讀

**Files:**
- Modify: `src_frontend/src/components/patrol/PatrolModal.tsx`
- Test: `src_frontend/src/components/patrol/PatrolModal.test.tsx`

- [ ] **Step 1: 讀取現有測試檔案，確認既有的 mock 慣例**

Run: `cat src_frontend/src/components/patrol/PatrolModal.test.tsx`（不修改，僅確認現有測試如何 mock `usePatrolOptions` 等 hook，供下一步比照撰寫新測試）

- [ ] **Step 2: 寫失敗測試 — 即時模式開關預設關閉，開啟後量測格失焦會查詢界限**

在 `src_frontend/src/components/patrol/PatrolModal.test.tsx`，比照檔案內既有的 hook mock 寫法，新增 mock `usePatrolLiveLimits`（若既有測試已經用 `vi.mock('../../hooks/usePatrol', ...)` 整包 mock，則在該 mock 物件內新增 `usePatrolLiveLimits: vi.fn()`），並新增測試：

```typescript
  it('即時模式關閉時不顯示切換後的判讀提示；開啟並填完一組量測後才查詢即時界限', async () => {
    const liveLimitsMock = vi.fn().mockReturnValue({
      data: { found: false }, isFetching: false,
    });
    vi.mocked(usePatrolLiveLimits).mockImplementation(liveLimitsMock);

    render(<PatrolModal show handleClose={vi.fn()} onSuccess={vi.fn()} editId={null} />);

    const liveModeToggle = screen.getByRole('checkbox', { name: '即時模式' });
    expect(liveModeToggle).not.toBeChecked();
    expect(liveLimitsMock).not.toHaveBeenCalled();

    await userEvent.click(liveModeToggle);
    expect(liveModeToggle).toBeChecked();
  });
```

若專案沒有安裝 `@testing-library/user-event`，改用既有測試檔案已使用的互動方式（例如 `fireEvent`）。

- [ ] **Step 3: 執行測試確認失敗**

Run: `cd src_frontend && npx vitest run PatrolModal.test.tsx`
Expected: FAIL，找不到 `name: '即時模式'` 的 checkbox

- [ ] **Step 4: 實作即時模式開關與失焦判讀邏輯**

修改 `src_frontend/src/components/patrol/PatrolModal.tsx`：

在 import 區塊新增：

```typescript
import { usePatrolLiveLimits, type PatrolLiveLimits } from '../../hooks/usePatrol';
import {
    buildPatrolPayload,
    buildPatrolUpdatePayload,
    buildLiveGroupSeries,
    evaluatePatrolLiveStability,
    getValidPatrolDetails,
    type PatrolDetailInput,
    type PatrolLiveViolation,
} from './patrolFormUtils';
```

（`buildPatrolPayload` 等既有 import 已存在，這裡是把新函式加進同一個 import 陳述式，取代原本第 13-18 行的 import。）

在 Details State 區塊（第 53-56 行）之後新增狀態：

```typescript
    const [liveMode, setLiveMode] = useState(false);
    const [liveLimitsCache, setLiveLimitsCache] = useState<Record<string, PatrolLiveLimits>>({});
    const [liveTouchedKey, setLiveTouchedKey] = useState<string | null>(null);
```

在 `resetForm` 內（第 58-70 行）新增重置：

```typescript
    const resetForm = useCallback(() => {
        setDate(formatLocalDate());
        setMachine('');
        setOperator('');
        setInspector('');
        setCustomer('');
        setMaterial('');
        setBatch('');
        setSpec('');
        setGroupCount(1);
        setDetails([]);
        setShowInner(false);
        setLiveMode(false);
        setLiveLimitsCache({});
        setLiveTouchedKey(null);
    }, []);
```

在 `handleDetailChange`（第 115-128 行）之後新增：

```typescript
    const handleDetailBlur = (pos: string, item: string) => {
        if (!liveMode) return;
        setLiveTouchedKey(`${pos}|${item}`);
    };

    const liveLimitsKey = liveTouchedKey ? liveTouchedKey.split('|') as [string, string] : null;
    const [liveLimitsPos, liveLimitsItem] = liveLimitsKey ?? ['', ''];
    const liveLimitsQuery = usePatrolLiveLimits(
        {
            m_id: machine, op_id: operator, cust_id: customer,
            mat: material, spec, item: liveLimitsItem, pos: liveLimitsPos,
            exclude_main_id: editId ?? undefined,
        },
        liveMode && !!liveTouchedKey && !(liveTouchedKey in liveLimitsCache),
    );

    useEffect(() => {
        if (liveTouchedKey && liveLimitsQuery.data && !(liveTouchedKey in liveLimitsCache)) {
            setLiveLimitsCache(prev => ({ ...prev, [liveTouchedKey]: liveLimitsQuery.data! }));
        }
    }, [liveTouchedKey, liveLimitsQuery.data, liveLimitsCache]);

    const liveViolations = useMemo(() => {
        if (!liveMode) return {};
        const violations: Record<string, PatrolLiveViolation> = {};
        for (const pos of ['前段', '中段', '後段']) {
            for (const item of ['外徑', '內徑', '厚度']) {
                const cached = liveLimitsCache[`${pos}|${item}`];
                if (!cached?.found) continue;
                for (let g = 1; g <= groupCount; g += 1) {
                    const group = `第${g}組`;
                    const { means, ranges } = buildLiveGroupSeries({
                        recentValues: cached.recent_values ?? [],
                        details, pos, item, groupCount: g,
                    });
                    if (means.length === 0) continue;
                    const violation = evaluatePatrolLiveStability({
                        means, ranges,
                        xCl: cached.x_cl!, xUcl: cached.x_ucl!, xLcl: cached.x_lcl!,
                        rCl: cached.r_cl!, rUcl: cached.r_ucl!, rLcl: cached.r_lcl!,
                    });
                    if (violation) {
                        violations[`${pos}|${item}|${group}`] = violation;
                    }
                }
            }
        }
        return violations;
    }, [liveMode, liveLimitsCache, details, groupCount]);
```

在 `handleDetailChange` 函式定義後方呼叫端（`PatrolMeasurementTable` 的 `onDetailChange` prop 保持不變），改為在量測表格外層新增即時模式開關，並把 `liveViolations` 與失焦事件傳入。修改 `<PatrolMeasurementTable .../>` 呼叫處（第 249-256 行）：

```typescript
                                    <Form.Check
                                        type="switch"
                                        id="patrol-live-mode"
                                        label="即時模式"
                                        checked={liveMode}
                                        onChange={e => setLiveMode(e.target.checked)}
                                        className="mb-2"
                                    />

                                    <PatrolMeasurementTable
                                        groupCount={groupCount}
                                        showInner={showInner}
                                        details={details}
                                        tolerances={tolerances}
                                        specStdValues={specStdValues}
                                        onDetailChange={handleDetailChange}
                                        liveViolations={liveViolations}
                                    />
```

`PatrolMeasurementTable` 目前的 `Form.Control` 沒有 `onBlur`；為了觸發 `handleDetailBlur`，修改 `PatrolMeasurementTable.tsx` 的 props 介面新增 `onCellBlur?: (pos: string, item: string) => void`，並在兩個 `Form.Control`（min 與 max）加上 `onBlur={() => onCellBlur?.(pos, item)}`。對應在 `PatrolModal.tsx` 的呼叫處補上 `onCellBlur={handleDetailBlur}`。

- [ ] **Step 5: 執行測試確認通過**

Run: `cd src_frontend && npx vitest run PatrolModal.test.tsx PatrolMeasurementTable.test.tsx`
Expected: 全部 PASS

- [ ] **Step 6: 型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 無錯誤

- [ ] **Step 7: 提交**

```bash
git add src_frontend/src/components/patrol/PatrolModal.tsx src_frontend/src/components/patrol/PatrolMeasurementTable.tsx src_frontend/src/components/patrol/PatrolModal.test.tsx
git commit -m "$(cat <<'EOF'
新增：巡檢表單即時模式開關與失焦即時判讀

開啟即時模式後，量測格失焦時查詢（並快取）該 item/position
的生效管制界限，把最近歷史值與本次表單已填完整的組別組成
序列即時判讀，違規則在表格顯示黃框與模具調整提示。
EOF
)"
```

---

## Task 7: 存檔後觸發正式 OCAP 事件

**Files:**
- Modify: `src_frontend/src/components/patrol/PatrolModal.tsx`

- [ ] **Step 1: 讀取既有 OCAP 面板整合方式作為對照**

Run: `sed -n '1,40p;100,180p;290,330p' src_frontend/src/components/spc/SpcStudyPanel.tsx`（不修改，僅確認 `useAnalyzeSpcStudy`／`SpcOcapOffcanvas`／`useSaveSpcOcap`／`useSpcAssignees` 的既有串接方式，比照撰寫）

- [ ] **Step 2: 實作**

在 `src_frontend/src/components/patrol/PatrolModal.tsx` 的 import 區塊新增：

```typescript
import { useAnalyzeSpcStudy, useSaveSpcOcap, useSpcAssignees } from '../../hooks/useSpcStudies';
import type { SpcEventSummary } from '../../types/spc';
import SpcOcapOffcanvas from '../spc/SpcOcapOffcanvas';
```

在既有的 `createMutation`／`updateMutation`（第 40-41 行）之後新增：

```typescript
    const analyzeOngoing = useAnalyzeSpcStudy();
    const saveOcap = useSaveSpcOcap();
    const [openEvents, setOpenEvents] = useState<SpcEventSummary[]>([]);
    const [selectedEvent, setSelectedEvent] = useState<SpcEventSummary | null>(null);
    const assignees = useSpcAssignees(Boolean(selectedEvent));
```

新增觸發正式判定的函式，放在 `handleSubmit` 定義之前：

```typescript
    const triggerOngoingAnalysisForTouchedStreams = async () => {
        const touchedStreams = new Set(
            Object.keys(liveViolations).map(key => key.split('|').slice(0, 2).join('|')),
        );
        const newEvents: SpcEventSummary[] = [];
        for (const streamKey of touchedStreams) {
            const [pos, item] = streamKey.split('|');
            try {
                const result = await analyzeOngoing.mutateAsync({
                    source: 'patrol',
                    filters: { m_id: machine, op_id: operator, cust_id: customer, mat: material, spec, item, pos },
                    study_type: 'ongoing',
                });
                const activeLimit = result.monitoring_limit
                    ?? result.limit_versions?.find(limit => limit.status === 'active');
                for (const event of activeLimit?.events ?? []) {
                    if (event.status === 'open') newEvents.push(event);
                }
            } catch (error) {
                console.error(`巡檢正式 SPC 判定失敗（${item}/${pos}）`, error);
            }
        }
        if (newEvents.length > 0) {
            setOpenEvents(newEvents);
            toast(`本次觸發 ${newEvents.length} 項製程異常，可查看建議處置`, { icon: '⚠️' });
        }
    };
```

修改 `handleSubmit`（第 130-174 行）的 `try` 區塊，在 `onSuccess(); handleClose();` 之前插入呼叫：

```typescript
        try {
            if (editId) {
                await updateMutation.mutateAsync({ id: editId, data: buildPatrolUpdatePayload({ ...payloadValues, editId }) });
            } else {
                await createMutation.mutateAsync(buildPatrolPayload(payloadValues));
            }
            if (liveMode && Object.keys(liveViolations).length > 0) {
                await triggerOngoingAnalysisForTouchedStreams();
            }
            onSuccess();
            handleClose();
        } catch (error) {
            console.error(error);
        }
```

在 `Modal` 的 JSX 最外層（`</Modal>` 之前）新增事件清單與 OCAP 面板：

```typescript
            {openEvents.length > 0 && (
                <div className="position-fixed bottom-0 end-0 m-3 p-2 bg-white border rounded shadow" style={{ zIndex: 1060 }}>
                    <div className="small fw-bold mb-1">本次觸發的製程異常</div>
                    {openEvents.map(event => (
                        <Button key={event.id} size="sm" variant="outline-danger" className="d-block mb-1" onClick={() => setSelectedEvent(event)}>
                            事件 #{event.id} · {event.chart_kind === 'location' ? '位置圖' : '變異圖'} · 查看建議
                        </Button>
                    ))}
                </div>
            )}
            {selectedEvent && (
                <SpcOcapOffcanvas
                    show
                    eventId={selectedEvent.id}
                    ocapId={selectedEvent.ocap?.id}
                    initialValue={selectedEvent.ocap}
                    onHide={() => setSelectedEvent(null)}
                    onSave={input => {
                        saveOcap.mutate(input, {
                            onSuccess: () => setSelectedEvent(null),
                        });
                    }}
                    pending={saveOcap.isPending}
                    saveError={saveOcap.isError}
                    assignees={assignees.data ?? []}
                    assigneesLoading={assignees.isLoading}
                    assigneesError={assignees.isError}
                />
            )}
        </Modal>
```

- [ ] **Step 3: 型別檢查**

Run: `cd src_frontend && npx tsc --noEmit`
Expected: 無錯誤（若 `AnalyzeSpcStudyInput` 的 `filters` 型別要求特定形狀，依實際型別錯誤調整 `triggerOngoingAnalysisForTouchedStreams` 內的 filters 物件）

- [ ] **Step 4: 執行既有測試套件確認沒有回歸**

Run: `cd src_frontend && npx vitest run PatrolModal.test.tsx`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src_frontend/src/components/patrol/PatrolModal.tsx
git commit -m "$(cat <<'EOF'
新增：巡檢即時模式存檔後觸發正式 SPC 事件與 OCAP 面板

存檔成功後，若本次曾觸發即時提示，對每個受影響的 item/position
呼叫既有的 ongoing analyze（完全沿用既有邏輯與稽核機制），
新產生的開放事件會提示並可直接開啟既有 OCAP 面板處置。
EOF
)"
```

---

## Task 8: 瀏覽器手動驗證

**Files:** 無程式碼變更，僅驗證。

- [ ] **Step 1: 確認後端已有可用的生效巡檢管制界限測試資料**

若本地開發資料庫沒有任何 `source='patrol'` 且 `status='active'` 的 `SpcLimitVersion`，先透過既有 SPC 研究頁面（`/spc-studies` 或既有巡檢 SPC 面板）跑一次分析並核准一組界限，或直接在資料庫插入一筆（比照 Task 1 測試中的 `_approved_patrol_limit` 資料形狀）。

- [ ] **Step 2: 啟動開發伺服器並開啟巡檢頁面**

Run: `cd backend && python app.py`（另一個終端機）`cd src_frontend && npm run dev`

導覽至巡檢頁面，點「新增巡檢」，選擇與 Step 1 界限相符的機台/材質/規格。

- [ ] **Step 3: 驗證即時模式標紅與提示**

開啟「即時模式」開關，於第一組「外徑」的 MIN／MAX 依序輸入會觸發「Rule 1: 超出控制限」的數值（例如遠高於 UCL），確認：
- 該儲存格出現黃框（`patrol-live-warning`）
- 儲存格下方出現「⚠️ 單點急劇偏移...」提示文字

- [ ] **Step 4: 驗證存檔後正式事件與 OCAP 面板**

點擊「儲存」，確認：
- 出現「本次觸發 N 項製程異常，可查看建議處置」的 toast
- 右下角出現事件按鈕，點擊後開啟既有的 OCAP 面板（`SpcOcapOffcanvas`），可填寫 6M 調查／製程調整並儲存

- [ ] **Step 5: 驗證關閉即時模式不影響既有流程**

重新開啟「新增巡檢」，不開啟即時模式，正常填寫並儲存，確認行為與變更前完全一致（無新增的 toast 或標記）。

---

## Self-Review Notes

- **spec 涵蓋度**：架構分層（前端輕量預覽 Task 3-6、存檔後正式判定 Task 7）、規則集對齊（Task 4 直接重用 `spcAnalysis.ts` 既有的 `DEFAULT_RULES`，未擴增規則）、編輯時排除自身歷史（Task 1 Step 6 測試）、無生效界限降級提示（Task 1 Step 1-5）、效能快取（Task 6 `liveLimitsCache`）、關閉即時模式不阻擋（Task 6 `liveMode` 純前端狀態，不影響 `handleSubmit` 既有邏輯）均已對應到任務。
- **型別一致性**：`PatrolLiveLimits`（Task 3 定義）在 Task 6、Task 7 中維持相同欄位名稱（`x_cl/x_ucl/x_lcl/r_cl/r_ucl/r_lcl/recent_values`）；`PatrolLiveViolation`（Task 4 定義於 `patrolFormUtils.ts`）在 Task 5、Task 6 中作為同一型別匯入使用，未重新定義。
- **已知風險**：Task 6 Step 4 與 Task 7 Step 2 的程式碼行號基準是撰寫本計畫當下的檔案內容；若前面任務執行時檔案已變動，需以實際內容為準調整插入位置（邏輯與變數命名保持一致即可）。
