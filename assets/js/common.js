/**
 * 品保管理系統 - 共用腳本
 * 統一的互動功能與工具函數
 */

// ========================================
// 1. 全域配置
// ========================================
const CONFIG = {
    API_BASE: window.location.protocol === 'file:' 
        ? 'http://localhost:5001' 
        : `${window.location.protocol}//${window.location.hostname}:${window.location.port || '5000'}`,
    TOKEN_KEY: 'authToken',
    USER_KEY: 'username'
};

// ========================================
// 2. 載入動畫控制
// ========================================
const PageLoader = {
    show() {
        const loader = document.querySelector('.page-loader');
        if (loader) {
            loader.classList.remove('hidden');
        }
    },
    
    hide() {
        const loader = document.querySelector('.page-loader');
        if (loader) {
            setTimeout(() => {
                loader.classList.add('hidden');
            }, 500);
        }
    },
    
    init() {
        // 頁面載入完成後隱藏 loader
        window.addEventListener('load', () => this.hide());
    }
};

// ========================================
// 3. 認證相關功能
// ========================================
const Auth = {
    getToken() {
        return localStorage.getItem(CONFIG.TOKEN_KEY);
    },
    
    setToken(token) {
        localStorage.setItem(CONFIG.TOKEN_KEY, token);
    },
    
    getUsername() {
        return localStorage.getItem(CONFIG.USER_KEY);
    },
    
    setUsername(username) {
        localStorage.setItem(CONFIG.USER_KEY, username);
    },
    
    clear() {
        localStorage.removeItem(CONFIG.TOKEN_KEY);
        localStorage.removeItem(CONFIG.USER_KEY);
    },
    
    isAuthenticated() {
        return !!this.getToken();
    },
    
    getHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    },
    
    async fetchWithAuth(url, options = {}) {
        if (!options.headers) options.headers = {};
        Object.assign(options.headers, this.getHeaders());
        
        try {
            const res = await fetch(url, options);
            
            if (res.status === 401) {
                this.handleUnauthorized();
                return null;
            }
            
            return res;
        } catch (err) {
            console.error('API 呼叫失敗:', err);
            throw err;
        }
    },
    
    handleUnauthorized() {
        alert('認證失效，請重新登入');
        this.clear();
        window.location.href = 'index.html';
    },
    
    logout() {
        this.clear();
        window.location.href = 'index.html';
    }
};

// ========================================
// 4. Toast 通知系統
// ========================================
const Toast = {
    container: null,
    
    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container position-fixed top-0 end-0 p-3';
            this.container.style.zIndex = '9999';
            document.body.appendChild(this.container);
        }
    },
    
    show(message, type = 'info', duration = 3000) {
        this.init();
        
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-modern animate-slide-in`;
        toast.style.minWidth = '300px';
        toast.innerHTML = `
            <i class="fas fa-${this.getIcon(type)}"></i>
            <span>${message}</span>
        `;
        
        this.container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },
    
    success(message, duration) {
        this.show(message, 'success', duration);
    },
    
    error(message, duration) {
        this.show(message, 'danger', duration);
    },
    
    warning(message, duration) {
        this.show(message, 'warning', duration);
    },
    
    info(message, duration) {
        this.show(message, 'info', duration);
    },
    
    getIcon(type) {
        const icons = {
            success: 'check-circle',
            danger: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
};

// ========================================
// 5. 確認對話框
// ========================================
const ConfirmDialog = {
    async show(message, title = '確認') {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal fade show';
            modal.style.display = 'block';
            modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content" style="border-radius: 1rem; border: none;">
                        <div class="modal-header border-0">
                            <h5 class="modal-title fw-bold">${title}</h5>
                            <button type="button" class="btn-close" onclick="this.closest('.modal').remove()"></button>
                        </div>
                        <div class="modal-body py-4">
                            <p class="mb-0">${message}</p>
                        </div>
                        <div class="modal-footer border-0">
                            <button type="button" class="btn btn-secondary" data-action="cancel">取消</button>
                            <button type="button" class="btn btn-primary" data-action="confirm">確定</button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            modal.querySelector('[data-action="cancel"]').addEventListener('click', () => {
                modal.remove();
                resolve(false);
            });
            
            modal.querySelector('[data-action="confirm"]').addEventListener('click', () => {
                modal.remove();
                resolve(true);
            });
            
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.remove();
                    resolve(false);
                }
            });
        });
    }
};

// ========================================
// 6. 表單驗證工具
// ========================================
const FormValidator = {
    validateRequired(value) {
        return value && value.toString().trim() !== '';
    },
    
    validateDate(dateStr) {
        if (!dateStr) return false;
        const regex = /^\d{4}-\d{2}-\d{2}$/;
        if (!regex.test(dateStr)) return false;
        const date = new Date(dateStr);
        return date instanceof Date && !isNaN(date);
    },
    
    validateNumber(value, min = null, max = null) {
        const num = parseFloat(value);
        if (isNaN(num)) return false;
        if (min !== null && num < min) return false;
        if (max !== null && num > max) return false;
        return true;
    },
    
    validateEmail(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    },
    
    showError(input, message) {
        input.classList.add('is-invalid');
        
        let feedback = input.nextElementSibling;
        if (!feedback || !feedback.classList.contains('invalid-feedback')) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            input.parentNode.insertBefore(feedback, input.nextSibling);
        }
        feedback.textContent = message;
    },
    
    clearError(input) {
        input.classList.remove('is-invalid');
        const feedback = input.nextElementSibling;
        if (feedback && feedback.classList.contains('invalid-feedback')) {
            feedback.remove();
        }
    },
    
    clearAllErrors(form) {
        form.querySelectorAll('.is-invalid').forEach(input => {
            this.clearError(input);
        });
    }
};

// ========================================
// 7. 資料處理工具
// ========================================
const DataUtils = {
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;
        return date.toISOString().split('T')[0];
    },
    
    formatNumber(num, decimals = 3) {
        if (num === null || num === undefined || isNaN(num)) return '';
        return parseFloat(num).toFixed(decimals);
    },
    
    formatDateTime(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;
        return date.toLocaleString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    downloadFile(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    }
};

// ========================================
// 8. 動畫效果
// ========================================
const Animations = {
    fadeIn(element, duration = 300) {
        element.style.opacity = '0';
        element.style.display = 'block';
        element.style.transition = `opacity ${duration}ms ease`;
        
        requestAnimationFrame(() => {
            element.style.opacity = '1';
        });
    },
    
    fadeOut(element, duration = 300) {
        element.style.transition = `opacity ${duration}ms ease`;
        element.style.opacity = '0';
        
        setTimeout(() => {
            element.style.display = 'none';
        }, duration);
    },
    
    slideDown(element, duration = 300) {
        element.style.maxHeight = '0';
        element.style.overflow = 'hidden';
        element.style.transition = `max-height ${duration}ms ease`;
        
        requestAnimationFrame(() => {
            element.style.maxHeight = element.scrollHeight + 'px';
        });
    },
    
    slideUp(element, duration = 300) {
        element.style.transition = `max-height ${duration}ms ease`;
        element.style.maxHeight = '0';
        
        setTimeout(() => {
            element.style.display = 'none';
        }, duration);
    },
    
    stagger(elements, animationClass, delay = 100) {
        elements.forEach((el, index) => {
            setTimeout(() => {
                el.classList.add(animationClass);
            }, index * delay);
        });
    }
};

// ========================================
// 9. 表格排序與搜尋
// ========================================
const TableUtils = {
    sort(table, column, direction = 'asc') {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            const aVal = a.cells[column].textContent.trim();
            const bVal = b.cells[column].textContent.trim();
            
            // 嘗試數字比較
            const aNum = parseFloat(aVal);
            const bNum = parseFloat(bVal);
            
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return direction === 'asc' ? aNum - bNum : bNum - aNum;
            }
            
            // 字串比較
            return direction === 'asc' 
                ? aVal.localeCompare(bVal, 'zh-TW')
                : bVal.localeCompare(aVal, 'zh-TW');
        });
        
        rows.forEach(row => tbody.appendChild(row));
    },
    
    filter(table, searchTerm) {
        const rows = table.querySelectorAll('tbody tr');
        const term = searchTerm.toLowerCase();
        
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(term) ? '' : 'none';
        });
    }
};

// ========================================
// 10. 初始化
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    // 初始化載入動畫
    PageLoader.init();
    
    // 為所有按鈕添加點擊效果
    document.querySelectorAll('.btn-modern, .btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            ripple.style.cssText = `
                position: absolute;
                background: rgba(255,255,255,0.3);
                border-radius: 50%;
                transform: scale(0);
                animation: ripple 0.6s linear;
                pointer-events: none;
            `;
            
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = e.clientX - rect.left - size/2 + 'px';
            ripple.style.top = e.clientY - rect.top - size/2 + 'px';
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => ripple.remove(), 600);
        });
    });
});

// 添加 ripple 動畫 CSS
const rippleStyle = document.createElement('style');
rippleStyle.textContent = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(rippleStyle);

// 匯出全域變數
window.CONFIG = CONFIG;
window.PageLoader = PageLoader;
window.Auth = Auth;
window.Toast = Toast;
window.ConfirmDialog = ConfirmDialog;
window.FormValidator = FormValidator;
window.DataUtils = DataUtils;
window.Animations = Animations;
window.TableUtils = TableUtils;
