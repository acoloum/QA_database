import { useEffect, useMemo, useState } from 'react';

import { RIGOR_STEPS } from '../../hooks/useCapa';
import type { CAPADetail, CAPASeverity, D7Action } from '../../types';
import { createCapaDraft, type CapaDraftState } from './capaDraft';

const SEVERITY_TO_RIGOR: Record<string, string> = {
    Critical: '完整8D',
    Major: '完整8D',
    Minor: '簡化5D',
};

const emptyDraft: CapaDraftState = {
    activeTab: 'd0',
    d0Symptom: '',
    d0Criteria: [],
    d0Severity: '',
    d0Rigor: '完整8D',
    d0Deadline: '',
    d1Champion: '',
    d1Leader: '',
    d1Members: [],
    d2What: '',
    d2Where: '',
    d2When: '',
    d2Who: '',
    d2Why: '',
    d2How: '',
    d2HowMany: '',
    d3Action: '',
    d3EffDate: '',
    d3Verif: '',
    d4Tool: '5why',
    d4FiveWhy: [],
    d4Fishbone: {},
    d4RootCause: '',
    d5Action: '',
    d5PlannedDate: '',
    d5VerifyPlan: '',
    d6ImplDate: '',
    d6Result: '',
    d6Verified: false,
    d7Actions: [],
    d8Confirm: '',
    d8Recog: '',
};

export interface UseCapaDraftParams {
    capa?: CAPADetail | null;
    capaId: number | null;
    isClosed: boolean;
    onUpdateStep: (id: number, data: Record<string, unknown>) => void;
    onCloseCapa: (data: { id: number; D8_confirmation: string; D8_recognition: string }) => void;
}

export const useCapaDraft = ({
    capa,
    capaId,
    isClosed,
    onUpdateStep,
    onCloseCapa,
}: UseCapaDraftParams) => {
    const [draft, setDraft] = useState<CapaDraftState>(emptyDraft);

    const setField = <K extends keyof CapaDraftState>(key: K, value: CapaDraftState[K]) => {
        setDraft(prev => ({ ...prev, [key]: value }));
    };

    useEffect(() => {
        if (!capa) return;
        let cancelled = false;
        queueMicrotask(() => {
            if (cancelled) return;
            setDraft(createCapaDraft(capa));
        });
        return () => { cancelled = true; };
    }, [capa]);

    const handleSeverityChange = (value: CAPASeverity | '') => {
        setDraft(prev => ({
            ...prev,
            d0Severity: value,
            d0Rigor: value && !isClosed ? SEVERITY_TO_RIGOR[value] ?? '完整8D' : prev.d0Rigor,
        }));
    };

    const steps = useMemo(
        () => RIGOR_STEPS[draft.d0Rigor] ?? [0, 1, 2, 3, 4, 5, 6, 7, 8],
        [draft.d0Rigor],
    );

    const saveStep = (stepKey: string, payload: Record<string, unknown>) => {
        if (!capaId) return;
        onUpdateStep(capaId, { step: stepKey, ...payload });
    };

    const toggleD7 = (idx: number, checked: boolean) => {
        setDraft(prev => ({
            ...prev,
            d7Actions: prev.d7Actions.map((action, i) => i === idx ? { ...action, checked } : action),
        }));
    };

    const updateD7Field = (idx: number, field: keyof D7Action, value: unknown) => {
        setDraft(prev => ({
            ...prev,
            d7Actions: prev.d7Actions.map((action, i) => i === idx ? { ...action, [field]: value } : action),
        }));
    };

    const handleClose8D = () => {
        if (!capaId || !draft.d8Confirm.trim()) return;
        onCloseCapa({ id: capaId, D8_confirmation: draft.d8Confirm, D8_recognition: draft.d8Recog });
    };

    const stepDone = (n: number) =>
        capa?.progress?.step_status?.[`D${n}`] === true;

    return {
        ...draft,
        steps,
        stepDone,
        handleSeverityChange,
        toggleD7,
        updateD7Field,
        handleClose8D,
        saveD0: () => saveStep('D0', {
            D0_symptom: draft.d0Symptom,
            D0_criteria: draft.d0Criteria,
            D0_severity: draft.d0Severity || null,
            D0_deadline: draft.d0Deadline || null,
            rigor: draft.d0Rigor,
        }),
        saveD1: () => saveStep('D1', {
            D1_champion_id: draft.d1Champion || null,
            D1_leader_id: draft.d1Leader || null,
            D1_members: draft.d1Members,
        }),
        saveD2: () => saveStep('D2', {
            D2_what: draft.d2What,
            D2_where: draft.d2Where,
            D2_when: draft.d2When,
            D2_who: draft.d2Who,
            D2_why: draft.d2Why,
            D2_how: draft.d2How,
            D2_how_many: draft.d2HowMany,
        }),
        saveD3: () => saveStep('D3', {
            D3_action: draft.d3Action,
            D3_effective_date: draft.d3EffDate || null,
            D3_verification: draft.d3Verif,
        }),
        saveD4: () => saveStep('D4', {
            D4_tool: draft.d4Tool,
            D4_five_why: draft.d4Tool === '5why' ? draft.d4FiveWhy : null,
            D4_fishbone: draft.d4Tool === 'fishbone' ? draft.d4Fishbone : null,
            D4_root_cause: draft.d4RootCause,
        }),
        saveD5: () => saveStep('D5', {
            D5_action: draft.d5Action,
            D5_planned_date: draft.d5PlannedDate || null,
            D5_verify_plan: draft.d5VerifyPlan,
        }),
        saveD6: () => saveStep('D6', {
            D6_implement_date: draft.d6ImplDate || null,
            D6_result: draft.d6Result,
            D6_verified: draft.d6Verified,
        }),
        saveD7: () => saveStep('D7', { D7_actions: draft.d7Actions }),
        setActiveTab: (value: string) => setField('activeTab', value),
        setD0Symptom: (value: string) => setField('d0Symptom', value),
        setD0Criteria: (value: string[]) => setField('d0Criteria', value),
        setD0Rigor: (value: string) => setField('d0Rigor', value),
        setD0Deadline: (value: string) => setField('d0Deadline', value),
        setD1Champion: (value: number | '') => setField('d1Champion', value),
        setD1Leader: (value: number | '') => setField('d1Leader', value),
        setD1Members: (value: number[]) => setField('d1Members', value),
        setD2What: (value: string) => setField('d2What', value),
        setD2Where: (value: string) => setField('d2Where', value),
        setD2When: (value: string) => setField('d2When', value),
        setD2Who: (value: string) => setField('d2Who', value),
        setD2Why: (value: string) => setField('d2Why', value),
        setD2How: (value: string) => setField('d2How', value),
        setD2HowMany: (value: string) => setField('d2HowMany', value),
        setD3Action: (value: string) => setField('d3Action', value),
        setD3EffDate: (value: string) => setField('d3EffDate', value),
        setD3Verif: (value: string) => setField('d3Verif', value),
        setD4Tool: (value: string) => setField('d4Tool', value),
        setD4FiveWhy: (value: { why: string; answer: string }[]) => setField('d4FiveWhy', value),
        setD4Fishbone: (value: Record<string, string[]>) => setField('d4Fishbone', value),
        setD4RootCause: (value: string) => setField('d4RootCause', value),
        setD5Action: (value: string) => setField('d5Action', value),
        setD5PlannedDate: (value: string) => setField('d5PlannedDate', value),
        setD5VerifyPlan: (value: string) => setField('d5VerifyPlan', value),
        setD6ImplDate: (value: string) => setField('d6ImplDate', value),
        setD6Result: (value: string) => setField('d6Result', value),
        setD6Verified: (value: boolean) => setField('d6Verified', value),
        setD8Confirm: (value: string) => setField('d8Confirm', value),
        setD8Recog: (value: string) => setField('d8Recog', value),
    };
};
