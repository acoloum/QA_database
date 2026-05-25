# 擠壓公差管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增擠壓製程公差管理功能（CRUD），並整合至現場巡檢頁面做即時 NG 比對。

**Architecture:** 後端新增獨立 Blueprint (`extrusion_tolerance_bp`)、Service、兩張 DB 資料表（主檔+明細）；前端新增管理頁面及巡檢 Modal 內嵌即時 NG 標示。比對邏輯採 3 優先等級（材質+規格精確 → 前兩段 → 無規格通用），不使用廠商維度。

**Tech Stack:** Flask 3.1 + SQLAlchemy / React 19 + TypeScript + TanStack React Query + React Bootstrap

---

## 檔案地圖

### 新增檔案
| 檔案 | 說明 |
|------|------|
| `backend/migration/06_add_extrusion_tolerance.sql` | 建立擠壓公差主檔、明細表 |
| `backend/services/extrusion_tolerance_service.py` | CRUD + check 邏輯 |
| `backend/routes/extrusion_tolerance.py` | Blueprint + 5 個端點 |
| `src_frontend/src/hooks/useExtrusionTolerance.ts` | React Query hooks |
| `src_frontend/src/pages/extrusion-tolerance/ExtrusionTolerancePage.tsx` | 管理列表頁 |
| `src_frontend/src/components/extrusion-tolerance/ExtrusionToleranceModal.tsx` | 新增/編輯 Modal |
| `src_frontend/src/components/extrusion-tolerance/ViewExtrusionToleranceModal.tsx` | 查看詳細 Modal |

### 修改檔案
| 檔案 | 修改內容 |
|------|----------|
| `backend/models.py` | 新增 `ExtrusionToleranceMain`、`ExtrusionToleranceDetail` 兩個 ORM 類別 |
| `backend/app.py` | 註冊 `extrusion_tolerance_bp` |
| `src_frontend/src/App.tsx` | 新增 `/extrusion-tolerance` 路由 |
| `src_frontend/src/components/Sidebar.tsx` | 新增「擠壓公差」選單項目 |
| `src_frontend/src/components/patrol/PatrolModal.tsx` | 整合擠壓公差即時 NG 比對 |

---

## Task 1: 資料庫 Migration

**Files:**
- Create: `backend/migration/06_add_extrusion_tolerance.sql`

- [ ] **Step 1: 建立 SQL 檔**

```sql
-- 建立擠壓公差主檔
CREATE TABLE IF NOT EXISTS "擠壓公差主檔" (
    "識別碼"   SERIAL PRIMARY KEY,
    "材質"     VARCHAR NOT NULL,
    "規格"     VARCHAR,
    "備註"     VARCHAR,
    "建立日期" DATE DEFAULT CURRENT_DATE
);

-- 建立擠壓公差明細
CREATE TABLE IF NOT EXISTS "擠壓公差明細" (
    "識別碼"   SERIAL PRIMARY KEY,
    "主檔ID"   INTEGER NOT NULL REFERENCES "擠壓公差主檔"("識別碼") ON DELETE CASCADE,
    "測量項目" VARCHAR NOT NULL,
    "測量位置" VARCHAR,
    "公差下限" NUMERIC,
    "公差上限" NUMERIC,
    "標準值"   NUMERIC,
    "單位"     VARCHAR DEFAULT 'mm'
);
```

- [ ] **Step 2: 套用 migration**

```bash
cd backend
psql -U postgres -d qa_database -f migration/06_add_extrusion_tolerance.sql
```

預期輸出：`CREATE TABLE` × 2

- [ ] **Step 3: 驗證資料表存在**

```bash
psql -U postgres -d qa_database -c "\dt 擠壓公差*"
```

預期：列出兩張資料表

---

## Task 2: Backend Models

**Files:**
- Modify: `backend/models.py`（在 `VendorToleranceDetail` 類別後方新增）

- [ ] **Step 1: 新增兩個 ORM 類別至 models.py**

在 `VendorToleranceDetail` 類別結尾後新增：

```python
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
    """擠壓公差明細"""
    __tablename__ = '擠壓公差明細'
    id = db.Column('識別碼', db.Integer, primary_key=True)
    main_id = db.Column('主檔ID', db.Integer, db.ForeignKey('擠壓公差主檔.識別碼'), nullable=False)
    item = db.Column('測量項目', db.String, nullable=False)
    position = db.Column('測量位置', db.String)
    tolerance_min = db.Column('公差下限', db.Numeric)
    tolerance_max = db.Column('公差上限', db.Numeric)
    std_val = db.Column('標準值', db.Numeric)
    unit = db.Column('單位', db.String, default='mm')
```

- [ ] **Step 2: 確認 Flask 可正常啟動（models import 無錯誤）**

```bash
# 從專案根目錄執行（C:\QC_Database）
python -c "from backend.models import ExtrusionToleranceMain, ExtrusionToleranceDetail; print('OK')"
```

預期：`OK`

---

## Task 3: Backend Service

**Files:**
- Create: `backend/services/extrusion_tolerance_service.py`

- [ ] **Step 1: 建立 Service 檔案**

```python
from typing import Dict, Any, List
from sqlalchemy.orm import joinedload
from ..extensions import db
from ..models import ExtrusionToleranceMain, ExtrusionToleranceDetail
from ..utils import format_value


class ExtrusionToleranceService:

    @staticmethod
    def _normalize_spec(s: str) -> str:
        """標準化規格字串（統一分隔符號）"""
        if not s:
            return ''
        s = str(s).strip().replace('×', '*').replace('x', '*').replace('X', '*')
        while '**' in s:
            s = s.replace('**', '*')
        return s.strip()

    @staticmethod
    def search(args: Dict[str, Any]) -> Dict[str, Any]:
        """列表查詢（分頁）"""
        query = ExtrusionToleranceMain.query
        if args.get('material'):
            query = query.filter(ExtrusionToleranceMain.material.like(f"%{args['material']}%"))
        if args.get('spec'):
            query = query.filter(ExtrusionToleranceMain.spec.like(f"%{args['spec']}%"))

        page = int(args.get('page', 1))
        page_size = int(args.get('page_size', 20))
        total = query.count()
        pagination = query.order_by(ExtrusionToleranceMain.id.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        data = [
            {
                "識別碼": t.id,
                "材質": t.material,
                "規格": t.spec or '',
                "備註": t.note or '',
                "建立日期": format_value(t.created_at),
            }
            for t in pagination.items
        ]
        return {"success": True, "data": data, "total": total, "page": page,
                "page_size": page_size, "total_pages": pagination.pages}

    @staticmethod
    def get_detail(tolerance_id: int) -> Dict[str, Any]:
        """取得單筆主檔 + 明細"""
        t = ExtrusionToleranceMain.query.options(
            joinedload(ExtrusionToleranceMain.details)
        ).get(tolerance_id)
        if not t:
            raise ValueError("找不到該筆擠壓公差資料")

        main = {
            "識別碼": t.id,
            "材質": t.material,
            "規格": t.spec or '',
            "備註": t.note or '',
            "建立日期": format_value(t.created_at),
        }
        details = [
            {
                "識別碼": d.id,
                "測量項目": d.item,
                "測量位置": d.position or '',
                "公差下限": format_value(d.tolerance_min),
                "公差上限": format_value(d.tolerance_max),
                "標準值": format_value(d.std_val),
                "單位": d.unit or 'mm',
            }
            for d in sorted(t.details, key=lambda x: x.id)
        ]
        return {"success": True, "main": main, "details": details}

    @staticmethod
    def add(data: Dict[str, Any]) -> int:
        """新增主檔 + 明細"""
        main = ExtrusionToleranceMain(
            material=data.get('材質'),
            spec=data.get('規格') or None,
            note=data.get('備註') or None,
            created_at=data.get('建立日期') or None,
        )
        db.session.add(main)
        db.session.flush()

        for d in data.get('details', []):
            db.session.add(ExtrusionToleranceDetail(
                main_id=main.id,
                item=d.get('測量項目'),
                position=d.get('測量位置') or None,
                tolerance_min=d.get('公差下限') or None,
                tolerance_max=d.get('公差上限') or None,
                std_val=d.get('標準值') or None,
                unit=d.get('單位', 'mm'),
            ))

        db.session.commit()
        return main.id

    @staticmethod
    def update(tolerance_id: int, data: Dict[str, Any]) -> bool:
        """更新主檔 + 明細（刪除重建明細）"""
        t = ExtrusionToleranceMain.query.get(tolerance_id)
        if not t:
            raise ValueError("找不到擠壓公差資料")

        t.material = data.get('材質')
        t.spec = data.get('規格') or None
        t.note = data.get('備註') or None
        t.created_at = data.get('建立日期') or None

        ExtrusionToleranceDetail.query.filter_by(main_id=tolerance_id).delete()
        for d in data.get('details', []):
            db.session.add(ExtrusionToleranceDetail(
                main_id=t.id,
                item=d.get('測量項目'),
                position=d.get('測量位置') or None,
                tolerance_min=d.get('公差下限') or None,
                tolerance_max=d.get('公差上限') or None,
                std_val=d.get('標準值') or None,
                unit=d.get('單位', 'mm'),
            ))

        db.session.commit()
        return True

    @staticmethod
    def delete(tolerance_id: int) -> bool:
        """刪除（CASCADE 自動刪明細）"""
        t = ExtrusionToleranceMain.query.get(tolerance_id)
        if t:
            db.session.delete(t)
            db.session.commit()
        return True

    @staticmethod
    def get_options() -> Dict[str, Any]:
        """取得篩選選項（材質、規格清單）"""
        materials = [r[0] for r in db.session.query(ExtrusionToleranceMain.material)
                     .distinct().order_by(ExtrusionToleranceMain.material).all() if r[0]]
        specs = [r[0] for r in db.session.query(ExtrusionToleranceMain.spec)
                 .distinct().filter(ExtrusionToleranceMain.spec != None,
                                    ExtrusionToleranceMain.spec != '')
                 .order_by(ExtrusionToleranceMain.spec).all()]
        return {"materials": materials, "specs": specs}

    @staticmethod
    def check(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        依材質+規格查詢對應擠壓公差。
        優先等級：
          1. 材質 + 規格完全匹配
          2. 材質 + 規格前兩段匹配（OD*壁厚 相同，長度不同）
          3. 材質 + 無規格（通用）
        """
        material = args.get('material')
        if not material:
            return {"success": False, "error": "材質為必填參數"}

        normalize = ExtrusionToleranceService._normalize_spec
        input_spec = normalize(args.get('spec', ''))

        candidates = ExtrusionToleranceMain.query.options(
            joinedload(ExtrusionToleranceMain.details)
        ).filter_by(material=material).all()

        buckets: Dict[int, list] = {1: [], 2: [], 3: []}

        for t in candidates:
            t_spec = normalize(t.spec or '')
            has_spec = t_spec != ''

            if has_spec:
                if t_spec == input_spec:
                    buckets[1].append(t)
                else:
                    # 前兩段比對（外徑*壁厚）
                    p_in = input_spec.split('*')
                    p_t = t_spec.split('*')
                    if (len(p_in) >= 2 and len(p_t) >= 2
                            and p_in[0] == p_t[0] and p_in[1] == p_t[1]):
                        buckets[2].append(t)
            else:
                buckets[3].append(t)

        matched = None
        priority = None
        for p in (1, 2, 3):
            if buckets[p]:
                matched = buckets[p][0]
                priority = p
                break

        if not matched:
            return {"success": True, "found": False, "message": "找不到對應的擠壓公差標準"}

        p_names = {
            1: "材質+規格完全匹配",
            2: "材質+規格前兩段匹配",
            3: "材質+無規格（通用）",
        }

        return {
            "success": True,
            "found": True,
            "tolerance_id": matched.id,
            "material": matched.material,
            "spec": matched.spec or '',
            "tolerances": [
                {
                    "項目": d.item,
                    "位置": d.position or '',
                    "公差下限": float(d.tolerance_min) if d.tolerance_min is not None else None,
                    "公差上限": float(d.tolerance_max) if d.tolerance_max is not None else None,
                    "標準值": float(d.std_val) if d.std_val is not None else None,
                    "單位": d.unit or 'mm',
                }
                for d in matched.details
            ],
            "matched_priority": priority,
            "priority_name": p_names[priority],
        }
```

- [ ] **Step 2: 確認 import 無語法錯誤**

```bash
# 從專案根目錄執行（C:\QC_Database）
python -c "from backend.services.extrusion_tolerance_service import ExtrusionToleranceService; print('OK')"
```

---

## Task 4: Backend Routes + Blueprint 註冊

**Files:**
- Create: `backend/routes/extrusion_tolerance.py`
- Modify: `backend/app.py`

- [ ] **Step 1: 建立 Routes 檔案**

```python
from flask import Blueprint, jsonify, request
from ..services.extrusion_tolerance_service import ExtrusionToleranceService
from ..utils import auth_required, handle_db_error

extrusion_tolerance_bp = Blueprint('extrusion_tolerance', __name__)


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/search', methods=['GET'])
@auth_required
def search():
    """查詢擠壓公差列表"""
    return jsonify(ExtrusionToleranceService.search(request.args))


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/<int:id>', methods=['GET'])
@auth_required
def get_detail(id):
    """取得單筆擠壓公差詳細"""
    try:
        return jsonify(ExtrusionToleranceService.get_detail(id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/add', methods=['POST'])
@auth_required
def add():
    """新增擠壓公差"""
    try:
        new_id = ExtrusionToleranceService.add(request.json)
        return jsonify({"success": True, "id": new_id})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/update/<int:id>', methods=['POST'])
@auth_required
def update(id):
    """更新擠壓公差"""
    try:
        ExtrusionToleranceService.update(id, request.json)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/delete/<int:id>', methods=['POST'])
@auth_required
def delete(id):
    """刪除擠壓公差"""
    try:
        ExtrusionToleranceService.delete(id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/options', methods=['GET'])
@auth_required
def get_options():
    """取得材質、規格選項"""
    try:
        return jsonify(ExtrusionToleranceService.get_options())
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500


@extrusion_tolerance_bp.route('/api/extrusion-tolerance/check', methods=['GET'])
@auth_required
def check():
    """依材質+規格查詢對應公差（供巡檢 NG 比對用）"""
    try:
        return jsonify(ExtrusionToleranceService.check(request.args))
    except Exception as e:
        return jsonify({"error": handle_db_error(e)}), 500
```

- [ ] **Step 2: 在 app.py 中 import 並註冊 Blueprint**

在 `backend/app.py` 中，`from .routes.tolerance import tolerance_bp` 下方新增：

```python
from .routes.extrusion_tolerance import extrusion_tolerance_bp
```

在 `app.register_blueprint(tolerance_bp)` 下方新增：

```python
app.register_blueprint(extrusion_tolerance_bp)
```

- [ ] **Step 3: 啟動後端，確認端點可訪問**

```bash
cd backend && python app.py &
curl -s http://localhost:5001/api/extrusion-tolerance/options
```

預期：回傳 `{"materials": [], "specs": []}` （表格為空，但端點正常）

- [ ] **Step 4: Commit**

```bash
git add backend/migration/06_add_extrusion_tolerance.sql \
        backend/models.py \
        backend/services/extrusion_tolerance_service.py \
        backend/routes/extrusion_tolerance.py \
        backend/app.py
git commit -m "feat(extrusion-tolerance): 新增擠壓公差後端 models、service、routes"
```

---

## Task 5: 前端 Hooks

**Files:**
- Create: `src_frontend/src/hooks/useExtrusionTolerance.ts`

- [ ] **Step 1: 建立 hooks 檔案**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../services/api';
import toast from 'react-hot-toast';

// ---- 型別定義 ----

export interface ExtrusionToleranceItem {
    識別碼: number;
    材質: string;
    規格: string;
    備註: string;
    建立日期: string;
}

export interface ExtrusionToleranceDetailItem {
    識別碼?: number;
    測量項目: string;
    測量位置: string;
    公差下限: number | null;
    公差上限: number | null;
    標準值: number | null;
    單位: string;
}

export interface ExtrusionToleranceDetailResponse {
    main: ExtrusionToleranceItem;
    details: ExtrusionToleranceDetailItem[];
}

export interface ExtrusionToleranceDetailResponse {
    success: boolean;
    main: ExtrusionToleranceItem;
    details: ExtrusionToleranceDetailItem[];
}

export interface ExtrusionToleranceCheckResult {
    found: boolean;
    tolerance_id?: number;
    material?: string;
    spec?: string;
    tolerances?: {
        項目: string;
        位置: string;
        公差下限: number | null;
        公差上限: number | null;
        標準值: number | null;
        單位: string;
    }[];
    priority_name?: string;
}

// ---- Hooks ----

export const useExtrusionToleranceList = (params: {
    page: number;
    page_size: number;
    material?: string;
    spec?: string;
}) =>
    useQuery({
        queryKey: ['extrusionToleranceList', params],
        queryFn: async () => {
            const p = new URLSearchParams();
            if (params.material) p.append('material', params.material);
            if (params.spec) p.append('spec', params.spec);
            p.append('page', params.page.toString());
            p.append('page_size', params.page_size.toString());
            const res = await api.get(`/extrusion-tolerance/search?${p}`);
            return res.data;
        },
        placeholderData: (prev) => prev,
    });

export const useExtrusionToleranceDetail = (id: number | null) =>
    useQuery({
        queryKey: ['extrusionToleranceDetail', id],
        queryFn: async () => {
            if (!id) return null;
            const res = await api.get(`/extrusion-tolerance/${id}`);
            return res.data as ExtrusionToleranceDetailResponse;
        },
        enabled: !!id,
    });

export const useExtrusionToleranceOptions = () =>
    useQuery({
        queryKey: ['extrusionToleranceOptions'],
        queryFn: async () => {
            const res = await api.get('/extrusion-tolerance/options');
            return res.data as { materials: string[]; specs: string[] };
        },
        staleTime: 5 * 60 * 1000,
    });

export const useAddExtrusionTolerance = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: object) => {
            const res = await api.post('/extrusion-tolerance/add', data);
            return res.data;
        },
        onSuccess: () => {
            toast.success('新增成功');
            qc.invalidateQueries({ queryKey: ['extrusionToleranceList'] });
            qc.invalidateQueries({ queryKey: ['extrusionToleranceOptions'] });
        },
    });
};

export const useUpdateExtrusionTolerance = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: number; data: object }) => {
            const res = await api.post(`/extrusion-tolerance/update/${id}`, data);
            return res.data;
        },
        onSuccess: (_d, vars) => {
            toast.success('更新成功');
            qc.invalidateQueries({ queryKey: ['extrusionToleranceList'] });
            qc.invalidateQueries({ queryKey: ['extrusionToleranceDetail', vars.id] });
        },
    });
};

export const useDeleteExtrusionTolerance = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: number) => {
            const res = await api.post(`/extrusion-tolerance/delete/${id}`);
            return res.data;
        },
        onSuccess: () => {
            toast.success('刪除成功');
            qc.invalidateQueries({ queryKey: ['extrusionToleranceList'] });
        },
    });
};

export const useExtrusionToleranceCheck = (material: string, spec: string) =>
    useQuery({
        queryKey: ['extrusionToleranceCheck', material, spec],
        queryFn: async () => {
            const p = new URLSearchParams({ material, spec });
            const res = await api.get(`/extrusion-tolerance/check?${p}`);
            return res.data as { success: boolean } & ExtrusionToleranceCheckResult;
        },
        enabled: !!material,   // 有材質才查
        staleTime: 60 * 1000,
    });
```

- [ ] **Step 2: 確認 TypeScript 編譯無錯誤**

```bash
cd src_frontend && npm run build 2>&1 | tail -5
```

預期：`✓ built in` 或無型別錯誤

---

## Task 6: 擠壓公差 CRUD 頁面

**Files:**
- Create: `src_frontend/src/pages/extrusion-tolerance/ExtrusionTolerancePage.tsx`
- Create: `src_frontend/src/components/extrusion-tolerance/ExtrusionToleranceModal.tsx`
- Create: `src_frontend/src/components/extrusion-tolerance/ViewExtrusionToleranceModal.tsx`

### Step 6-1: ViewExtrusionToleranceModal（唯讀查看）

- [ ] **建立 ViewExtrusionToleranceModal.tsx**

```tsx
import { Modal, Table, Badge } from 'react-bootstrap';
import { useExtrusionToleranceDetail } from '../../hooks/useExtrusionTolerance';

interface Props {
    show: boolean;
    id: number | null;
    onClose: () => void;
}

const ViewExtrusionToleranceModal = ({ show, id, onClose }: Props) => {
    const { data, isLoading } = useExtrusionToleranceDetail(id);

    return (
        <Modal show={show} onHide={onClose} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>擠壓公差詳細</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {isLoading && <p>載入中…</p>}
                {data && (
                    <>
                        <dl className="row mb-3">
                            <dt className="col-sm-2">材質</dt>
                            <dd className="col-sm-4">{data.main.材質}</dd>
                            <dt className="col-sm-2">規格</dt>
                            <dd className="col-sm-4">{data.main.規格 || '（通用）'}</dd>
                            <dt className="col-sm-2">備註</dt>
                            <dd className="col-sm-10">{data.main.備註}</dd>
                        </dl>
                        <Table bordered size="sm">
                            <thead className="table-secondary">
                                <tr>
                                    <th>測量項目</th>
                                    <th>測量位置</th>
                                    <th>公差下限</th>
                                    <th>公差上限</th>
                                    <th>標準值</th>
                                    <th>單位</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.details.map((d, i) => (
                                    <tr key={i}>
                                        <td>{d.測量項目}</td>
                                        <td>{d.測量位置}</td>
                                        <td>{d.公差下限 ?? '-'}</td>
                                        <td>{d.公差上限 ?? '-'}</td>
                                        <td>{d.標準值 ?? '-'}</td>
                                        <td><Badge bg="secondary">{d.單位}</Badge></td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    </>
                )}
            </Modal.Body>
        </Modal>
    );
};

export default ViewExtrusionToleranceModal;
```

### Step 6-2: ExtrusionToleranceModal（新增/編輯）

- [ ] **建立 ExtrusionToleranceModal.tsx**

```tsx
import { useState, useEffect, useCallback } from 'react';
import { Modal, Button, Form, Row, Col, Table } from 'react-bootstrap';
import {
    useExtrusionToleranceDetail,
    useAddExtrusionTolerance,
    useUpdateExtrusionTolerance,
} from '../../hooks/useExtrusionTolerance';

interface DetailRow {
    測量項目: string;
    測量位置: string;
    公差下限: string;
    公差上限: string;
    標準值: string;
    單位: string;
}

const ITEMS = ['外徑', '內徑', '厚度'];
const POSITIONS = ['前段', '中段', '後段'];

const emptyRow = (): DetailRow => ({
    測量項目: '外徑',
    測量位置: '前段',
    公差下限: '',
    公差上限: '',
    標準值: '',
    單位: 'mm',
});

interface Props {
    show: boolean;
    editId: number | null;
    onClose: () => void;
    onSuccess: () => void;
}

const ExtrusionToleranceModal = ({ show, editId, onClose, onSuccess }: Props) => {
    const { data: detail, isLoading } = useExtrusionToleranceDetail(editId);
    const addMutation = useAddExtrusionTolerance();
    const updateMutation = useUpdateExtrusionTolerance();

    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');
    const [note, setNote] = useState('');
    const [createdAt, setCreatedAt] = useState(new Date().toISOString().split('T')[0]);
    const [rows, setRows] = useState<DetailRow[]>([emptyRow()]);

    const reset = useCallback(() => {
        setMaterial('');
        setSpec('');
        setNote('');
        setCreatedAt(new Date().toISOString().split('T')[0]);
        setRows([emptyRow()]);
    }, []);

    useEffect(() => {
        if (!show) return;
        if (!editId) { reset(); return; }
        if (!detail) return;
        const m = detail.main;
        setMaterial(m.材質);
        setSpec(m.規格 || '');
        setNote(m.備註 || '');
        setCreatedAt(m.建立日期?.split('T')[0] || new Date().toISOString().split('T')[0]);
        setRows(
            detail.details.length > 0
                ? detail.details.map((d) => ({
                      測量項目: d.測量項目,
                      測量位置: d.測量位置,
                      公差下限: d.公差下限 != null ? String(d.公差下限) : '',
                      公差上限: d.公差上限 != null ? String(d.公差上限) : '',
                      標準值: d.標準值 != null ? String(d.標準值) : '',
                      單位: d.單位 || 'mm',
                  }))
                : [emptyRow()]
        );
    }, [show, editId, detail, reset]);

    const updateRow = (idx: number, field: keyof DetailRow, val: string) => {
        setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: val } : r)));
    };

    const handleSubmit = async () => {
        if (!material.trim()) { alert('材質為必填'); return; }
        const payload = {
            材質: material.trim(),
            規格: spec.trim() || null,
            備註: note.trim() || null,
            建立日期: createdAt,
            details: rows.map((r) => ({
                測量項目: r.測量項目,
                測量位置: r.測量位置,
                公差下限: r.公差下限 !== '' ? parseFloat(r.公差下限) : null,
                公差上限: r.公差上限 !== '' ? parseFloat(r.公差上限) : null,
                標準值: r.標準值 !== '' ? parseFloat(r.標準值) : null,
                單位: r.單位 || 'mm',
            })),
        };
        try {
            if (editId) {
                await updateMutation.mutateAsync({ id: editId, data: payload });
            } else {
                await addMutation.mutateAsync(payload);
            }
            onSuccess();
            onClose();
        } catch {
            // toast 由 mutation onError 處理
        }
    };

    return (
        <Modal show={show} onHide={onClose} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>{editId ? '編輯' : '新增'}擠壓公差</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {isLoading && editId ? (
                    <p>載入中…</p>
                ) : (
                    <>
                        <Row className="mb-2">
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>材質 <span className="text-danger">*</span></Form.Label>
                                    <Form.Control value={material} onChange={(e) => setMaterial(e.target.value)} placeholder="如 6063" />
                                </Form.Group>
                            </Col>
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>規格</Form.Label>
                                    <Form.Control value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="如 62.5*2.3（留空=通用）" />
                                </Form.Group>
                            </Col>
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>建立日期</Form.Label>
                                    <Form.Control type="date" value={createdAt} onChange={(e) => setCreatedAt(e.target.value)} />
                                </Form.Group>
                            </Col>
                            <Col md={3}>
                                <Form.Group>
                                    <Form.Label>備註</Form.Label>
                                    <Form.Control value={note} onChange={(e) => setNote(e.target.value)} />
                                </Form.Group>
                            </Col>
                        </Row>

                        <Table bordered size="sm" className="mt-3">
                            <thead className="table-secondary">
                                <tr>
                                    <th>測量項目</th>
                                    <th>測量位置</th>
                                    <th>公差下限</th>
                                    <th>公差上限</th>
                                    <th>標準值</th>
                                    <th>單位</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((r, i) => (
                                    <tr key={i}>
                                        <td>
                                            <Form.Select size="sm" value={r.測量項目} onChange={(e) => updateRow(i, '測量項目', e.target.value)}>
                                                {ITEMS.map((it) => <option key={it}>{it}</option>)}
                                            </Form.Select>
                                        </td>
                                        <td>
                                            <Form.Select size="sm" value={r.測量位置} onChange={(e) => updateRow(i, '測量位置', e.target.value)}>
                                                {POSITIONS.map((p) => <option key={p}>{p}</option>)}
                                            </Form.Select>
                                        </td>
                                        <td><Form.Control size="sm" type="number" value={r.公差下限} onChange={(e) => updateRow(i, '公差下限', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" value={r.公差上限} onChange={(e) => updateRow(i, '公差上限', e.target.value)} /></td>
                                        <td><Form.Control size="sm" type="number" value={r.標準值} onChange={(e) => updateRow(i, '標準值', e.target.value)} /></td>
                                        <td>
                                            <Form.Select size="sm" value={r.單位} onChange={(e) => updateRow(i, '單位', e.target.value)}>
                                                <option>mm</option>
                                            </Form.Select>
                                        </td>
                                        <td>
                                            <Button size="sm" variant="outline-danger" onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}>✕</Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                        <Button size="sm" variant="outline-secondary" onClick={() => setRows((prev) => [...prev, emptyRow()])}>
                            + 新增明細列
                        </Button>
                    </>
                )}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onClose}>取消</Button>
                <Button variant="primary" onClick={handleSubmit} disabled={addMutation.isPending || updateMutation.isPending}>
                    {editId ? '更新' : '新增'}
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default ExtrusionToleranceModal;
```

### Step 6-3: ExtrusionTolerancePage（列表管理）

- [ ] **建立 ExtrusionTolerancePage.tsx**

```tsx
import { useState } from 'react';
import { Button, Card, Table, Form, Row, Col, Pagination } from 'react-bootstrap';
import {
    useExtrusionToleranceList,
    useDeleteExtrusionTolerance,
} from '../../hooks/useExtrusionTolerance';
import ExtrusionToleranceModal from '../../components/extrusion-tolerance/ExtrusionToleranceModal';
import ViewExtrusionToleranceModal from '../../components/extrusion-tolerance/ViewExtrusionToleranceModal';

const ExtrusionTolerancePage = () => {
    const [page, setPage] = useState(1);
    const [material, setMaterial] = useState('');
    const [spec, setSpec] = useState('');

    const { data: result, isLoading, refetch } = useExtrusionToleranceList({
        page, page_size: 20, material, spec,
    });
    const deleteMutation = useDeleteExtrusionTolerance();

    const [showModal, setShowModal] = useState(false);
    const [editId, setEditId] = useState<number | null>(null);
    const [showViewModal, setShowViewModal] = useState(false);
    const [viewId, setViewId] = useState<number | null>(null);

    const handleSearch = () => { setPage(1); refetch(); };
    const handleAdd = () => { setEditId(null); setShowModal(true); };
    const handleEdit = (id: number) => { setEditId(id); setShowModal(true); };
    const handleView = (id: number) => { setViewId(id); setShowViewModal(true); };
    const handleDelete = (id: number) => {
        if (!window.confirm('確定要刪除此筆擠壓公差資料？')) return;
        deleteMutation.mutate(id);
    };

    const rows: any[] = result?.data || [];
    const totalPages = result?.total_pages || 1;

    return (
        <div>
            <div className="d-flex justify-content-between align-items-center mb-3">
                <h4>擠壓公差管理</h4>
                <Button variant="primary" size="sm" onClick={handleAdd}>+ 新增</Button>
            </div>

            <Card className="mb-3">
                <Card.Body>
                    <Row className="g-2 align-items-end">
                        <Col md={3}>
                            <Form.Label>材質</Form.Label>
                            <Form.Control size="sm" value={material} onChange={(e) => setMaterial(e.target.value)} placeholder="模糊搜尋" />
                        </Col>
                        <Col md={3}>
                            <Form.Label>規格</Form.Label>
                            <Form.Control size="sm" value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="如 62.5*2.3" />
                        </Col>
                        <Col md={2}>
                            <Button size="sm" onClick={handleSearch}>查詢</Button>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>

            <Card>
                <Card.Body>
                    {isLoading ? (
                        <p>載入中…</p>
                    ) : (
                        <Table bordered hover size="sm">
                            <thead className="table-secondary">
                                <tr>
                                    <th>材質</th>
                                    <th>規格</th>
                                    <th>備註</th>
                                    <th>建立日期</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.length === 0 ? (
                                    <tr><td colSpan={5} className="text-center text-muted">無資料</td></tr>
                                ) : rows.map((r: any) => (
                                    <tr key={r.識別碼}>
                                        <td>{r.材質}</td>
                                        <td>{r.規格 || <span className="text-muted">（通用）</span>}</td>
                                        <td>{r.備註}</td>
                                        <td>{r.建立日期}</td>
                                        <td>
                                            <Button size="sm" variant="outline-info" className="me-1" onClick={() => handleView(r.識別碼)}>查看</Button>
                                            <Button size="sm" variant="outline-primary" className="me-1" onClick={() => handleEdit(r.識別碼)}>編輯</Button>
                                            <Button size="sm" variant="outline-danger" onClick={() => handleDelete(r.識別碼)}>刪除</Button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </Table>
                    )}

                    {totalPages > 1 && (
                        <Pagination size="sm">
                            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
                                <Pagination.Item key={p} active={p === page} onClick={() => setPage(p)}>{p}</Pagination.Item>
                            ))}
                        </Pagination>
                    )}
                </Card.Body>
            </Card>

            <ExtrusionToleranceModal
                show={showModal}
                editId={editId}
                onClose={() => setShowModal(false)}
                onSuccess={() => refetch()}
            />
            <ViewExtrusionToleranceModal
                show={showViewModal}
                id={viewId}
                onClose={() => setShowViewModal(false)}
            />
        </div>
    );
};

export default ExtrusionTolerancePage;
```

- [ ] **Step 4: TypeScript 編譯確認**

```bash
cd src_frontend && npm run build 2>&1 | tail -5
```

---

## Task 7: 路由 & 側邊欄

**Files:**
- Modify: `src_frontend/src/App.tsx`
- Modify: `src_frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: 在 App.tsx 新增 import 及路由**

在 `import TolerancePage` 下方新增：
```tsx
import ExtrusionTolerancePage from './pages/extrusion-tolerance/ExtrusionTolerancePage';
```

在 `<Route path="/tolerance" element={<TolerancePage />} />` 下方新增：
```tsx
<Route path="/extrusion-tolerance" element={<ExtrusionTolerancePage />} />
```

- [ ] **Step 2: 在 Sidebar.tsx 新增選單項目**

在 `{ title: '公差管理', path: '/tolerance', icon: 'fa-ruler-combined' }` 下方新增：
```ts
{ title: '擠壓公差', path: '/extrusion-tolerance', icon: 'fa-compress-alt' },
```

- [ ] **Step 3: 啟動前端確認頁面可正常渲染**

```bash
cd src_frontend && npm run dev
```

瀏覽 `http://localhost:5173/extrusion-tolerance`，確認頁面出現、CRUD 操作可用。

- [ ] **Step 4: Commit**

```bash
git add src_frontend/src/hooks/useExtrusionTolerance.ts \
        src_frontend/src/pages/extrusion-tolerance/ \
        src_frontend/src/components/extrusion-tolerance/ \
        src_frontend/src/App.tsx \
        src_frontend/src/components/Sidebar.tsx
git commit -m "feat(extrusion-tolerance): 新增擠壓公差管理前端頁面與選單"
```

---

## Task 8: 巡檢 Modal 整合即時 NG 比對

**Files:**
- Modify: `src_frontend/src/components/patrol/PatrolModal.tsx`

**目標：** PatrolModal 中，當 `material` 有值時，自動呼叫 `/extrusion-tolerance/check`，取得對應擠壓公差，並在 `renderTableRows()` 中對 NG 的輸入框加上紅色背景（不新增欄位，改用顏色標示，避免表格過寬）。

- [ ] **Step 1: 在 PatrolModal.tsx 頂部新增 import**

```tsx
import { useExtrusionToleranceCheck } from '../../hooks/useExtrusionTolerance';
```

- [ ] **Step 2: 在 PatrolModal 函式內、`const isSaving = ...` 之前，新增 hook 呼叫與 NG 判斷函式**

```tsx
// 取得擠壓公差（有 material 就查，spec 空字串表示通用）
const { data: toleranceResult } = useExtrusionToleranceCheck(material, spec);
const tolerances = toleranceResult?.found ? (toleranceResult.tolerances ?? []) : [];

// 判斷單一儲存格是否 NG
const isCellNG = (pos: string, item: string, type: 'min' | 'max', gName: string): boolean => {
    const tol = tolerances.find((t) => t.項目 === item && t.位置 === pos);
    if (!tol) return false;
    const valStr = getDetailValue(gName, pos, item, type);
    if (valStr === '') return false;
    const val = parseFloat(valStr);
    if (type === 'min' && tol.公差下限 != null && val < tol.公差下限) return true;
    if (type === 'max' && tol.公差上限 != null && val > tol.公差上限) return true;
    return false;
};
```

- [ ] **Step 3: 修改 `renderTableRows()` 中的 `<td>` 樣式，NG 時加紅色背景**

在 `renderTableRows()` 函式中，找到 MIN 的 `<td style={{ padding: '2px' }}>` 與 MAX 的 `<td style={{ padding: '2px' }}>`，分別改為：

```tsx
// MIN 的 td
<td style={{ padding: '2px', backgroundColor: isCellNG(pos, item, 'min', gName) ? '#ffcccc' : undefined }}>
    <Form.Control
        size="sm"
        type="number"
        step="0.01"
        value={getDetailValue(gName, pos, item, 'min')}
        onChange={e => handleDetailChange(gName, pos, item, 'min', e.target.value)}
        className="patrol-input"
        style={{ backgroundColor: isCellNG(pos, item, 'min', gName) ? '#ffcccc' : undefined }}
    />
</td>

// MAX 的 td
<td style={{ padding: '2px', backgroundColor: isCellNG(pos, item, 'max', gName) ? '#ffcccc' : undefined }}>
    <Form.Control
        size="sm"
        type="number"
        step="0.01"
        value={getDetailValue(gName, pos, item, 'max')}
        onChange={e => handleDetailChange(gName, pos, item, 'max', e.target.value)}
        className="patrol-input"
        style={{ backgroundColor: isCellNG(pos, item, 'max', gName) ? '#ffcccc' : undefined }}
    />
</td>
```

注意：在 `renderTableRows()` 函式內，`gName` 即為 `第${i}組` 字串，`pos`、`item` 來自外層迴圈，可直接使用。

- [ ] **Step 4: 確認 TypeScript 編譯**

```bash
cd src_frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 5: 手動驗證**
  1. 後端建一筆擠壓公差資料（材質 6063、外徑前段公差下限 62.0、上限 63.0）
  2. 巡檢 Modal 輸入材質 6063、規格 63*3（或留空）
  3. 外徑前段 MIN 輸入 61（< 62.0）→ 該格應變紅
  4. 改為 62.2 → 該格恢復正常背景

- [ ] **Step 6: Commit**

```bash
git add src_frontend/src/components/patrol/PatrolModal.tsx
git commit -m "feat(patrol): 整合擠壓公差即時 NG 比對，NG 格以紅色底色標示"
```

---

## 完成確認清單

- [ ] `擠壓公差主檔`、`擠壓公差明細` 資料表存在
- [ ] `/api/extrusion-tolerance/*` 所有端點可正常呼叫
- [ ] 前端 `/extrusion-tolerance` 頁面可執行 新增 / 查看 / 編輯 / 刪除
- [ ] 側邊欄顯示「擠壓公差」選單項目
- [ ] 巡檢 Modal 輸入量測值時即時顯示 NG/OK 狀態
