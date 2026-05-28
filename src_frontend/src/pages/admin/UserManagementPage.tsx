import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Form, Table, Badge, Modal, Alert, Spinner, Nav } from 'react-bootstrap';
import toast from 'react-hot-toast';
import api from '../../services/api';
import { useAuth } from '../../context/useAuth';
import { useRoles } from '../../context/useRoles';
import type { UserRecord } from '../../types';
import type { RoleOption } from '../../context/useRoles';

// ── 權限定義（顯示用） ────────────────────────────────────
const PERMISSION_GROUPS: { label: string; perms: { key: string; label: string }[] }[] = [
    {
        label: 'NCMR',
        perms: [
            { key: 'ncmr.view', label: '查看' },
            { key: 'ncmr.create', label: '建立' },
            { key: 'ncmr.edit_own', label: '編輯（自己）' },
            { key: 'ncmr.edit', label: '編輯（所有）' },
            { key: 'ncmr.delete', label: '刪除' },
        ],
    },
    {
        label: 'CAPA',
        perms: [
            { key: 'capa.view', label: '查看' },
            { key: 'capa.create', label: '建立' },
            { key: 'capa.edit', label: '編輯' },
            { key: 'capa.close', label: '結案' },
        ],
    },
    {
        label: '重工',
        perms: [
            { key: 'rework.view', label: '查看' },
            { key: 'rework.create', label: '建立' },
            { key: 'rework.approve', label: '審核' },
            { key: 'rework.delete', label: '刪除' },
        ],
    },
    {
        label: '客訴',
        perms: [
            { key: 'complaint.view', label: '查看' },
            { key: 'complaint.create', label: '建立' },
            { key: 'complaint.edit', label: '編輯' },
            { key: 'complaint.delete', label: '刪除' },
        ],
    },
    {
        label: '出貨巡檢',
        perms: [
            { key: 'shipping.view', label: '查看' },
            { key: 'shipping.create', label: '建立' },
            { key: 'shipping.edit_own', label: '編輯（自己）' },
            { key: 'shipping.edit', label: '編輯（所有）' },
            { key: 'shipping.delete', label: '刪除' },
        ],
    },
    {
        label: '巡線',
        perms: [
            { key: 'patrol.view', label: '查看' },
            { key: 'patrol.create', label: '建立' },
            { key: 'patrol.edit_own', label: '編輯（自己）' },
            { key: 'patrol.edit', label: '編輯（所有）' },
            { key: 'patrol.delete', label: '刪除' },
        ],
    },
    {
        label: '廠商 / 報表 / 管理',
        perms: [
            { key: 'vendor.manage', label: '廠商管理' },
            { key: 'report.view', label: '報表查看' },
            { key: 'user.manage', label: '使用者管理' },
        ],
    },
];

// ── API 函式 ──────────────────────────────────────────────
const fetchUsers = async (): Promise<UserRecord[]> => {
    const res = await api.get<UserRecord[]>('/users');
    return res.data;
};

const createUser = async (data: { username: string; password: string; role: string }) => {
    const res = await api.post('/users', data);
    return res.data;
};

const updateRole = async ({ id, role }: { id: number; role: string }) => {
    const res = await api.put(`/users/${id}/role`, { role });
    return res.data;
};

const updateActive = async ({ id, is_active }: { id: number; is_active: boolean }) => {
    const res = await api.put(`/users/${id}/active`, { is_active });
    return res.data;
};

const updateRolePermissions = async ({ code, permissions }: { code: string; permissions: Record<string, boolean> }) => {
    const res = await api.patch(`/roles/${code}`, { permissions });
    return res.data;
};

// ── 工具函式 ──────────────────────────────────────────────
const formatCreatedAt = (iso: string | null): string => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' });
};

const getErrorMessage = (err: unknown): string => {
    if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { error?: string } } };
        return axiosErr.response?.data?.error ?? '操作失敗，請稍後再試';
    }
    return '操作失敗，請稍後再試';
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

// ── 角色編輯 Modal ────────────────────────────────────────
const RoleEditModal = ({
    role,
    onHide,
}: {
    role: RoleOption | null;
    onHide: () => void;
}) => {
    const queryClient = useQueryClient();
    const [perms, setPerms] = useState<Record<string, boolean>>(role?.permissions ?? {});

    const mutation = useMutation({
        mutationFn: updateRolePermissions,
        onSuccess: () => {
            toast.success(`「${role?.name}」權限已更新`);
            queryClient.invalidateQueries({ queryKey: ['roles'] });
            onHide();
        },
        onError: (err) => toast.error(getErrorMessage(err)),
    });

    if (!role) return null;

    const toggle = (key: string, checked: boolean) =>
        setPerms(prev => ({ ...prev, [key]: checked }));

    const handleSave = () => mutation.mutate({ code: role.code, permissions: perms });

    return (
        <Modal show onHide={onHide} centered size="lg">
            <Modal.Header closeButton>
                <Modal.Title>
                    <i className="fa-solid fa-shield-halved me-2"></i>
                    編輯角色權限 — {role.name}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body style={{ maxHeight: '60vh', overflowY: 'auto' }}>
                {PERMISSION_GROUPS.map(group => (
                    <div key={group.label} className="mb-4">
                        <div className="fw-semibold text-primary mb-2 border-bottom pb-1">{group.label}</div>
                        <div className="row row-cols-2 row-cols-md-3 g-2">
                            {group.perms.map(({ key, label }) => (
                                <div key={key} className="col">
                                    <Form.Check
                                        type="checkbox"
                                        id={`perm-${key}`}
                                        label={label}
                                        checked={!!perms[key]}
                                        onChange={e => toggle(key, e.target.checked)}
                                    />
                                    <div className="text-muted" style={{ fontSize: '0.7rem', marginLeft: '1.5rem' }}>
                                        {key}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onHide}>取消</Button>
                <Button variant="primary" onClick={handleSave} disabled={mutation.isPending}>
                    {mutation.isPending
                        ? <><Spinner animation="border" size="sm" className="me-2" />儲存中...</>
                        : <><i className="fa-solid fa-check me-2"></i>儲存權限</>
                    }
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

// ── 主元件 ────────────────────────────────────────────────
const UserManagementPage = () => {
    const queryClient = useQueryClient();
    const { user: currentUser, hasPermission } = useAuth();
    const currentUserId = currentUser ? Number(currentUser.user_id) : null;
    const [activeTab, setActiveTab] = useState<'users' | 'roles'>('users');

    const { data: roleOptions = [] } = useRoles();

    // ── 使用者頁籤 state ──
    const { data: users = [], isLoading, isError } = useQuery({
        queryKey: ['userList'],
        queryFn: fetchUsers,
    });

    const roleMutation = useMutation({
        mutationFn: updateRole,
        onSuccess: () => {
            toast.success('角色已更新');
            queryClient.invalidateQueries({ queryKey: ['userList'] });
        },
        onError: (err) => {
            toast.error(getErrorMessage(err));
            queryClient.invalidateQueries({ queryKey: ['userList'] });
        },
    });

    const activeMutation = useMutation({
        mutationFn: updateActive,
        onSuccess: (_data, variables) => {
            toast.success(variables.is_active ? '帳號已啟用' : '帳號已停用');
            queryClient.invalidateQueries({ queryKey: ['userList'] });
        },
        onError: (err) => toast.error(getErrorMessage(err)),
    });

    const handleRoleChange = (u: UserRecord, newRole: string) => {
        if (newRole === 'admin' && u.role !== 'admin') {
            if (!window.confirm(`確定要將「${u.username}」升級為管理員？`)) return;
        }
        roleMutation.mutate({ id: u.id, role: newRole });
    };

    // 新增使用者 Modal
    const [showModal, setShowModal] = useState(false);
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newConfirm, setNewConfirm] = useState('');
    const [newRole, setNewRole] = useState<string>('inspector');
    const [formError, setFormError] = useState('');

    const createMutation = useMutation({
        mutationFn: createUser,
        onSuccess: () => {
            toast.success('使用者建立成功');
            queryClient.invalidateQueries({ queryKey: ['userList'] });
            setShowModal(false);
            resetForm();
        },
        onError: (err) => setFormError(getErrorMessage(err)),
    });

    const resetForm = () => {
        setNewUsername(''); setNewPassword(''); setNewConfirm('');
        setNewRole('inspector'); setFormError('');
    };

    const handleCreateSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setFormError('');
        const trimmedUsername = newUsername.trim();
        if (!/^[A-Za-z0-9_\-.]{3,50}$/.test(trimmedUsername)) {
            setFormError('使用者名稱長度需 3–50 字元，僅允許英數字、底線、連字號、點號');
            return;
        }
        if (newPassword !== newConfirm) { setFormError('兩次密碼輸入不一致'); return; }
        if (newPassword.length < 8) { setFormError('密碼長度至少需要 8 個字元'); return; }
        createMutation.mutate({ username: trimmedUsername, password: newPassword, role: newRole });
    };

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
                    <Button variant="primary" onClick={() => { resetForm(); setShowModal(true); }}>
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
                            <Table hover responsive className="mb-0">
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
                                                    <Button
                                                        size="sm"
                                                        variant={u.is_active ? 'outline-danger' : 'outline-success'}
                                                        disabled={isSelf || activeMutation.isPending}
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

            {/* 新增使用者 Modal */}
            <Modal show={showModal} onHide={() => setShowModal(false)} centered>
                <Modal.Header closeButton>
                    <Modal.Title>
                        <i className="fa-solid fa-user-plus me-2"></i>新增使用者
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {formError && <Alert variant="danger">{formError}</Alert>}
                    <Form onSubmit={handleCreateSubmit} id="createUserForm">
                        <Form.Group className="mb-3">
                            <Form.Label>使用者名稱</Form.Label>
                            <Form.Control
                                type="text"
                                placeholder="3–50 字元，英數字、底線、連字號、點號"
                                value={newUsername}
                                maxLength={50}
                                onChange={e => setNewUsername(e.target.value)}
                                required
                            />
                        </Form.Group>
                        <Form.Group className="mb-3">
                            <Form.Label>密碼</Form.Label>
                            <Form.Control
                                type="password"
                                placeholder="至少 8 個字元"
                                value={newPassword}
                                onChange={e => setNewPassword(e.target.value)}
                                required
                                minLength={8}
                            />
                        </Form.Group>
                        <Form.Group className="mb-3">
                            <Form.Label>確認密碼</Form.Label>
                            <Form.Control
                                type="password"
                                placeholder="再次輸入密碼"
                                value={newConfirm}
                                onChange={e => setNewConfirm(e.target.value)}
                                required
                            />
                        </Form.Group>
                        <Form.Group className="mb-1">
                            <Form.Label>角色</Form.Label>
                            <Form.Select value={newRole} onChange={e => setNewRole(e.target.value)}>
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
                        </Form.Group>
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowModal(false)}>取消</Button>
                    <Button
                        variant="primary"
                        type="submit"
                        form="createUserForm"
                        disabled={createMutation.isPending}
                    >
                        {createMutation.isPending
                            ? <><Spinner animation="border" size="sm" className="me-2" />建立中...</>
                            : <><i className="fa-solid fa-check me-2"></i>建立使用者</>
                        }
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* 角色權限編輯 Modal */}
            {editingRole && (
                <RoleEditModal role={editingRole} onHide={() => setEditingRole(null)} />
            )}
        </div>
    );
};

export default UserManagementPage;
