interface MechanicalTestFormProps {
  testId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

export default function MechanicalTestForm({ testId, onClose }: MechanicalTestFormProps) {
  return (
    <div role="dialog" aria-label="機械性質檢驗表單">
      <p>{testId === null ? '新增檢驗' : '編輯檢驗'}</p>
      <button type="button" className="btn btn-sm" onClick={onClose}>關閉</button>
    </div>
  );
}
