# SPC OCAP 責任人選擇與即時資料更新實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 OCAP 責任人數字 ID 改為限用品保角色的下拉選單，並讓儲存後的 OCAP 立即同步到目前 SPC 事件。

**Architecture:** 後端以 `SpcOcapService` 集中維護可指派角色白名單、清單查詢與寫入驗證，SPC 路由只暴露最小必要資料並回傳完整 OCAP。前端由 React Query 取得責任人、以 API 回傳的 `SpcOcapRecord` 不可變更新 `monitoring_limit` 與 `limit_versions` 事件，再失效化真正使用中的研究快取。

**Tech Stack:** Flask 3.1、SQLAlchemy、pytest、React 19、TypeScript 5.9、TanStack React Query 5、React Bootstrap、Vitest、Testing Library

## Global Constraints

- 所有使用者介面、程式碼備註、說明與 commit 訊息使用繁體中文。
- 可指派角色固定為 `qa_supervisor`、`qc_manager`、`admin`，且帳號必須啟用。
- `/api/users` 與 `user.manage` 權限維持不變。
- 歷史責任人若已停用或角色不符，未變更責任人時仍可維護其他 OCAP 欄位。
- 不新增資料表或欄位，不建立資料庫 migration。
- `tmp/` 不得納入任何 commit。

---

## 檔案與責任邊界

- `backend/services/spc_ocap_service.py`：可指派角色政策、責任人查詢、指派驗證與 OCAP 儲存交易。
- `backend/routes/spc_studies.py`：SPC 責任人唯讀端點及完整 OCAP HTTP 契約。
- `backend/tests/test_services/test_spc_ocap_service.py`：角色白名單、啟用狀態、歷史值相容與拒絕時不寫稽核紀錄。
- `backend/tests/test_spc_study_routes.py`：權限、最小回應欄位、完整 POST／PATCH 回應。
- `src_frontend/src/types/spc.ts`：`SpcAssignee` 與完整 OCAP 型別。
- `src_frontend/src/hooks/useSpcStudies.ts`：責任人查詢、完整 OCAP mutation 與正確研究快取失效化。
- `src_frontend/src/hooks/useSpcStudies.test.tsx`：查詢與 mutation 契約測試。
- `src_frontend/src/components/spc/SpcOcapOffcanvas.tsx`：責任人選單、歷史不可指派值及載入／失敗提示。
- `src_frontend/src/components/spc/SpcOcapOffcanvas.test.tsx`：選單顯示與 payload 測試。
- `src_frontend/src/components/spc/SpcStudyPanel.tsx`：成功儲存後同步事件與父層版本。
- `src_frontend/src/components/spc/SpcStudyPanel.test.tsx`：不重新整理即可重開最新 OCAP 的整合測試。

### Task 1: 後端責任人政策與服務層驗證

**Files:**
- Modify: `backend/services/spc_ocap_service.py`
- Test: `backend/tests/test_services/test_spc_ocap_service.py`

**Interfaces:**
- Produces: `OCAP_ASSIGNABLE_ROLE_CODES: tuple[str, ...]`
- Produces: `SpcOcapService.list_assignable_users() -> list[dict[str, Any]]`
- Produces: `SpcOcapService.save_ocap(...)` 在新增或更換責任人時驗證帳號資格。

- [ ] **Step 1: 寫入失敗的服務測試**

在 `backend/tests/test_services/test_spc_ocap_service.py` 增加角色／使用者工廠與三個測試：

```python
def _role(db_session, code, name, permissions=None):
    role = Role(code=code, name=name, permissions=permissions or {})
    db_session.add(role)
    db_session.flush()
    return role


def _user(db_session, username, role, *, active=True):
    user = User(username=username, password="hashed", role=role, is_active=active)
    db_session.add(user)
    db_session.flush()
    return user


def test_assignable_users_only_include_active_quality_roles(app, db_session):
    with app.app_context():
        for code, name in (
            ("qa_supervisor", "QA主管"),
            ("qc_manager", "品管經理"),
            ("admin", "系統管理員"),
            ("inspector", "檢驗員"),
        ):
            _role(db_session, code, name)
        qa = _user(db_session, "qa-active", "qa_supervisor")
        manager = _user(db_session, "manager-active", "qc_manager")
        admin = _user(db_session, "admin-active", "admin")
        _user(db_session, "qa-disabled", "qa_supervisor", active=False)
        _user(db_session, "inspector-active", "inspector")
        db_session.commit()

        rows = SpcOcapService.list_assignable_users()

        assert {row["id"] for row in rows} == {qa.id, manager.id, admin.id}
        assert {tuple(row) for row in rows} == {
            ("id", "username", "role", "role_name")
        }


def test_new_or_changed_owner_must_be_assignable(app, db_session):
    with app.app_context():
        actor = _actor(db_session)
        _role(db_session, "inspector", "檢驗員")
        invalid_owner = _user(db_session, "invalid-owner", "inspector")
        _, version, limit = _study_limit(db_session, actor)
        event = SpcOcapService.sync_events(limit.id, version.id, [{
            "chart_kind": "variation", "rule_code": "beyond_limits",
            "point_index": 1, "observed_value": 0.5,
        }])[0]

        with pytest.raises(SpcValidationError) as exc:
            SpcOcapService.save_ocap(event.id, actor.id, {
                "owner_id": invalid_owner.id, "status": "open",
            })

        assert exc.value.code == "SPC_OCAP_OWNER_NOT_ASSIGNABLE"
        assert SpcOcap.query.filter_by(event_id=event.id).first() is None
        assert AuditLog.query.filter_by(module="spc_ocap").count() == 0


def test_unchanged_historical_owner_does_not_block_other_edits(app, db_session):
    with app.app_context():
        actor = _actor(db_session)
        historical_owner = _user(
            db_session, "historical-owner", actor.role, active=True
        )
        _, version, limit = _study_limit(db_session, actor)
        event = SpcOcapService.sync_events(limit.id, version.id, [{
            "chart_kind": "variation", "rule_code": "beyond_limits",
            "point_index": 2, "observed_value": 0.6,
        }])[0]
        created = SpcOcapService.save_ocap(event.id, actor.id, {
            "owner_id": historical_owner.id, "status": "open",
        })
        historical_owner.is_active = False
        db_session.commit()

        updated = SpcOcapService.save_ocap(event.id, actor.id, {
            "owner_id": historical_owner.id,
            "process_adjustment": "調整壓力參數",
            "status": "open",
        })

        assert updated.id == created.id
        assert updated.owner_id == historical_owner.id
        assert updated.process_adjustment == "調整壓力參數"
```

測試檔需補上：

```python
from backend.models import SpcOcap
from backend.services.spc_errors import SpcValidationError
```

- [ ] **Step 2: 執行測試並確認因介面尚不存在而失敗**

Run: `venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_ocap_service.py -q`

Expected: FAIL，指出 `list_assignable_users` 不存在，且不可指派責任人尚未被拒絕。

- [ ] **Step 3: 實作角色白名單、清單與條件式驗證**

在服務檔匯入 `Role`、`User` 並新增：

```python
from ..models import Role, SpcEvent, SpcLimitVersion, SpcOcap, SpcStudyVersion, User

OCAP_ASSIGNABLE_ROLE_CODES = ("qa_supervisor", "qc_manager", "admin")


class SpcOcapService:
    @staticmethod
    def list_assignable_users() -> list[dict[str, Any]]:
        rows = (
            db.session.query(User, Role)
            .join(Role, Role.code == User.role)
            .filter(
                User.is_active.is_(True),
                User.role.in_(OCAP_ASSIGNABLE_ROLE_CODES),
            )
            .order_by(Role.name, User.username, User.id)
            .all()
        )
        return [{
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "role_name": role.name,
        } for user, role in rows]

    @staticmethod
    def _validate_owner_change(
        current_owner_id: int | None, payload: Mapping[str, Any]
    ) -> None:
        if "owner_id" not in payload:
            return
        owner_id = payload["owner_id"]
        if owner_id is None or owner_id == current_owner_id:
            return
        owner = db.session.get(User, owner_id)
        if (
            owner is None
            or not owner.is_active
            or owner.role not in OCAP_ASSIGNABLE_ROLE_CODES
        ):
            raise SpcValidationError(
                "SPC_OCAP_OWNER_NOT_ASSIGNABLE",
                "責任人必須是啟用中的 QA主管、品管經理或系統管理員",
            )
```

在 `save_ocap` 查得既有 OCAP 後、建立新 `SpcOcap` 前呼叫：

```python
current_owner_id = ocap.owner_id if ocap is not None else None
SpcOcapService._validate_owner_change(current_owner_id, payload)
```

- [ ] **Step 4: 執行服務測試並確認通過**

Run: `venv\Scripts\python.exe -m pytest backend\tests\test_services\test_spc_ocap_service.py -q`

Expected: PASS。

- [ ] **Step 5: 提交服務層變更**

```powershell
git add backend/services/spc_ocap_service.py backend/tests/test_services/test_spc_ocap_service.py
git commit -m "修正：限制 SPC OCAP 可指派責任人"
```

### Task 2: SPC 責任人 API 與完整 OCAP 回應

**Files:**
- Modify: `backend/routes/spc_studies.py`
- Test: `backend/tests/test_spc_study_routes.py`

**Interfaces:**
- Consumes: `SpcOcapService.list_assignable_users()`。
- Produces: `GET /api/spc/assignees -> ApiSuccess[list[SpcAssignee]]`。
- Produces: OCAP POST／PATCH `-> ApiSuccess[SpcOcapRecord]`。

- [ ] **Step 1: 新增 API 權限、過濾及完整回應測試**

在 `spc_roles` fixture 增加白名單角色：

```python
Role(code="qa_supervisor", name="QA主管", permissions={"spc.manage": True}),
Role(code="qc_manager", name="品管經理", permissions={"spc.manage": True}),
Role(code="admin", name="系統管理員", permissions={"spc.manage": True}),
Role(code="inspector", name="檢驗員", permissions={"spc.view": True}),
```

新增清單測試：

```python
def test_spc_assignees_require_manage_and_expose_minimal_active_quality_users(
    client, db_session, spc_roles
):
    manager = _user(db_session, "assignee-reader", "spc_manager")
    viewer = _user(db_session, "assignee-viewer", "spc_viewer")
    qa = _user(db_session, "qa-choice", "qa_supervisor")
    qc = _user(db_session, "qc-choice", "qc_manager")
    admin = _user(db_session, "admin-choice", "admin")
    _user(db_session, "inspector-choice", "inspector")
    disabled = _user(db_session, "disabled-choice", "qa_supervisor")
    disabled.is_active = False
    db_session.commit()

    forbidden = client.get("/api/spc/assignees", headers=_headers(viewer))
    response = client.get("/api/spc/assignees", headers=_headers(manager))

    assert forbidden.status_code == 403
    assert response.status_code == 200
    rows = response.get_json()["data"]
    assert {row["id"] for row in rows} == {qa.id, qc.id, admin.id}
    assert set(rows[0]) == {"id", "username", "role", "role_name"}
```

在現有事件追溯測試中，以 API 建立及更新 OCAP，並確認完整欄位：

```python
created = client.post(
    f"/api/spc/events/{event.id}/ocap",
    headers=_headers(manager),
    json={
        "investigation_6m": {"summary": "壓力波動"},
        "owner_id": None,
        "status": "open",
    },
)
assert created.status_code == 200
created_data = created.get_json()["data"]
assert created_data["event_id"] == event.id
assert created_data["investigation_6m"] == {"summary": "壓力波動"}
assert "created_at" in created_data
assert "updated_at" in created_data

updated = client.patch(
    f"/api/spc/ocap/{created_data['id']}",
    headers=_headers(manager),
    json={"process_adjustment": "調整壓力", "status": "open"},
)
assert updated.status_code == 200
assert updated.get_json()["data"]["process_adjustment"] == "調整壓力"
```

- [ ] **Step 2: 執行路由測試並確認失敗**

Run: `venv\Scripts\python.exe -m pytest backend\tests\test_spc_study_routes.py -q`

Expected: FAIL；責任人端點回傳 404，OCAP 回應缺少完整欄位。

- [ ] **Step 3: 實作端點並重用完整序列化器**

在 OCAP 路由前新增：

```python
@spc_studies_bp.get("/api/spc/assignees")
@auth_required
@require_permission("spc.manage")
@_handle_spc_errors
def list_ocap_assignees(current_user):
    return _success(SpcOcapService.list_assignable_users())
```

將建立及更新回應分別改為：

```python
return _success(serialize_ocap(ocap))
```

```python
return _success(serialize_ocap(updated))
```

- [ ] **Step 4: 執行路由與服務測試並確認通過**

Run: `venv\Scripts\python.exe -m pytest backend\tests\test_spc_study_routes.py backend\tests\test_services\test_spc_ocap_service.py -q`

Expected: PASS。

- [ ] **Step 5: 提交 API 變更**

```powershell
git add backend/routes/spc_studies.py backend/tests/test_spc_study_routes.py
git commit -m "功能：新增 SPC OCAP 責任人查詢 API"
```

### Task 3: 前端責任人查詢與下拉選單

**Files:**
- Modify: `src_frontend/src/types/spc.ts`
- Modify: `src_frontend/src/hooks/useSpcStudies.ts`
- Modify: `src_frontend/src/hooks/useSpcStudies.test.tsx`
- Modify: `src_frontend/src/components/spc/SpcOcapOffcanvas.tsx`
- Modify: `src_frontend/src/components/spc/SpcOcapOffcanvas.test.tsx`

**Interfaces:**
- Consumes: `GET /api/spc/assignees` 與完整 OCAP POST／PATCH 回應。
- Produces: `SpcAssignee`、`useSpcAssignees(enabled)`、`useSaveSpcOcap(studyId)`。
- Produces: `SpcOcapOffcanvas` 的 `assignees`、`assigneesLoading`、`assigneesError` props。

- [ ] **Step 1: 新增 hooks 的失敗測試**

擴充匯入並加入兩個測試：

```tsx
import {
  useAnalyzeSpcStudy, useSaveSpcOcap, useSpcAssignees, useSubmitSpcStudy,
} from './useSpcStudies';

it('只在啟用時查詢 SPC 可指派責任人', async () => {
  vi.mocked(api.get).mockResolvedValue({
    data: { success: true, data: [{
      id: 8, username: 'qa-user', role: 'qa_supervisor', role_name: 'QA主管',
    }] },
  });
  const queryClient = new QueryClient();
  const { result } = renderHook(() => useSpcAssignees(true), {
    wrapper: createWrapper(queryClient),
  });

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(api.get).toHaveBeenCalledWith('/spc/assignees');
  expect(result.current.data?.[0].role_name).toBe('QA主管');
});

it('儲存 OCAP 後回傳完整資料並失效化實際研究快取', async () => {
  const ocap = {
    id: 3, event_id: 81, investigation_6m: { summary: '模具磨耗' },
    remeasurement: null, process_adjustment: '更換模具',
    product_disposition: null, owner_id: 8, effectiveness: null,
    status: 'open', created_by: 1, updated_by: 1,
    created_at: '2026-07-19T01:00:00Z', updated_at: '2026-07-19T01:00:00Z',
  };
  vi.mocked(api.patch).mockResolvedValue({ data: { success: true, data: ocap } });
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
  const { result } = renderHook(() => useSaveSpcOcap(9), {
    wrapper: createWrapper(queryClient),
  });

  let returned;
  await act(async () => {
    returned = await result.current.mutateAsync({
      eventId: 81, ocapId: 3, payload: { process_adjustment: '更換模具' },
    });
  });

  expect(returned).toEqual(ocap);
  expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['spcStudy', 9] });
  expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ['spcEvents'] });
  expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: ['spcOcap', 81] });
});
```

- [ ] **Step 2: 新增下拉選單的失敗測試**

將既有測試改為傳入責任人並驗證選項與 payload，再新增歷史值測試：

```tsx
const assignees = [
  { id: 8, username: 'qa-user', role: 'qa_supervisor', role_name: 'QA主管' },
  { id: 9, username: 'qc-user', role: 'qc_manager', role_name: '品管經理' },
];

render(
  <SpcOcapOffcanvas
    show eventId={81} assignees={assignees}
    onHide={vi.fn()} onSave={onSave}
  />,
);
expect(screen.getByLabelText('責任人')).toBeInTheDocument();
expect(screen.getByRole('option', { name: 'qa-user（QA主管）' })).toBeInTheDocument();
fireEvent.change(screen.getByLabelText('責任人'), { target: { value: '9' } });
fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));
expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
  payload: expect.objectContaining({ owner_id: 9 }),
}));

it('保留不在清單中的歷史責任人但禁止重新選取', () => {
  render(
    <SpcOcapOffcanvas
      show eventId={81} assignees={assignees}
      initialValue={{ owner_id: 77 } as never}
      onHide={vi.fn()} onSave={vi.fn()}
    />,
  );
  const historical = screen.getByRole('option', {
    name: '原責任人 ID：77（目前不可指派）',
  });
  expect(historical).toBeDisabled();
  expect(screen.getByLabelText('責任人')).toHaveValue('77');
});
```

- [ ] **Step 3: 執行窄測試並確認失敗**

Run: `npm test -- --run src/hooks/useSpcStudies.test.tsx src/components/spc/SpcOcapOffcanvas.test.tsx`

Workdir: `src_frontend`

Expected: FAIL；新 hook、props 與責任人選單尚不存在。

- [ ] **Step 4: 實作型別與 hooks**

在 `src_frontend/src/types/spc.ts` 增加：

```typescript
export interface SpcAssignee {
  id: number;
  username: string;
  role: 'qa_supervisor' | 'qc_manager' | 'admin';
  role_name: string;
}
```

在 hooks 匯入 `SpcAssignee`、`SpcOcapRecord`，移除 `SpcOcapSummary`，新增與修改：

```typescript
export const useSpcAssignees = (enabled = true) => useQuery({
  queryKey: ['spcAssignees'],
  queryFn: async () => unwrap(
    await api.get<ApiSuccess<SpcAssignee[]>>('/spc/assignees'),
  ),
  enabled,
});

export const useSaveSpcOcap = (studyId: number | null) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ eventId, ocapId, payload }: SpcOcapInput) => unwrap(
      ocapId == null
        ? await api.post<ApiSuccess<SpcOcapRecord>>(`/spc/events/${eventId}/ocap`, payload)
        : await api.patch<ApiSuccess<SpcOcapRecord>>(`/spc/ocap/${ocapId}`, payload),
    ),
    onSuccess: () => {
      if (studyId != null) {
        queryClient.invalidateQueries({ queryKey: ['spcStudy', studyId] });
      }
    },
  });
};
```

- [ ] **Step 5: 將責任人欄位改成選單**

擴充 props：

```typescript
assignees?: SpcAssignee[];
assigneesLoading?: boolean;
assigneesError?: boolean;
```

預設值設為 `assignees = []`、`assigneesLoading = false`、`assigneesError = false`，並以以下選單取代數字欄位：

```tsx
const historicalOwner = ownerId !== ''
  && !assignees.some(assignee => String(assignee.id) === ownerId);

<Form.Group className="mb-3" controlId="ocap-owner">
  <Form.Label>責任人</Form.Label>
  <Form.Select
    value={ownerId}
    disabled={assigneesLoading}
    onChange={event => setOwnerId(event.target.value)}
  >
    <option value="">未指派</option>
    {historicalOwner && (
      <option value={ownerId} disabled>
        原責任人 ID：{ownerId}（目前不可指派）
      </option>
    )}
    {assignees.map(assignee => (
      <option key={assignee.id} value={assignee.id}>
        {assignee.username}（{assignee.role_name}）
      </option>
    ))}
  </Form.Select>
  {assigneesLoading && <Form.Text>正在載入責任人清單…</Form.Text>}
  {assigneesError && (
    <Form.Text className="text-danger">責任人清單載入失敗，請稍後再試。</Form.Text>
  )}
</Form.Group>
```

- [ ] **Step 6: 執行 hooks 與表單測試並確認通過**

Run: `npm test -- --run src/hooks/useSpcStudies.test.tsx src/components/spc/SpcOcapOffcanvas.test.tsx`

Workdir: `src_frontend`

Expected: PASS。

- [ ] **Step 7: 提交前端資料取得與選單**

```powershell
git add src_frontend/src/types/spc.ts src_frontend/src/hooks/useSpcStudies.ts src_frontend/src/hooks/useSpcStudies.test.tsx src_frontend/src/components/spc/SpcOcapOffcanvas.tsx src_frontend/src/components/spc/SpcOcapOffcanvas.test.tsx
git commit -m "功能：新增 SPC OCAP 責任人下拉選單"
```

### Task 4: 儲存後立即同步目前事件

**Files:**
- Modify: `src_frontend/src/components/spc/SpcStudyPanel.tsx`
- Modify: `src_frontend/src/components/spc/SpcStudyPanel.test.tsx`
- Modify: `src_frontend/src/components/spc/SpcOcapOffcanvas.tsx`
- Modify: `src_frontend/src/components/spc/SpcOcapOffcanvas.test.tsx`

**Interfaces:**
- Consumes: `useSpcAssignees(enabled)`、`useSaveSpcOcap(studyId)` 與完整 `SpcOcapRecord`。
- Produces: `replaceEventOcap(version, eventId, ocap) -> SpcStudyResult`，同時更新 `monitoring_limit` 及 `limit_versions`。

- [ ] **Step 1: 新增不可變事件更新與重新開啟測試**

在測試檔新增 hoisted mocks：

```tsx
const saveOcapMock = vi.hoisted(() => vi.fn());
const assigneesState = vi.hoisted(() => ({
  data: [{ id: 8, username: 'qa-user', role: 'qa_supervisor', role_name: 'QA主管' }],
}));
```

更新 hooks mock：

```tsx
useSaveSpcOcap: () => ({
  mutate: saveOcapMock, isPending: false, isError: false,
}),
useSpcAssignees: () => ({
  data: assigneesState.data, isLoading: false, isError: false,
}),
```

新增測試：

```tsx
it('OCAP 儲存後立即替換事件資料，重新開啟不需重新整理', async () => {
  const oldOcap = {
    id: 3, event_id: 81, investigation_6m: { summary: '舊原因' },
    remeasurement: null, process_adjustment: '舊調整', product_disposition: null,
    owner_id: 8, effectiveness: null, status: 'open', created_by: 1,
    updated_by: 1, created_at: '2026-07-19T01:00:00Z',
    updated_at: '2026-07-19T01:00:00Z',
  };
  const newOcap = {
    ...oldOcap, process_adjustment: '新調整',
    updated_at: '2026-07-19T02:00:00Z',
  };
  const ongoing = {
    ...version,
    study_type: 'ongoing',
    status: 'active',
    data_hash: 'current-hash',
    monitoring_limit: {
      id: 8, study_version_id: version.id, revision: 1, chart_type: 'xbar_s',
      limits: {}, status: 'active', approved_by: 1, approved_at: '2026-07-18',
      events: [{
        id: 81, limit_version_id: 8, study_version_id: version.id,
        sample_id: null, chart_kind: 'variation', rule_code: 'beyond_limits',
        point_index: 4, observed_value: 0.8, status: 'investigating',
        created_at: '2026-07-19T00:00:00Z', ocap: oldOcap,
      }],
    },
    limit_versions: [],
  } as SpcStudyResult;
  let latest = ongoing;
  const onVersionChange = vi.fn((value: SpcStudyResult) => { latest = value; });
  saveOcapMock.mockImplementation((_input, options) => options.onSuccess(newOcap));
  const view = render(
    <SpcStudyPanel
      source="shipping" filters={ongoing.filters}
      preview={{ process_stream_key: 'stream-a', data_hash: 'current-hash' } as never}
      version={ongoing} onVersionChange={onVersionChange}
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
  expect(screen.getByLabelText('製程調整')).toHaveValue('舊調整');
  fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));

  await waitFor(() => expect(onVersionChange).toHaveBeenCalled());
  expect(latest.monitoring_limit?.events[0].ocap?.process_adjustment).toBe('新調整');

  view.rerender(
    <SpcStudyPanel
      source="shipping" filters={ongoing.filters}
      preview={{ process_stream_key: 'stream-a', data_hash: 'current-hash' } as never}
      version={latest} onVersionChange={onVersionChange}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: /事件 #81/ }));
  expect(screen.getByLabelText('製程調整')).toHaveValue('新調整');
});
```

- [ ] **Step 2: 執行面板測試並確認舊資料問題可重現**

Run: `npm test -- --run src/components/spc/SpcStudyPanel.test.tsx`

Workdir: `src_frontend`

Expected: FAIL；`onSuccess` 只關閉側欄，父層版本事件仍是舊 OCAP。

- [ ] **Step 3: 實作不可變事件替換函式**

在元件外新增：

```typescript
const replaceLimitEventOcap = (
  limit: SpcLimitVersionSummary,
  eventId: number,
  ocap: SpcOcapRecord,
): SpcLimitVersionSummary => ({
  ...limit,
  events: limit.events?.map(event => (
    event.id === eventId ? { ...event, ocap, status: ocap.status === 'closed' ? 'closed' : 'investigating' } : event
  )),
});

export const replaceEventOcap = (
  version: SpcStudyResult,
  eventId: number,
  ocap: SpcOcapRecord,
): SpcStudyResult => ({
  ...version,
  monitoring_limit: version.monitoring_limit
    ? replaceLimitEventOcap(version.monitoring_limit, eventId, ocap)
    : version.monitoring_limit,
  limit_versions: version.limit_versions?.map(limit =>
    replaceLimitEventOcap(limit, eventId, ocap)),
});
```

補上 `SpcLimitVersionSummary`、`SpcOcapRecord` 型別匯入。

- [ ] **Step 4: 串接責任人查詢、完整回應與錯誤提示**

在取得 `canManage` 後呼叫：

```typescript
const saveOcap = useSaveSpcOcap(version?.study_id ?? null);
const assignees = useSpcAssignees(Boolean(selectedEvent && canManage));
```

將 OCAP 元件 props 與成功處理改成：

```tsx
assignees={assignees.data ?? []}
assigneesLoading={assignees.isLoading}
assigneesError={assignees.isError}
onSave={input => saveOcap.mutate(input, {
  onSuccess: ocap => {
    if (version) {
      onVersionChange(replaceEventOcap(version, selectedEvent.id, ocap));
    }
    setSelectedEvent(null);
  },
})}
```

在側欄儲存按鈕上方顯示 mutation 失敗提示：

```tsx
{saveError && (
  <Alert variant="danger" className="py-2">
    OCAP 儲存失敗，已保留目前輸入，請確認資料後再試。
  </Alert>
)}
```

其中 `SpcOcapOffcanvasProps` 增加 `saveError?: boolean`，面板傳入 `saveError={saveOcap.isError}`。

- [ ] **Step 5: 執行所有 SPC 前端窄測試並確認通過**

Run: `npm test -- --run src/hooks/useSpcStudies.test.tsx src/components/spc/SpcOcapOffcanvas.test.tsx src/components/spc/SpcStudyPanel.test.tsx`

Workdir: `src_frontend`

Expected: PASS。

- [ ] **Step 6: 提交事件同步修正**

```powershell
git add src_frontend/src/components/spc/SpcStudyPanel.tsx src_frontend/src/components/spc/SpcStudyPanel.test.tsx src_frontend/src/components/spc/SpcOcapOffcanvas.tsx src_frontend/src/components/spc/SpcOcapOffcanvas.test.tsx
git commit -m "修正：立即同步 SPC OCAP 儲存結果"
```

### Task 5: 全量驗證與交付檢查

**Files:**
- Verify only; no new files expected.

**Interfaces:**
- Consumes: Tasks 1–4 的完整後端與前端變更。
- Produces: 可提交與推送的驗證證據。

- [ ] **Step 1: 執行後端全量測試**

Run: `venv\Scripts\python.exe -m pytest backend\tests -q`

Expected: PASS，沒有失敗或錯誤。

- [ ] **Step 2: 執行前端 lint**

Run: `npm run lint`

Workdir: `src_frontend`

Expected: exit code 0，沒有 ESLint error 或 warning。

- [ ] **Step 3: 執行前端全量測試**

Run: `npm test`

Workdir: `src_frontend`

Expected: PASS，所有 Vitest 測試通過。

- [ ] **Step 4: 執行前端 production build**

Run: `npm run build`

Workdir: `src_frontend`

Expected: exit code 0，TypeScript 與 Vite build 成功。

- [ ] **Step 5: 執行依賴與差異檢查**

Run: `npm audit`

Workdir: `src_frontend`

Expected: exit code 0，沒有已知漏洞。

Run: `git diff --check`

Workdir: repository root

Expected: 沒有輸出。

- [ ] **Step 6: 檢查提交與工作樹範圍**

Run: `git status --short`

Expected: 只允許既有未追蹤的 `tmp/`；所有功能檔案均已提交，沒有把 `tmp/` 納入版本控制。
