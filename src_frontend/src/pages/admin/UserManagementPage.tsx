import { useState } from 'react';
import { Button, Card, Form, Table, Badge, Alert, Spinner, Nav, Modal } from 'react-bootstrap';
import ConfirmActionModal, { type ConfirmActionState } from '../../components/common/ConfirmActionModal';
import { useAuth } from '../../context/useAuth';
import { useRoles } from '../../context/useRoles';
import type { UserRecord } from '../../types';
import type { RoleOption } from '../../context/useRoles';
import {
    useAdminUsers,
    useResetAdminUserPassword,
    useUpdateAdminUserActive,
    useUpdateAdminUserRole,
} from '../../hooks/useAdmin';
import CreateUserModal from './CreateUserModal';
import RoleEditModal from './RoleEditModal';

const formatCreatedAt = (iso: string | null): string => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' });
};

// ── 角色權限標籤（摘要用） ────────────────────────────────
const PermBadges = ({ permissions }: { permissions: Record<string, boolean> }) => {
    const active = Object.entries(permissions)
        .filter(([, v]) => v)
        .map(([k]) => k);
    if (active.length === 0) return <span className="text-muted small">無權限</span>;
    return (
        <div className="d-flex flex-wrap gap-1">
            {active.map(k => (
                <Badge key={k} bg="secondary" className="fw-normal" style={{ fontSize: '0.7rem' }}>
                    {k}
                </Badge>
            ))}
        </div>
    );
};

// ── 主元件 ────────────────────────────────────────────────
const UserManagementPage = () => {
    const { user: currentUser, hasPermission } = useAuth();
    const currentUserId = currentUser ? Number(currentUser.user_id) : null;
    const [activeTab, setActiveTab] = useState<'users' | 'roles'>('users');
    const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null);

    const { data: roleOptions = [] } = useRoles();

    // ── 使用者頁籤 state ──
    const { data: users = [], isLoading, isError } = useAdminUsers();
    const roleMutation = useUpdateAdminUserRole();
    const activeMutation = useUpdateAdminUserActive();
    const [resetTarget, setResetTarget] = useState<UserRecord | null>(null);
    const [resetPassword, setResetPassword] = useState('');
    const [resetError, setResetError] = useState('');
    const closeResetModal = () => {
        setResetTarget(null);
        setResetPassword('');
        setResetError('');
    };
    const resetPasswordMutation = useResetAdminUserPassword({
        onSuccess: closeResetModal,
    });

    const handleResetPassword = (event: React.FormEvent) => {
        event.preventDefault();
        setResetError('');
        if (!resetTarget) return;
        if (resetPassword.length < 8) {
            setResetError('密碼長度至少需要 8 個字元');
            return;
        }
        resetPasswordMutation.mutate({
            id: resetTarget.id,
            password: resetPassword,
        });
    };

    const handleRoleChange = (u: UserRecord, newRole: string) => {
        if (newRole === 'admin' && u.role !== 'admin') {
            setConfirmAction({
                title: '升級為管理員',
                message: `確定要將「${u.username}」升級為管理員？`,
                confirmLabel: '升級',
                confirmVariant: 'warning',
                onConfirm: () => roleMutation.mutateAsync({ id: u.id, role: newRole }),
            });
            return;
        }
        roleMutation.mutate({ id: u.id, role: newRole });
    };

    const [showModal, setShowModal] = useState(false);

    // ── 角色頁籤 state ──
    const [editingRole, setEditingRole] = useState<RoleOption | null>(null);

    // ── 渲染 ────────────────────────────────────────────
    return (
        <div className="container-fluid py-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h4 className="mb-0">
                    <i className="fa-solid fa-users-gear me-2 text-primary"></i>使用者管理
                </h4>
                {activeTab === 'users' && (
                    <Button variant="primary" onClick={() => setShowModal(true)}>
                        <i className="fa-solid fa-user-plus me-2"></i>新增使用者
                    </Button>
                )}
            </div>

            <Nav variant="tabs" className="mb-3" activeKey={activeTab} onSelect={k => setActiveTab(k as 'users' | 'roles')}>
                <Nav.Item>
                    <Nav.Link eventKey="users">
                        <i className="fa-solid fa-users me-2"></i>使用者
                    </Nav.Link>
                </Nav.Item>
                <Nav.Item>
                    <Nav.Link eventKey="roles">
                        <i className="fa-solid fa-shield-halved me-2"></i>角色與權限
                    </Nav.Link>
                </Nav.Item>
            </Nav>

            {/* ── 使用者頁籤 ── */}
            {activeTab === 'users' && (
                <Card className="shadow-sm border-0">
                    <Card.Body className="p-0">
                        {isLoading && (
                            <div className="text-center py-5">
                                <Spinner animation="border" variant="primary" />
                            </div>
                        )}
                        {isError && (
                            <Alert variant="danger" className="m-3">載入使用者列表失敗，請重新整理頁面</Alert>
                        )}
                        {!isLoading && !isError && (
                            <Table hover responsive className="dense-list-table mb-0">
                                <thead className="table-light">
                                    <tr>
                                        <th className="ps-4">#</th>
                                        <th>使用者名稱</th>
                                        <th>角色</th>
                                        <th>帳號狀態</th>
                                        <th>建立日期</th>
                                        <th className="text-end pe-4">操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(u => {
                                        const isSelf = u.id === currentUserId;
                                        return (
                                            <tr key={u.id}>
                                                <td className="ps-4 text-muted">{u.id}</td>
                                                <td>
                                                    <i className="fa-solid fa-user me-2 text-secondary"></i>
                                                    {u.username}
                                                    {isSelf && <Badge bg="info" className="ms-2 fw-normal">我</Badge>}
                                                </td>
                                                <td>
                                                    <Form.Select
                                                        size="sm"
                                                        style={{ width: '130px' }}
                                                        value={u.role}
                                                        disabled={isSelf || roleMutation.isPending || !hasPermission('user.manage')}
                                                        title={isSelf ? '無法修改自己的角色' : !hasPermission('user.manage') ? '無此操作權限' : undefined}
                                                        onChange={e => handleRoleChange(u, e.target.value)}
                                                    >
                                                        {roleOptions.length > 0
                                                            ? roleOptions.map(r => (
                                                                <option key={r.code} value={r.code}>{r.name}</option>
                                                            ))
                                                            : (
                                                                <>
                                                                    <option value="inspector">檢驗員</option>
                                                                    <option value="admin">系統管理員</option>
                                                                </>
                                                            )
                                                        }
                                                    </Form.Select>
                                                </td>
                                                <td>
                                                    <Badge bg={u.is_active ? 'success' : 'secondary'}>
                                                        {u.is_active ? '啟用中' : '已停用'}
                                                    </Badge>
                                                </td>
                                                <td className="text-muted small">{formatCreatedAt(u.created_at)}</td>
                                                <td className="text-end pe-4">
                                                    {hasPermission('user.manage') && (
                                                        <Button
                                                            size="sm"
                                                            variant="outline-primary"
                                                            className="me-2"
                                                            aria-label={`重設 ${u.username} 的密碼`}
                                                            disabled={resetPasswordMutation.isPending}
                                                            onClick={() => setResetTarget(u)}
                                                        >
                                                            <i className="fa-solid fa-key me-1"></i>重設密碼
                                                        </Button>
                                                    )}
                                                    <Button
                                                        size="sm"
                                                        variant={u.is_active ? 'outline-danger' : 'outline-success'}
                                                        disabled={isSelf || activeMutation.isPending || !hasPermission('user.manage')}
                                                        title={isSelf ? '無法停用自己的帳號' : undefined}
                                                        onClick={() => activeMutation.mutate({ id: u.id, is_active: !u.is_active })}
                                                    >
                                                        {u.is_active
                                                            ? <><i className="fa-solid fa-ban me-1"></i>停用</>
                                                            : <><i className="fa-solid fa-check me-1"></i>啟用</>
                                                        }
                                                    </Button>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {users.length === 0 && (
                                        <tr>
                                            <td colSpan={6} className="text-center text-muted py-4">尚無使用者資料</td>
                                        </tr>
                                    )}
                                </tbody>
                            </Table>
                        )}
                    </Card.Body>
                </Card>
            )}

            {/* ── 角色與權限頁籤 ── */}
            {activeTab === 'roles' && (
                <Card className="shadow-sm border-0">
                    <Card.Body className="p-0">
                        <Table hover responsive className="mb-0">
                            <thead className="table-light">
                                <tr>
                                    <th className="ps-4" style={{ width: '90px' }}>代碼</th>
                                    <th style={{ width: '120px' }}>角色名稱</th>
                                    <th>已啟用權限</th>
                                    <th className="text-end pe-4" style={{ width: '100px' }}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {roleOptions.map(r => (
                                    <tr key={r.code}>
                                        <td className="ps-4">
                                            <code className="text-secondary small">{r.code}</code>
                                        </td>
                                        <td className="fw-semibold">{r.name}</td>
                                        <td><PermBadges permissions={r.permissions} /></td>
                                        <td className="text-end pe-4">
                                            {hasPermission('user.manage') && (
                                                <Button
                                                    size="sm"
                                                    variant="outline-primary"
                                                    onClick={() => setEditingRole(r)}
                                                >
                                                    <i className="fa-solid fa-pen me-1"></i>編輯
                                                </Button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                                {roleOptions.length === 0 && (
                                    <tr>
                                        <td colSpan={4} className="text-center text-muted py-4">載入角色資料中…</td>
                                    </tr>
                                )}
                            </tbody>
                        </Table>
                    </Card.Body>
                </Card>
            )}

            <CreateUserModal
                show={showModal}
                roleOptions={roleOptions}
                onHide={() => setShowModal(false)}
            />

            <Modal show={!!resetTarget} onHide={closeResetModal} centered>
                <Modal.Header closeButton>
                    <Modal.Title>重設「{resetTarget?.username}」密碼</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {resetError && <Alert variant="danger">{resetError}</Alert>}
                    <Form
                        id="resetUserPasswordForm"
                        aria-label="重設密碼表單"
                        onSubmit={handleResetPassword}
                    >
                        <Form.Group>
                            <Form.Label htmlFor="resetUserPassword">新密碼</Form.Label>
                            <Form.Control
                                id="resetUserPassword"
                                type="password"
                                value={resetPassword}
                                minLength={8}
                                autoComplete="new-password"
                                onChange={event => setResetPassword(event.target.value)}
                                required
                            />
                            <Form.Text muted>至少 8 個字元；完成後會撤銷該帳號既有登入憑證。</Form.Text>
                        </Form.Group>
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={closeResetModal}>取消</Button>
                    <Button
                        variant="primary"
                        type="submit"
                        form="resetUserPasswordForm"
                        aria-label="確認重設密碼"
                        disabled={resetPasswordMutation.isPending}
                    >
                        {resetPasswordMutation.isPending ? '重設中…' : '確認重設'}
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* 角色權限編輯 Modal */}
            {editingRole && (
                <RoleEditModal role={editingRole} onHide={() => setEditingRole(null)} />
            )}
            <ConfirmActionModal action={confirmAction} onHide={() => setConfirmAction(null)} />
        </div>
    );
};

export default UserManagementPage;
