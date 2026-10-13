import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Col, Form, Modal, Row, Table } from 'react-bootstrap';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import { apiErrorMessage, apiErrorNeedsToast } from '../../services/apiError';
import type { MechanicalSuspectMeasurement, MechSuspectItem } from '../../types';
import PermissionAction from '../PermissionAction';
import { mechanicalKeys } from '../../hooks/queryKeys';

const SUSPECT_ITEMS: MechSuspectItem[] = ['硬度', '抗拉強度', '降伏強度', '伸長率'];

interface Props {
  /** 開啟該爐次的編輯表單，供更正誤植數值 */
  onEdit: (testId: number) => void;
}

/** 待確認的排除／恢復動作；excluded 為送出後的目標狀態 */
interface PendingExclusion {
  row: MechanicalSuspectMeasurement;
  excluded: boolean;
}

/**
 * 機械性質疑似異常值清單。
 *
 * 誤植（多打位數、小數點錯位）應開啟表單更正數值；確認為無效數據才標示排除統計，
 * 排除後量測值保留追溯，只是不納入 SPC 計算（AIAG-VDA SPC §6.6）。
 */
export default function MechanicalSuspectPanel({ onEdit }: Props) {
  const queryClient = useQueryClient();
  const [item, setItem] = useState('');
  const [material, setMaterial] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [includeExcluded, setIncludeExcluded] = useState(false);
  const [page, setPage] = useState(1);
  const [pending, setPending] = useState<PendingExclusion | null>(null);
  const [reason, setReason] = useState('');

  const changeFilter = <T,>(setter: (value: T) => void, value: T) => {
    setPage(1);
    setter(value);
  };

  const params = {
    item,
    material,
    date_from: dateFrom,
    date_to: dateTo,
    include_excluded: includeExcluded,
    page,
    page_size: 20,
  };
  const { data, isLoading, isError } = useQuery({
    queryKey: mechanicalKeys.suspects(params),
    queryFn: () => mechanicalApi.suspects(params),
  });

  const exclusionMutation = useMutation({
    mutationFn: ({ row, excluded }: PendingExclusion) =>
      mechanicalApi.setExclusion(row.識別碼, excluded, reason.trim()),
    onSuccess: (_result, { row, excluded }) => {
      toast.success(excluded ? '已排除統計' : '已恢復統計');
      setPending(null);
      setReason('');
      queryClient.invalidateQueries({ queryKey: mechanicalKeys.root });
      queryClient.invalidateQueries({ queryKey: mechanicalKeys.detail(row.檢驗ID) });
      queryClient.invalidateQueries({ queryKey: mechanicalKeys.statsRoot });
    },
    onError: (error) => {
      const message = apiErrorMessage(error, '更新排除狀態失敗，請稍後再試');
      if (apiErrorNeedsToast(error)) toast.error(message);
    },
  });

  const openExclusion = (row: MechanicalSuspectMeasurement, excluded: boolean) => {
    setReason('');
    setPending({ row, excluded });
  };

  const rows = data?.data ?? [];
  return (
    <>
      <Card className="mb-3">
        <Card.Body>
          <p className="text-muted small mb-2">
            依「量測項目＋材質」分組，列出偏離同組中間 50% 資料超過 {data?.rule.iqr_fence ?? 5} 倍
            四分位距、或為 0／負值的量測值（同組少於 {data?.rule.min_group_size ?? 10} 筆時只檢查 0／負值）。
            誤植請以「編輯」更正；確認為無效數據才排除統計。
          </p>
          <Row className="g-2 align-items-end">
            <Col md={2}>
              <Form.Label htmlFor="mechanical-suspect-item">量測項目</Form.Label>
              <Form.Select
                id="mechanical-suspect-item"
                size="sm"
                value={item}
                onChange={(event) => changeFilter(setItem, event.target.value)}
              >
                <option value="">全部</option>
                {SUSPECT_ITEMS.map((value) => <option key={value} value={value}>{value}</option>)}
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-suspect-material">材質</Form.Label>
              <Form.Control
                id="mechanical-suspect-material"
                size="sm"
                placeholder="材質"
                value={material}
                onChange={(event) => changeFilter(setMaterial, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-suspect-date-from">起始日期</Form.Label>
              <Form.Control
                id="mechanical-suspect-date-from"
                type="date"
                size="sm"
                value={dateFrom}
                onChange={(event) => changeFilter(setDateFrom, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Label htmlFor="mechanical-suspect-date-to">結束日期</Form.Label>
              <Form.Control
                id="mechanical-suspect-date-to"
                type="date"
                size="sm"
                value={dateTo}
                onChange={(event) => changeFilter(setDateTo, event.target.value)}
              />
            </Col>
            <Col md={2}>
              <Form.Check
                id="mechanical-suspect-include-excluded"
                type="switch"
                label="含已排除"
                checked={includeExcluded}
                onChange={(event) => changeFilter(setIncludeExcluded, event.target.checked)}
              />
            </Col>
          </Row>
        </Card.Body>
      </Card>

      <Card>
        <Card.Body>
          {isLoading ? (
            <p>載入中…</p>
          ) : isError ? (
            <p role="alert" className="text-danger mb-0">載入疑似異常值失敗，請稍後再試</p>
          ) : (
            <>
              <Table bordered hover responsive size="sm" className="dense-list-table">
                <thead className="table-secondary">
                  <tr>
                    <th>檢驗ID</th>
                    <th>測試日期</th>
                    <th>材質</th>
                    <th>產品尺寸</th>
                    <th>項目</th>
                    <th>位置</th>
                    <th>量測值</th>
                    <th>同組中位數</th>
                    <th>正常範圍</th>
                    <th>同爐次其他值</th>
                    <th>提示</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.識別碼} className={row.排除統計 ? 'table-light text-muted' : undefined}>
                      <td className="text-muted">{row.檢驗ID}</td>
                      <td>{row.測試日期 ?? '—'}</td>
                      <td>{row.材質}</td>
                      <td>{row.產品尺寸}</td>
                      <td>{row.量測項目}</td>
                      <td>{row.測量位置}{row.取樣序}</td>
                      <td className={row.排除統計 ? undefined : 'text-danger fw-bold'}>{row.量測值}</td>
                      <td>{row.同組中位數 ?? '—'}</td>
                      <td>
                        {row.正常下界 !== null && row.正常上界 !== null
                          ? `${row.正常下界} ～ ${row.正常上界}`
                          : `資料不足（${row.同組筆數} 筆）`}
                      </td>
                      <td>
                        {row.同爐次其他值.length === 0 ? '—' : row.同爐次其他值.map((sibling) => (
                          <div
                            key={`${sibling.測量位置}-${sibling.取樣序}`}
                            className={sibling.排除統計 ? 'text-decoration-line-through' : undefined}
                          >
                            {`${sibling.測量位置}${sibling.取樣序}：${sibling.量測值}`}
                          </div>
                        ))}
                      </td>
                      <td className="text-truncate" style={{ maxWidth: 220 }} title={row.提示}>
                        {row.提示}
                      </td>
                      <td>
                        <div className="d-flex flex-wrap gap-1">
                          <PermissionAction permission="mechanical.edit" reasonDisplay="tooltip">
                            <Button size="sm" variant="outline-primary" onClick={() => onEdit(row.檢驗ID)}>
                              編輯
                            </Button>
                          </PermissionAction>
                          <PermissionAction
                            permission="mechanical.edit"
                            permissions={['spc.manage']}
                            reasonDisplay="tooltip"
                          >
                            {row.排除統計 ? (
                              <Button size="sm" variant="outline-success" onClick={() => openExclusion(row, false)}>
                                恢復統計
                              </Button>
                            ) : (
                              <Button size="sm" variant="outline-warning" onClick={() => openExclusion(row, true)}>
                                排除統計
                              </Button>
                            )}
                          </PermissionAction>
                        </div>
                        {row.排除統計 && (
                          <div className="small text-muted">已排除：{row.排除原因 || '未填原因'}</div>
                        )}
                      </td>
                    </tr>
                  ))}
                  {data && rows.length === 0 && (
                    <tr>
                      <td colSpan={12} className="text-center text-muted">目前沒有疑似異常值</td>
                    </tr>
                  )}
                </tbody>
              </Table>
              {data && (
                <div className="d-flex flex-wrap justify-content-between align-items-center gap-2">
                  <span>共 {data.total} 筆</span>
                  <div className="d-flex align-items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline-secondary"
                      disabled={page <= 1}
                      onClick={() => setPage((current) => current - 1)}
                    >
                      上一頁
                    </Button>
                    <span>第 {data.page} / {Math.max(data.total_pages, 1)} 頁</span>
                    <Button
                      size="sm"
                      variant="outline-secondary"
                      disabled={page >= data.total_pages}
                      onClick={() => setPage((current) => current + 1)}
                    >
                      下一頁
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </Card.Body>
      </Card>

      <Modal show={pending !== null} onHide={() => setPending(null)} centered>
        <Modal.Header closeButton>
          <Modal.Title>{pending?.excluded ? '排除統計' : '恢復統計'}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {pending && (
            <p className="mb-2">
              {`檢驗ID ${pending.row.檢驗ID} / ${pending.row.量測項目} / `}
              {`${pending.row.測量位置}${pending.row.取樣序} / 量測值 ${pending.row.量測值}`}
            </p>
          )}
          {pending?.excluded && (
            <p className="small text-muted">
              排除後數值仍保留並可追溯，只是不納入 SPC 計算；若只是打錯數字，請改用「編輯」更正。
            </p>
          )}
          <Form.Label htmlFor="mechanical-exclusion-reason">原因</Form.Label>
          <Form.Control
            id="mechanical-exclusion-reason"
            as="textarea"
            rows={2}
            maxLength={200}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setPending(null)}>取消</Button>
          <Button
            variant={pending?.excluded ? 'warning' : 'success'}
            disabled={!reason.trim() || exclusionMutation.isPending}
            onClick={() => pending && exclusionMutation.mutate(pending)}
          >
            {pending?.excluded ? '確認排除' : '確認恢復'}
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
}
