import { useNavigate } from 'react-router';
import { useDashboardTodos } from '../../hooks/useDashboard';
import type { TodoItem } from '../../hooks/useDashboard';

const TodoList = () => {
    const navigate = useNavigate();
    const { todos, loading, error } = useDashboardTodos();

    const getTypeIcon = (type: string) => {
        switch (type) {
            case 'ncmr':
                return { icon: 'fa-triangle-exclamation', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' };
            case 'capa':
                return { icon: 'fa-file-signature', color: '#0ea5e9', bg: 'rgba(14, 165, 233, 0.1)' };
            case 'rework':
                return { icon: 'fa-rotate', color: '#14b8a6', bg: 'rgba(20, 184, 166, 0.1)' };
            default:
                return { icon: 'fa-tasks', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.1)' };
        }
    };

    const getPriorityBadge = (priority: string) => {
        switch (priority) {
            case 'high':
                return { label: '緊急', class: 'badge-danger' };
            case 'medium':
                return { label: '一般', class: 'badge-warning' };
            default:
                return { label: '低', class: 'badge-secondary' };
        }
    };

    const formatDate = (dateStr: string | null) => {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const today = new Date();
        const diffDays = Math.floor((today.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return '今天';
        if (diffDays === 1) return '昨天';
        if (diffDays < 7) return `${diffDays} 天前`;
        return date.toLocaleDateString('zh-TW');
    };

    if (loading) {
        return (
            <div className="card mb-4">
                <div className="card-header">
                    <i className="fa-solid fa-clipboard-list me-2 text-primary"></i>
                    <span className="fw-bold">待處理事項</span>
                </div>
                <div className="card-body">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="todo-item-skeleton mb-3">
                            <div className="skeleton-line"></div>
                            <div className="skeleton-line short"></div>
                        </div>
                    ))}
                </div>
            </div>
        );
    }

    if (error || !todos || todos.length === 0) {
        return (
            <div className="card mb-4">
                <div className="card-header d-flex align-items-center">
                    <i className="fa-solid fa-clipboard-list me-2 text-primary"></i>
                    <span className="fw-bold">待處理事項</span>
                </div>
                <div className="card-body text-center text-muted py-4">
                    <i className="fa-solid fa-check-circle fa-2x mb-2 text-success"></i>
                    <p className="mb-0">目前沒有待處理事項</p>
                </div>
            </div>
        );
    }

    return (
        <div className="card mb-4">
            <div className="card-header d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center">
                    <i className="fa-solid fa-clipboard-list me-2 text-primary"></i>
                    <span className="fw-bold">待處理事項</span>
                </div>
                <span className="badge bg-primary rounded-pill">{todos.length}</span>
            </div>
            <div className="card-body p-0">
                <div className="list-group list-group-flush">
                    {todos.map((todo: TodoItem, index: number) => {
                        const typeInfo = getTypeIcon(todo.type);
                        const priorityInfo = getPriorityBadge(todo.priority);
                        
                        return (
                            <a
                                key={index}
                                href={todo.path}
                                className="list-group-item list-group-item-action d-flex align-items-center p-3"
                                onClick={(e) => {
                                    e.preventDefault();
                                    navigate(todo.path);
                                }}
                            >
                                <div 
                                    className="todo-type-icon me-3"
                                    style={{ 
                                        backgroundColor: typeInfo.bg,
                                        color: typeInfo.color 
                                    }}
                                >
                                    <i className={`fa-solid ${typeInfo.icon}`}></i>
                                </div>
                                <div className="flex-grow-1 min-width-0">
                                    <div className="d-flex justify-content-between align-items-center mb-1">
                                        <span className="todo-title text-truncate fw-semibold">
                                            {todo.title}
                                        </span>
                                        <span className={`badge ${priorityInfo.class} ms-2`}>
                                            {priorityInfo.label}
                                        </span>
                                    </div>
                                    {todo.description && (
                                        <p className="todo-desc text-muted mb-0 text-truncate">
                                            {todo.description}
                                        </p>
                                    )}
                                </div>
                                {todo.date && (
                                    <span className="todo-date text-muted ms-2">
                                        {formatDate(todo.date)}
                                    </span>
                                )}
                            </a>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default TodoList;
