interface CalibrationStepperProps {
  currentStep: number;
  onSelect: (step: number) => void;
  enabledThrough: number;
  locked?: boolean;
  minimumStep?: number;
}

const STEPS = ['設備與程序', '條件與證書', '原始讀值', '證據檢閱'];

export default function CalibrationStepper({
  currentStep,
  onSelect,
  enabledThrough,
  locked = false,
  minimumStep = 1,
}: CalibrationStepperProps) {
  return (
    <nav className="cal-stepper" aria-label="校正登錄步驟">
      <ol>
        {STEPS.map((label, index) => {
          const step = index + 1;
          return (
            <li key={label}>
              <button
                type="button"
                aria-current={currentStep === step ? 'step' : undefined}
                disabled={
                  step > enabledThrough
                  || step < minimumStep
                  || (locked && step !== currentStep)
                }
                onClick={() => onSelect(step)}
              >
                <span>{step}</span>
                {label}
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
