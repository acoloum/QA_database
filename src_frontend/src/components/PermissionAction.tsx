import { cloneElement, useId } from 'react';
import type { MouseEventHandler, ReactElement } from 'react';

import { useAuth } from '../context/useAuth';

interface DisabledActionProps {
  disabled?: boolean;
  'aria-describedby'?: string;
  onClick?: MouseEventHandler<HTMLElement>;
}

interface PermissionActionProps {
  permission: string;
  permissions?: readonly string[];
  requireMode?: 'all' | 'any';
  mode?: 'disable' | 'hide';
  reason?: string;
  children: ReactElement<DisabledActionProps>;
}

const DISABLED_INTRINSIC_ELEMENTS = new Set([
  'button',
  'fieldset',
  'input',
  'optgroup',
  'option',
  'select',
  'textarea',
]);

/**
 * 將缺權限的單一動作停用並說明原因；不具 disabled 語意的原生元素會隱藏。
 * 自訂元件必須遵守 disabled prop 契約。
 */
const PermissionAction = ({
  permission,
  permissions = [],
  requireMode = 'all',
  mode = 'disable',
  reason: specifiedReason,
  children,
}: PermissionActionProps) => {
  const { hasPermission } = useAuth();
  const reasonId = `permission-reason-${useId().replaceAll(':', '')}`;
  const requiredPermissions = [...new Set([permission, ...permissions])];
  const checks = requiredPermissions.map((item) => hasPermission(item));
  const allowed = requireMode === 'all' ? checks.every(Boolean) : checks.some(Boolean);

  if (allowed) {
    return children;
  }
  if (mode === 'hide') {
    return null;
  }

  const supportsDisabled = typeof children.type !== 'string'
    || DISABLED_INTRINSIC_ELEMENTS.has(children.type);
  if (!supportsDisabled) {
    throw new Error('PermissionAction child 不支援 disabled；請明確使用 mode="hide"');
  }

  const describedBy = [children.props['aria-describedby'], reasonId]
    .filter(Boolean)
    .join(' ');
  const reason = specifiedReason ?? (requiredPermissions.length === 1
    ? `需要 ${requiredPermissions[0]} 權限`
    : `需要${requireMode === 'all' ? '全部' : '任一'}權限：${requiredPermissions.join('、')}`);

  return (
    <>
      {cloneElement(children, {
        disabled: true,
        'aria-describedby': describedBy,
        onClick: (event) => {
          event.preventDefault();
          event.stopPropagation();
        },
      })}
      <small id={reasonId} className="d-block text-muted">{reason}</small>
    </>
  );
};

export default PermissionAction;
