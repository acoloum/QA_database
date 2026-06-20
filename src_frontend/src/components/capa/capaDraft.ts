import type { CAPADetail, CAPASeverity, D7Action } from '../../types';
import { RIGOR_STEPS } from '../../hooks/useCapa';
import { D7_TYPES } from './capaD7Types';

export interface CapaDraftState {
    activeTab: string;
    d0Symptom: string;
    d0Criteria: string[];
    d0Severity: CAPASeverity | '';
    d0Rigor: string;
    d0Deadline: string;
    d1Champion: number | '';
    d1Leader: number | '';
    d1Members: number[];
    d2What: string;
    d2Where: string;
    d2When: string;
    d2Who: string;
    d2Why: string;
    d2How: string;
    d2HowMany: string;
    d3Action: string;
    d3EffDate: string;
    d3Verif: string;
    d4Tool: string;
    d4FiveWhy: { why: string; answer: string }[];
    d4Fishbone: Record<string, string[]>;
    d4RootCause: string;
    d5Action: string;
    d5PlannedDate: string;
    d5VerifyPlan: string;
    d6ImplDate: string;
    d6Result: string;
    d6Verified: boolean;
    d7Actions: D7Action[];
    d8Confirm: string;
    d8Recog: string;
}

export const mergeD7Actions = (serverActions: D7Action[] = []) =>
    D7_TYPES.map(type => {
        const found = serverActions.find(action => action.type === type.key);
        return found ?? {
            type: type.key,
            checked: false,
            assignee_id: null,
            due_date: null,
            description: '',
            part_nos: '',
        };
    });

export const createCapaDraft = (capa: CAPADetail): CapaDraftState => {
    const sourceInfo = (capa.source_info ?? {}) as Record<string, string | number | null>;
    const isNcmr = capa.source_type === 'ncmr';
    const steps = RIGOR_STEPS[capa.rigor] ?? [0, 1, 2, 3, 4, 5, 6, 7, 8];

    return {
        activeTab: `d${steps[0]}`,
        d0Symptom: capa.D0_symptom ?? '',
        d0Criteria: capa.D0_criteria ?? [],
        d0Severity: (capa.D0_severity ?? '') as CAPASeverity | '',
        d0Rigor: capa.rigor ?? '完整8D',
        d0Deadline: capa.D0_deadline ?? '',
        d1Champion: capa.D1_champion_id ?? '',
        d1Leader: capa.D1_leader_id ?? '',
        d1Members: capa.D1_members ?? [],
        d2What: capa.D2_what ?? ((sourceInfo.defect as string) ?? ''),
        d2Where: capa.D2_where ?? (isNcmr ? ((sourceInfo.source as string) ?? '') : ''),
        d2When: capa.D2_when ?? '',
        d2Who: capa.D2_who ?? (isNcmr ? ((sourceInfo.vendor as string) ?? '') : ''),
        d2Why: capa.D2_why ?? '',
        d2How: capa.D2_how ?? (isNcmr ? ((sourceInfo.defect_detail as string) ?? '') : ''),
        d2HowMany: capa.D2_how_many ?? (isNcmr && sourceInfo.defect_qty != null
            ? `${sourceInfo.defect_qty} / ${sourceInfo.total_qty ?? '?'} 支`
            : ''),
        d3Action: capa.D3_action ?? '',
        d3EffDate: capa.D3_effective_date ?? '',
        d3Verif: capa.D3_verification ?? '',
        d4Tool: capa.D4_tool ?? '5why',
        d4FiveWhy: (capa.D4_five_why ?? []) as { why: string; answer: string }[],
        d4Fishbone: (capa.D4_fishbone ?? {}) as Record<string, string[]>,
        d4RootCause: capa.D4_root_cause ?? '',
        d5Action: capa.D5_action ?? '',
        d5PlannedDate: capa.D5_planned_date ?? '',
        d5VerifyPlan: capa.D5_verify_plan ?? '',
        d6ImplDate: capa.D6_implement_date ?? '',
        d6Result: capa.D6_result ?? '',
        d6Verified: capa.D6_verified ?? false,
        d7Actions: mergeD7Actions(capa.D7_actions ?? []),
        d8Confirm: capa.D8_confirmation ?? '',
        d8Recog: capa.D8_recognition ?? '',
    };
};
