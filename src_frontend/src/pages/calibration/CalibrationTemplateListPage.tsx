import { useState } from 'react';
import { Modal } from 'react-bootstrap';
import { Link } from 'react-router-dom';

import { useAuth } from '../../context/useAuth';
import {
  useCalibrationTemplates,
  useCreateCalibrationTemplate,
} from '../../hooks/useCalibrationTemplates';
import { ApiError } from '../../services/apiError';
import type {
  CalibrationTemplate,
  CalibrationTemplateListParams,
} from '../../types/calibration';
import './calibration.css';

const templateStatus = (template: CalibrationTemplate) => {
  if (template.status === 'inactive') return '已停用';
  const approved = template.current_approved_version;
  return approved ? `已核准 · V${approved.version_no}` : '尚無核准版本';
};

interface CreateError {
  message: string;
  field: string | null;
}

const createErrorDetails = (error: unknown): CreateError => {
  const message = error instanceof Error
    ? error.message
    : '模板未建立，請檢查輸入內容。';
  if (!(error instanceof ApiError)) return { message, field: null };
  const field = typeof error.details?.field === 'string'
    ? error.details.field
    : error.field ?? null;
  return { message, field };
};

export default function CalibrationTemplateListPage() {
  const { hasPermission } = useAuth();
  const canManage = hasPermission('calibration.manage');
  const [params, setParams] = useState<CalibrationTemplateListParams>({
    page: 1,
    page_size: 25,
  });
  const [searchText, setSearchText] = useState('');
  const templates = useCalibrationTemplates({
    ...params,
    search: searchText.trim() || undefined,
  });
  const createTemplate = useCreateCalibrationTemplate();
  const [showCreate, setShowCreate] = useState(false);
  const [createError, setCreateError] = useState<CreateError | null>(null);
  const [draft, setDraft] = useState({
    template_code: '',
    name: '',
    equipment_type: '',
    description: '',
  });

  return (
    <main className="cal-page" aria-labelledby="cal-template-list-title">
      <header className="cal-page-header">
        <div>
          <p className="cal-kicker">量測治理 / 程序與判定規則</p>
          <h1 id="cal-template-list-title">校正模板</h1>
          <p>模板定義校正點、重複次數與允差；核准版本才可建立正式校正。</p>
        </div>
        {canManage && (
          <button
            className="cal-button cal-button--primary"
            type="button"
            onClick={() => {
              setCreateError(null);
              setShowCreate(true);
            }}
          >
            建立模板
          </button>
        )}
      </header>

      <form className="cal-filter-bar" onSubmit={(event) => event.preventDefault()}>
        <label>
          搜尋模板
          <input
            type="search"
            value={searchText}
            placeholder="模板代碼或名稱"
            onChange={(event) => {
              setSearchText(event.target.value);
              setParams((current) => ({ ...current, page: 1 }));
            }}
          />
        </label>
        <label>
          模板狀態
          <select
            value={params.status ?? ''}
            onChange={(event) => setParams((current) => ({
              ...current,
              page: 1,
              status: (
                event.target.value || undefined
              ) as CalibrationTemplateListParams['status'],
            }))}
          >
            <option value="">全部</option>
            <option value="active">啟用</option>
            <option value="inactive">停用</option>
          </select>
        </label>
        <label>
          適用設備類型
          <input
            value={params.equipment_type ?? ''}
            onChange={(event) => setParams((current) => ({
              ...current,
              page: 1,
              equipment_type: event.target.value || undefined,
            }))}
          />
        </label>
      </form>

      {templates.isLoading && <p className="cal-state" role="status">正在讀取模板…</p>}
      {templates.isError && (
        <div className="cal-state cal-state--error" role="alert">
          <p>模板清單載入失敗。</p>
          <button type="button" onClick={() => void templates.refetch()}>重新載入</button>
        </div>
      )}
      {!templates.isLoading && !templates.isError && (
        <>
          <section className="cal-template-grid" aria-label="校正模板清單">
            {(templates.data?.items ?? []).map((template) => (
              <article className="cal-template-card" key={template.id}>
                <div className="cal-template-card__index" aria-hidden="true">
                  {template.template_code}
                </div>
                <header>
                  <div>
                    <code>{template.template_code}</code>
                    <h2>{template.name}</h2>
                  </div>
                  <span data-status={template.status}>
                    {template.status === 'active' ? '啟用' : '停用'}
                  </span>
                </header>
                <dl>
                  <div><dt>適用設備</dt><dd>{template.equipment_type}</dd></div>
                  <div>
                    <dt>目前版本</dt>
                    <dd>
                      {templateStatus(template)}
                      {template.current_approved_version?.approved_at && (
                        <small className="cal-template-card__evidence">
                          核准時間：
                          {new Date(
                            template.current_approved_version.approved_at,
                          ).toLocaleString('zh-TW')}
                        </small>
                      )}
                    </dd>
                  </div>
                </dl>
                <p>{template.description || '尚未填寫模板說明。'}</p>
                <Link
                  className="cal-button cal-button--secondary"
                  to={`/calibration/templates/${template.id}`}
                  aria-label={`管理${template.name}`}
                >
                  檢視版本與規則
                </Link>
              </article>
            ))}
          </section>
          {(templates.data?.items.length ?? 0) === 0 && (
            <p className="cal-state">沒有符合條件的校正模板。</p>
          )}
          <nav className="cal-pagination" aria-label="模板分頁">
            <button
              type="button"
              disabled={params.page <= 1}
              onClick={() => setParams((current) => ({
                ...current, page: current.page - 1,
              }))}
            >
              上一頁
            </button>
            <span>第 {params.page} 頁 · 共 {templates.data?.total ?? 0} 筆</span>
            <button
              type="button"
              disabled={
                params.page * params.page_size >= (templates.data?.total ?? 0)
              }
              onClick={() => setParams((current) => ({
                ...current, page: current.page + 1,
              }))}
            >
              下一頁
            </button>
          </nav>
        </>
      )}

      <Modal
        show={showCreate}
        onHide={() => setShowCreate(false)}
        centered
        className="cal-modal"
        aria-labelledby="create-template-title"
      >
        <Modal.Header closeButton>
          <div>
            <p className="cal-kicker">建立穩定模板身分</p>
            <Modal.Title id="create-template-title">新校正模板</Modal.Title>
          </div>
        </Modal.Header>
        <Modal.Body>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                setCreateError(null);
                const payload = {
                  template_code: draft.template_code.trim(),
                  name: draft.name.trim(),
                  equipment_type: draft.equipment_type.trim(),
                  description: draft.description.trim() || null,
                };
                if (
                  !payload.template_code || !payload.name
                  || !payload.equipment_type
                ) {
                  setCreateError({
                    message: '模板代碼、名稱與適用設備類型為必填',
                    field: null,
                  });
                  return;
                }
                void createTemplate.mutateAsync(payload)
                  .then(() => setShowCreate(false))
                  .catch((error: unknown) => {
                    const details = createErrorDetails(error);
                    setCreateError(details);
                    if (details.field) {
                      const field = details.field;
                      requestAnimationFrame(() => {
                        document.getElementById(
                          `create-template-${field.replaceAll('_', '-')}`,
                        )?.focus();
                      });
                    }
                  });
              }}
            >
              <label>
                模板代碼
                <input
                  id="create-template-template-code"
                  autoFocus
                  value={draft.template_code}
                  aria-invalid={createError?.field === 'template_code' || undefined}
                  aria-describedby={createError ? 'create-template-error' : undefined}
                  onChange={(event) => setDraft((current) => ({
                    ...current, template_code: event.target.value,
                  }))}
                />
              </label>
              <label>
                模板名稱
                <input
                  id="create-template-name"
                  value={draft.name}
                  aria-invalid={createError?.field === 'name' || undefined}
                  aria-describedby={createError ? 'create-template-error' : undefined}
                  onChange={(event) => setDraft((current) => ({
                    ...current, name: event.target.value,
                  }))}
                />
              </label>
              <label>
                適用設備類型
                <input
                  id="create-template-equipment-type"
                  value={draft.equipment_type}
                  aria-invalid={createError?.field === 'equipment_type' || undefined}
                  aria-describedby={createError ? 'create-template-error' : undefined}
                  onChange={(event) => setDraft((current) => ({
                    ...current, equipment_type: event.target.value,
                  }))}
                />
              </label>
              <label>
                模板說明
                <textarea
                  id="create-template-description"
                  rows={3}
                  value={draft.description}
                  aria-invalid={createError?.field === 'description' || undefined}
                  aria-describedby={createError ? 'create-template-error' : undefined}
                  onChange={(event) => setDraft((current) => ({
                    ...current, description: event.target.value,
                  }))}
                />
              </label>
              {createError && (
                <div
                  className="cal-inline-error"
                  id="create-template-error"
                  role="alert"
                >
                  <p>{createError.message}</p>
                  {createError.field && <p>欄位：{createError.field}</p>}
                </div>
              )}
              <div className="cal-dialog__actions">
                <button type="button" onClick={() => setShowCreate(false)}>取消</button>
                <button
                  className="cal-button cal-button--primary"
                  type="submit"
                  disabled={createTemplate.isPending}
                >
                  確認建立模板
                </button>
              </div>
            </form>
        </Modal.Body>
      </Modal>
    </main>
  );
}
