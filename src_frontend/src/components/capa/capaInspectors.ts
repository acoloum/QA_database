export interface InspectorItem {
    id: number;
    name: string;
    group: string;
}

export const inspectorLabel = (i: InspectorItem) => i.name;

export const groupInspectors = (list: InspectorItem[]) =>
    list.reduce((acc, i) => {
        const g = i.group || '其他';
        (acc[g] = acc[g] || []).push(i);
        return acc;
    }, {} as Record<string, InspectorItem[]>);
