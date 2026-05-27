# Plan C — 廠商績效模組 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增廠商績效模組，每月計算各廠商的缺陷率、CAPA 件數、客訴件數，並以評分（0-100）呈現，前端新增廠商績效頁面。

**Architecture:** 新增 `VendorPerformance` 模型；`VendorPerformanceService` 負責計算邏輯；新增 `/api/vendor-performance` 路由；前端新增 `/vendor-performance` 頁面。

**Tech Stack:** Flask 3.1、SQLAlchemy、React 19、TypeScript、Chart.js（已安裝）

**執行前提：** Plan A 已完成（api_success/api_error helper 已存在）；Plan D 已完成（ShippingData 重構完成，缺陷率由 ShippingMeasurement 計算）

---

### Task 1：VendorPerformance 模型

**Files:**
- Modify: `backend/models.py`

- [ ] **Step 1：在 models.py 結尾新增模型**

在 `ActionTask` 類別之後插入：

```python
class VendorPerformance(db.Model):
    """廠商績效 — 每月計算一次，可重複覆蓋"""
    __tablename__ = '廠商績效'
    __table_args__ = (
        db.UniqueConstraint('廠商_ID', '期間', name='uq_vendor_period'),
    )

    id               = db.Column('識別碼',        db.Integer, primary_key=True)
    vendor_id        = db.Column('廠商_ID',        db.Integer, db.ForeignKey('廠商資料.識別碼'), nullable=False)
    period           = db.Column('期間',           db.String(7),  nullable=False)  # 'YYYY-MM'
    inspection_count = db.Column('檢驗批次數',     db.Integer, default=0)
    defect_count     = db.Column('不良批次數',     db.Integer, default=0)
    defect_rate      = db.Column('缺陷率',         db.Float,   default=0.0)       # 百分比
    capa_count       = db.Column('CAPA件數',       db.Integer, default=0)
    avg_capa_days    = db.Column('平均CAPA結案天數', db.Float,  nullable=True)
    complaint_count  = db.Column('客訴件數',       db.Integer, default=0)
    score            = db.Column('績效評分',       db.Float,   default=100.0)     # 0-100
    calculated_at    = db.Column('計算時間',       db.DateTime, default=datetime.utcnow)

    vendor = db.relationship('Vendor', backref='performances')
```

- [ ] **Step 2：產生並套用遷移**

```powershell
cd C:\QC_Database\backend
$env:FLASK_APP = "app.py"
flask db migrate -m "新增廠商績效表"
flask db upgrade
```

- [ ] **Step 3：Commit**

```powershell
git add backend/models.py backend/migrations/
git commit -m "feat(models): 新增 VendorPerformance 廠商績效資料表"
```

---

### Task 2：VendorPerformanceService

**Files:**
- Create: `backend/services/vendor_performance_service.py`
- Test: `backend/tests/test_services/test_vendor_performance.py`（新建）

- [ ] **Step 1：撰寫測試**

建立 `backend/tests/test_services/test_vendor_performance.py`：

```python
import pytest
from datetime import date
from backend.models import Vendor, ShippingData, VendorPerformance
from backend.extensions import db as _db
from backend.services.vendor_performance_service import VendorPerformanceService

@pytest.fixture
def vendor(app):
    with app.app_context():
        v = Vendor(name='測試廠商A')
        _db.session.add(v)
        _db.session.commit()
        yield v
        _db.session.rollback()

def test_calculate_score_perfect(app):
    """零缺陷、零CAPA、零客訴 → 滿分100"""
    with app.app_context():
        score = VendorPerformanceService._compute_score(
            defect_rate=0, avg_capa_days=0, complaint_count=0
        )
        assert score == 100.0

def test_calculate_score_deductions(app):
    """缺陷率10% → 扣20分；客訴2件 → 扣10分 → 70分"""
    with app.app_context():
        score = VendorPerformanceService._compute_score(
            defect_rate=10.0, avg_capa_days=0, complaint_count=2
        )
        assert score == 70.0

def test_calculate_score_minimum_zero(app):
    """扣超過100分時最低為0"""
    with app.app_context():
        score = VendorPerformanceService._compute_score(
            defect_rate=50.0, avg_capa_days=100, complaint_count=10
        )
        assert score == 0.0

def test_get_or_calculate_creates_record(app, vendor):
    with app.app_context():
        result = VendorPerformanceService.get_or_calculate(vendor.id, '2026-05')
        assert result['vendor_id'] == vendor.id
        assert result['period'] == '2026-05'
        assert 'score' in result
        # 確認已存入 DB
        perf = VendorPerformance.query.filter_by(vendor_id=vendor.id, period='2026-05').first()
        assert perf is not None
```

- [ ] **Step 2：確認測試失敗**

```powershell
python -m pytest backend/tests/test_services/test_vendor_performance.py -v
```

預期：`ImportError`

- [ ] **Step 3：建立 vendor_performance_service.py**

建立 `backend/services/vendor_performance_service.py`：

```python
"""廠商績效計算服務"""
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from sqlalchemy import extract, func
from ..extensions import db
from ..models import Vendor, ShippingData, CorrectiveAction, CustomerComplaint, VendorPerformance


class VendorPerformanceService:

    @staticmethod
    def _compute_score(defect_rate: float, avg_capa_days: float, complaint_count: int) -> float:
        """
        評分公式：
          - 缺陷率每 1% 扣 2 分，最多扣 40 分
          - CAPA 平均天數每天扣 1 分，最多扣 30 分
          - 客訴每件扣 5 分，最多扣 30 分
        """
        score = 100.0
        score -= min(defect_rate * 2, 40)
        score -= min((avg_capa_days or 0) * 1, 30)
        score -= min(complaint_count * 5, 30)
        return max(round(score, 1), 0.0)

    @staticmethod
    def get_or_calculate(vendor_id: int, period: str) -> Dict[str, Any]:
        """取得或重新計算指定廠商指定月份的績效"""
        year, month = int(period[:4]), int(period[5:7])

        # 出貨巡檢統計（同月份、同廠商）
        inspections = ShippingData.query.filter(
            ShippingData.vendor_id == vendor_id,
            extract('year',  ShippingData.date) == year,
            extract('month', ShippingData.date) == month,
        ).all()

        inspection_count = len(inspections)
        defect_count     = sum(1 for i in inspections if i.is_ng)
        defect_rate      = round(defect_count / inspection_count * 100, 2) if inspection_count else 0.0

        # CAPA 統計（以 source_type='ncmr' 且 NCMR 關聯廠商）— 簡化：以建立月份計
        capas = CorrectiveAction.query.filter(
            extract('year',  CorrectiveAction.created_at) == year,
            extract('month', CorrectiveAction.created_at) == month,
        ).all()
        # 過濾來源為此廠商的 CAPA（透過 NCMR 的 vendor 欄位比對）
        vendor = Vendor.query.get(vendor_id)
        vendor_name = vendor.name if vendor else ''
        from ..models import NCMR
        vendor_capas = []
        for ca in capas:
            if ca.source_type == 'ncmr' and ca.source_id:
                ncmr = NCMR.query.get(ca.source_id)
                if ncmr and ncmr.vendor == vendor_name:
                    vendor_capas.append(ca)

        capa_count = len(vendor_capas)
        closed_capas = [ca for ca in vendor_capas if ca.status == '已結案' and ca.d8_close_date and ca.created_at]
        avg_capa_days = None
        if closed_capas:
            days_list = [(ca.d8_close_date - ca.created_at.date()).days for ca in closed_capas]
            avg_capa_days = round(sum(days_list) / len(days_list), 1)

        # 客訴統計
        complaint_count = CustomerComplaint.query.filter(
            CustomerComplaint.customer == vendor_name,
            extract('year',  CustomerComplaint.complaint_date) == year,
            extract('month', CustomerComplaint.complaint_date) == month,
        ).count()

        score = VendorPerformanceService._compute_score(defect_rate, avg_capa_days or 0, complaint_count)

        # 寫入或更新 DB
        perf = VendorPerformance.query.filter_by(vendor_id=vendor_id, period=period).first()
        if perf is None:
            perf = VendorPerformance(vendor_id=vendor_id, period=period)
            db.session.add(perf)

        perf.inspection_count = inspection_count
        perf.defect_count     = defect_count
        perf.defect_rate      = defect_rate
        perf.capa_count       = capa_count
        perf.avg_capa_days    = avg_capa_days
        perf.complaint_count  = complaint_count
        perf.score            = score
        perf.calculated_at    = datetime.utcnow()
        db.session.commit()

        return VendorPerformanceService._to_dict(perf)

    @staticmethod
    def list_by_period(period: str) -> List[Dict[str, Any]]:
        """取得指定月份所有廠商績效（自動補算未計算廠商）"""
        vendors = Vendor.query.all()
        results = []
        for v in vendors:
            results.append(VendorPerformanceService.get_or_calculate(v.id, period))
        return sorted(results, key=lambda x: x['score'])  # 低分排前

    @staticmethod
    def history(vendor_id: int, months: int = 6) -> List[Dict[str, Any]]:
        """取得指定廠商最近 N 個月績效歷史"""
        records = VendorPerformance.query\
            .filter_by(vendor_id=vendor_id)\
            .order_by(VendorPerformance.period.desc())\
            .limit(months).all()
        return [VendorPerformanceService._to_dict(r) for r in records]

    @staticmethod
    def _to_dict(perf: VendorPerformance) -> Dict[str, Any]:
        return {
            'id':               perf.id,
            'vendor_id':        perf.vendor_id,
            'vendor_name':      perf.vendor.name if perf.vendor else None,
            'period':           perf.period,
            'inspection_count': perf.inspection_count,
            'defect_count':     perf.defect_count,
            'defect_rate':      perf.defect_rate,
            'capa_count':       perf.capa_count,
            'avg_capa_days':    perf.avg_capa_days,
            'complaint_count':  perf.complaint_count,
            'score':            perf.score,
            'calculated_at':    perf.calculated_at.isoformat() if perf.calculated_at else None,
        }
```

- [ ] **Step 4：確認測試通過**

```powershell
python -m pytest backend/tests/test_services/test_vendor_performance.py -v
```

- [ ] **Step 5：Commit**

```powershell
git add backend/services/vendor_performance_service.py backend/tests/test_services/test_vendor_performance.py
git commit -m "feat(vendor-performance): 新增廠商績效計算服務"
```

---

### Task 3：路由

**Files:**
- Create: `backend/routes/vendor_performance.py`
- Modify: `backend/app.py`（註冊 blueprint）

- [ ] **Step 1：建立路由**

建立 `backend/routes/vendor_performance.py`：

```python
"""廠商績效路由"""
from flask import Blueprint, jsonify, request
from ..services.vendor_performance_service import VendorPerformanceService
from ..utils import auth_required, api_success, api_error
from datetime import date

vendor_perf_bp = Blueprint('vendor_performance', __name__)


@vendor_perf_bp.route('/api/vendor-performance', methods=['GET'])
@auth_required
def list_vendor_performance(current_user):
    """GET /api/vendor-performance?period=2026-05"""
    period = request.args.get('period', date.today().strftime('%Y-%m'))
    try:
        data = VendorPerformanceService.list_by_period(period)
        return api_success(data)
    except Exception as e:
        return api_error(str(e), 500)


@vendor_perf_bp.route('/api/vendor-performance/<int:vendor_id>/history', methods=['GET'])
@auth_required
def vendor_history(current_user, vendor_id: int):
    """GET /api/vendor-performance/<vendor_id>/history?months=6"""
    months = int(request.args.get('months', 6))
    try:
        data = VendorPerformanceService.history(vendor_id, months)
        return api_success(data)
    except Exception as e:
        return api_error(str(e), 500)
```

- [ ] **Step 2：在 app.py 註冊 blueprint**

找到 blueprint 註冊區段，加入：

```python
from .routes.vendor_performance import vendor_perf_bp
app.register_blueprint(vendor_perf_bp)
```

- [ ] **Step 3：Commit**

```powershell
git add backend/routes/vendor_performance.py backend/app.py
git commit -m "feat(routes): 新增廠商績效 API 路由"
```

---

### Task 4：前端類型與 Hook

**Files:**
- Modify: `src_frontend/src/types/index.ts`
- Create: `src_frontend/src/hooks/useVendorPerformance.ts`

- [ ] **Step 1：新增類型**

在 `types/index.ts` 尾端新增：

```typescript
export interface VendorPerformance {
    id: number;
    vendor_id: number;
    vendor_name?: string;
    period: string;
    inspection_count: number;
    defect_count: number;
    defect_rate: number;
    capa_count: number;
    avg_capa_days?: number | null;
    complaint_count: number;
    score: number;
    calculated_at?: string;
}
```

- [ ] **Step 2：建立 hook**

建立 `src_frontend/src/hooks/useVendorPerformance.ts`：

```typescript
import { useQuery } from '@tanstack/react-query';
import api from '../services/api';
import type { VendorPerformance } from '../types';

export const useVendorPerformanceList = (period: string) =>
    useQuery({
        queryKey: ['vendorPerformance', period],
        queryFn: async () => {
            const res = await api.get<{ success: boolean; data: VendorPerformance[] }>(
                '/vendor-performance', { params: { period } }
            );
            return res.data.data;
        },
    });

export const useVendorPerformanceHistory = (vendorId: number, months = 6) =>
    useQuery({
        queryKey: ['vendorPerformanceHistory', vendorId, months],
        queryFn: async () => {
            const res = await api.get<{ success: boolean; data: VendorPerformance[] }>(
                `/vendor-performance/${vendorId}/history`, { params: { months } }
            );
            return res.data.data;
        },
        enabled: vendorId > 0,
    });
```

- [ ] **Step 3：Commit**

```powershell
git add src_frontend/src/types/index.ts src_frontend/src/hooks/useVendorPerformance.ts
git commit -m "feat(types): 新增 VendorPerformance 類型與 hook"
```

---

### Task 5：前端廠商績效頁面

**Files:**
- Create: `src_frontend/src/pages/vendor/VendorPerformancePage.tsx`
- Modify: `src_frontend/src/App.tsx`（新增路由）
- Modify: `src_frontend/src/components/layout/Sidebar.tsx`（新增選單）

- [ ] **Step 1：建立頁面**

建立 `src_frontend/src/pages/vendor/VendorPerformancePage.tsx`：

```tsx
import { useState } from 'react';
import { Container, Card, Table, Badge, Form, Row, Col, Spinner } from 'react-bootstrap';
import { Line } from 'react-chartjs-2';
import { useVendorPerformanceList, useVendorPerformanceHistory } from '../../hooks/useVendorPerformance';

const scoreVariant = (score: number) =>
    score >= 80 ? 'success' : score >= 60 ? 'warning' : 'danger';

const VendorPerformancePage = () => {
    const today = new Date();
    const [period, setPeriod] = useState(
        `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
    );
    const [selectedVendorId, setSelectedVendorId] = useState<number | null>(null);

    const { data: list = [], isLoading } = useVendorPerformanceList(period);
    const { data: history = [] } = useVendorPerformanceHistory(selectedVendorId ?? 0);

    return (
        <Container fluid className="py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="bi bi-bar-chart-steps me-2 text-primary" />
                    廠商績效評比
                </h4>
                <Form.Control
                    type="month"
                    value={period}
                    onChange={e => setPeriod(e.target.value)}
                    style={{ width: '160px' }}
                />
            </div>

            <Card className="shadow-sm mb-4">
                <Card.Body className="p-0">
                    <Table hover className="mb-0">
                        <thead className="table-light">
                            <tr>
                                <th>廠商</th>
                                <th>評分</th>
                                <th>檢驗批次</th>
                                <th>不良批次</th>
                                <th>缺陷率</th>
                                <th>CAPA件數</th>
                                <th>客訴件數</th>
                                <th>平均CAPA天數</th>
                            </tr>
                        </thead>
                        <tbody>
                            {isLoading ? (
                                <tr><td colSpan={8} className="text-center py-4">
                                    <Spinner animation="border" size="sm" className="me-2" />載入中…
                                </td></tr>
                            ) : list.map(row => (
                                <tr
                                    key={row.vendor_id}
                                    style={{ cursor: 'pointer' }}
                                    className={selectedVendorId === row.vendor_id ? 'table-active' : ''}
                                    onClick={() => setSelectedVendorId(
                                        selectedVendorId === row.vendor_id ? null : row.vendor_id
                                    )}
                                >
                                    <td className="fw-semibold">{row.vendor_name}</td>
                                    <td>
                                        <Badge bg={scoreVariant(row.score)} style={{ fontSize: '0.9rem' }}>
                                            {row.score}
                                        </Badge>
                                    </td>
                                    <td>{row.inspection_count}</td>
                                    <td>{row.defect_count}</td>
                                    <td className={row.defect_rate > 10 ? 'text-danger fw-semibold' : ''}>
                                        {row.defect_rate.toFixed(1)}%
                                    </td>
                                    <td>{row.capa_count}</td>
                                    <td>{row.complaint_count}</td>
                                    <td>{row.avg_capa_days != null ? `${row.avg_capa_days} 天` : '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </Table>
                </Card.Body>
            </Card>

            {/* 趨勢圖 */}
            {selectedVendorId && history.length > 0 && (
                <Card className="shadow-sm">
                    <Card.Header className="fw-semibold">
                        {list.find(r => r.vendor_id === selectedVendorId)?.vendor_name} — 近期評分走勢
                    </Card.Header>
                    <Card.Body>
                        <Row>
                            <Col md={8}>
                                <Line
                                    data={{
                                        labels: [...history].reverse().map(h => h.period),
                                        datasets: [{
                                            label: '績效評分',
                                            data: [...history].reverse().map(h => h.score),
                                            borderColor: '#0d6efd',
                                            backgroundColor: 'rgba(13,110,253,0.1)',
                                            tension: 0.3,
                                            fill: true,
                                        }],
                                    }}
                                    options={{
                                        responsive: true,
                                        scales: { y: { min: 0, max: 100 } },
                                        plugins: { legend: { display: false } },
                                    }}
                                />
                            </Col>
                            <Col md={4}>
                                <Table size="sm">
                                    <thead><tr><th>期間</th><th>評分</th><th>缺陷率</th></tr></thead>
                                    <tbody>
                                        {history.map(h => (
                                            <tr key={h.period}>
                                                <td>{h.period}</td>
                                                <td><Badge bg={scoreVariant(h.score)}>{h.score}</Badge></td>
                                                <td>{h.defect_rate.toFixed(1)}%</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </Table>
                            </Col>
                        </Row>
                    </Card.Body>
                </Card>
            )}
        </Container>
    );
};

export default VendorPerformancePage;
```

- [ ] **Step 2：在 App.tsx 新增路由**

找到路由定義區，新增：

```tsx
import VendorPerformancePage from './pages/vendor/VendorPerformancePage';

// 在 <Routes> 內加入：
<Route path="/vendor-performance" element={<ProtectedRoute><VendorPerformancePage /></ProtectedRoute>} />
```

- [ ] **Step 3：在 Sidebar 新增選單項目**

找到側邊欄定義（通常在 `Sidebar.tsx` 或 `Layout.tsx`），加入廠商績效連結：

```tsx
<Nav.Link href="/vendor-performance">
    <i className="bi bi-bar-chart-steps me-2" />廠商績效
</Nav.Link>
```

- [ ] **Step 4：TypeScript build 驗證**

```powershell
cd C:\QC_Database\src_frontend
npm run build
```

預期：無錯誤

- [ ] **Step 5：Commit 並推送**

```powershell
git add src_frontend/src/pages/vendor/ src_frontend/src/App.tsx src_frontend/src/components/
git commit -m "feat(vendor-performance): 新增廠商績效頁面、路由、側邊欄連結"
git push origin master
```
