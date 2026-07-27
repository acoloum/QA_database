import { useState } from 'react';
import { Modal } from 'react-bootstrap';

import EquipmentDetailDrawer from '../../components/msa/EquipmentDetailDrawer';
import EquipmentStatusBadge from '../../components/msa/EquipmentStatusBadge';
import { useAuth } from '../../context/useAuth';
import {
  useCreateMsaEquipment,
  useMsaEquipment,
} from '../../hooks/useMsaEquipment';
import type {
  CalibrationStatus,
  EquipmentListParams,
  EquipmentStatus,
  MeasurementEquipment,
} from '../../types/msa';
import './msaEquipment.css';

const EQUIPMENT_STATUS_OPTIONS: Array<{ value: EquipmentStatus; label: string }> = [
  { value: 'active', label: '使用中' },
  { value: 'pending_review', label: '待確認' },
  { value: 'maintenance', label: '維修' },
  { value: 'inactive', label: '停用' },
  { value: 'scrapped', label: '報廢' },
];

const CALIBRATION_STATUS_OPTIONS: Array<{ value: CalibrationStatus; label: string }> = [
  { value: 'failed', label: '失敗' },
  { value: 'expired', label: '逾期' },
  { value: 'missing', label: '缺少證據' },
  { value: 'due_soon', label: '30 日內到期' },
  { value: 'valid', label: '有效' },
  { value: 'exempt', label: '免校' },
];

const errorText = (error: unknown) => (
  error instanceof Error ? error.message : '設備資料未儲存，請檢查輸入內容。'
);

function EquipmentCard({
  equipment,
  onOpen,
}: {
  equipment: MeasurementEquipment;
  onOpen: () => void;
}) {
  return (
    <li className={`msa-equipment-card risk-${equipment.calibration_status}`}>
      <div className="msa-equipment-card__rail" aria-hidden="true" />
      <div className="msa-equipment-card__body">
        <header>
          <div>
            <span className="msa-mono">{equipment.equipment_no}</span>
            <strong>{equipment.name}</strong>
          </div>
          <EquipmentStatusBadge status={equipment.calibration_status} />
        </header>
        <p>
          {equipment.resolution ?? '未填解析度'} {equipment.unit || ''}
          {' · '}{equipment.location || '未填位置'}
        </p>
        {equipment.calibration_block_reason && (
          <p className="msa-block-reason">{equipment.calibration_block_reason}</p>
        )}
        <footer>
          <EquipmentStatusBadge status={equipment.status} />
          <button
            type="button"
            className="msa-button msa-button--quiet"
            aria-label={`查看 ${equipment.equipment_no}`}
            onClick={onOpen}
          >
            查看證據
          </button>
        </footer>
      </div>
    </li>
  );
}

export default function MeasurementEquipmentPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('msa.manage');
  const [params, setParams] = useState<EquipmentListParams>({
    page: 1,
    page_size: 25,
    sort: 'risk',
    order: 'asc',
  });
  const query = useMsaEquipment(params);
  const createEquipment = useCreateMsaEquipment();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const items: MeasurementEquipment[] = query.data?.items ?? [];

  const count = (predicate: (item: MeasurementEquipment) => boolean) => (
    items.filter(predicate).length
  );
  const risks = [
    {
      label: '校驗失敗',
      count: count((item) => item.calibration_status === 'failed'),
      onClick: () => setParams((current) => ({
        ...current, page: 1, calibration_status: 'failed',
      })),
    },
    {
      label: '校驗逾期',
      count: count((item) => item.calibration_status === 'expired'),
      onClick: () => setParams((current) => ({
        ...current, page: 1, calibration_status: 'expired',
      })),
    },
    {
      label: '待確認',
      count: count((item) => item.status === 'pending_review'),
      onClick: () => setParams((current) => ({
        ...current, page: 1, status: 'pending_review',
      })),
    },
    {
      label: '維修',
      count: count((item) => item.status === 'maintenance'),
      onClick: () => setParams((current) => ({
        ...current, page: 1, status: 'maintenance',
      })),
    },
    {
      label: '30 日內到期',
      count: count((item) => item.calibration_status === 'due_soon'),
      onClick: () => setParams((current) => ({
        ...current, page: 1, calibration_status: 'due_soon',
      })),
    },
  ];

  return (
    <main className="msa-page" aria-labelledby="equipment-title">
      <header className="msa-page__header">
        <div>
          <p className="msa-eyebrow">MSA / 量測資源治理</p>
          <h1 id="equipment-title">設備清單</h1>
          <p>先辨識會阻擋正式研究的設備，再沿證據軌完成處置。</p>
        </div>
        {canManage && (
          <div className="msa-page__actions">
            <a className="msa-button msa-button--outline" href="/msa/imports">匯入設備</a>
            <button
              type="button"
              className="msa-button msa-button--primary"
              onClick={() => setShowCreate(true)}
            >
              新增設備
            </button>
          </div>
        )}
      </header>

      <nav className="msa-risk-queue" aria-label="設備風險佇列">
        <span className="msa-risk-queue__label">本頁風險佇列</span>
        {risks.map((risk) => (
          <button type="button" key={risk.label} onClick={risk.onClick}>
            <span>{risk.label}</span>
            <strong className="msa-mono">{risk.count}</strong>
          </button>
        ))}
      </nav>

      <form
        className="msa-filters"
        aria-label="設備篩選"
        onSubmit={(event) => event.preventDefault()}
      >
        <label>
          搜尋
          <input
            type="search"
            placeholder="設備編號、名稱或序號"
            value={params.q ?? ''}
            onChange={(event) => setParams((current) => ({
              ...current,
              page: 1,
              q: event.target.value || undefined,
            }))}
          />
        </label>
        <label>
          設備狀態
          <select
            value={params.status ?? ''}
            onChange={(event) => setParams((current) => ({
              ...current,
              page: 1,
              status: (event.target.value || undefined) as EquipmentStatus | undefined,
            }))}
          >
            <option value="">全部</option>
            {EQUIPMENT_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          校驗狀態
          <select
            value={params.calibration_status ?? ''}
            onChange={(event) => setParams((current) => ({
              ...current,
              page: 1,
              calibration_status: (event.target.value || undefined) as CalibrationStatus | undefined,
            }))}
          >
            <option value="">全部</option>
            {CALIBRATION_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="msa-button msa-button--quiet"
          onClick={() => setParams({
            page: 1,
            page_size: 25,
            sort: 'risk',
            order: 'asc',
          })}
        >
          清除篩選
        </button>
      </form>

      {query.isLoading && <div className="msa-state" role="status">正在讀取設備證據</div>}
      {query.isError && (
        <div className="msa-state msa-state--error" role="alert">
          <p>無法載入設備清單</p>
          <button type="button" onClick={() => void query.refetch()}>重試</button>
        </div>
      )}
      {!query.isLoading && !query.isError && items.length === 0 && (
        <div className="msa-state">
          <strong>尚無符合條件的量測設備</strong>
          <p>調整篩選條件，或由具 msa.manage 權限的人員建立設備。</p>
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="msa-equipment-table-wrap">
            <table className="msa-equipment-table" aria-label="量測設備與校驗風險">
              <caption>量測設備與校驗風險</caption>
              <thead>
                <tr>
                  <th scope="col">證據軌</th>
                  <th scope="col">設備編號／名稱</th>
                  <th scope="col">量測能力</th>
                  <th scope="col">校驗證據</th>
                  <th scope="col">設備狀態</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((equipment) => (
                  <tr key={equipment.id} className={`risk-${equipment.calibration_status}`}>
                    <td className="msa-evidence-rail">
                      <span aria-hidden="true" />
                      <span className="visually-hidden">
                        {equipment.calibration_status}
                      </span>
                    </td>
                    <td>
                      <strong className="msa-mono">{equipment.equipment_no}</strong>
                      <span>{equipment.name}</span>
                      <small>{equipment.serial_no || '未填序號'}</small>
                    </td>
                    <td className="msa-mono">
                      {equipment.resolution ?? '—'} {equipment.unit || ''}
                      <small>{equipment.equipment_type || '未分類'}</small>
                    </td>
                    <td>
                      <EquipmentStatusBadge status={equipment.calibration_status} />
                      <time className="msa-mono">
                        {equipment.next_calibration_date || '無下次校驗日'}
                      </time>
                      {equipment.calibration_block_reason && (
                        <small className="msa-block-reason">
                          {equipment.calibration_block_reason}
                        </small>
                      )}
                    </td>
                    <td><EquipmentStatusBadge status={equipment.status} /></td>
                    <td>
                      <button
                        type="button"
                        className="msa-button msa-button--quiet"
                        aria-label={`查看 ${equipment.equipment_no}`}
                        onClick={() => setSelectedId(equipment.id)}
                      >
                        查看
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="msa-equipment-cards" aria-label="行動版設備清單">
            {items.map((equipment) => (
              <EquipmentCard
                key={equipment.id}
                equipment={equipment}
                onOpen={() => setSelectedId(equipment.id)}
              />
            ))}
          </ul>
          <nav className="msa-pagination" aria-label="設備清單分頁">
            <button
              type="button"
              disabled={params.page <= 1}
              onClick={() => setParams((current) => ({
                ...current, page: Math.max(1, current.page - 1),
              }))}
            >
              上一頁
            </button>
            <span className="msa-mono">
              第 {query.data?.page ?? params.page} 頁 · 共 {query.data?.total ?? 0} 筆
            </span>
            <button
              type="button"
              disabled={(params.page * params.page_size) >= (query.data?.total ?? 0)}
              onClick={() => setParams((current) => ({
                ...current, page: current.page + 1,
              }))}
            >
              下一頁
            </button>
          </nav>
        </>
      )}

      <EquipmentDetailDrawer
        equipmentId={selectedId}
        show={selectedId != null}
        onHide={() => setSelectedId(null)}
      />

      <Modal
        show={showCreate}
        onHide={() => setShowCreate(false)}
        restoreFocus
        aria-labelledby="create-equipment-title"
        dialogClassName="msa-create-dialog"
      >
        <Modal.Header closeButton>
          <Modal.Title id="create-equipment-title">新增量測設備</Modal.Title>
        </Modal.Header>
        <Modal.Body>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                setCreateError(null);
                void createEquipment.mutateAsync({
                  equipment_no: String(data.get('equipment_no')),
                  name: String(data.get('name')),
                  equipment_type: String(data.get('equipment_type') || '') || null,
                  serial_no: String(data.get('serial_no') || '') || null,
                  resolution: String(data.get('resolution') || '') || null,
                  unit: String(data.get('unit') || '') || null,
                  status: 'pending_review',
                }).then(() => setShowCreate(false)).catch((error: unknown) => {
                  setCreateError(errorText(error));
                });
              }}
            >
              <label>設備編號<input name="equipment_no" required autoFocus /></label>
              <label>設備名稱<input name="name" required /></label>
              <label>設備類型<input name="equipment_type" /></label>
              <label>序號<input name="serial_no" /></label>
              <label>解析度<input name="resolution" inputMode="decimal" /></label>
              <label>單位<input name="unit" /></label>
              {createError && <p role="alert">{createError}</p>}
              <button
                className="msa-button msa-button--primary"
                type="submit"
                disabled={createEquipment.isPending}
              >
                建立待確認設備
              </button>
            </form>
        </Modal.Body>
      </Modal>
    </main>
  );
}
