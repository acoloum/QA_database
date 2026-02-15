
const parseSpec = (spec) => {
    if (!spec) return {};

    const parts = spec.replace(/×/g, '*').replace(/x/g, '*').split('*').map(p => parseFloat(p.trim()));
    const result = {};

    console.log("Parts:", parts);

    // Current Logic
    if (parts.length >= 2 && parts[0] && parts[1]) {
        if (parts[1] < parts[0]) {
            console.log("Branch: ID (< OD)");
            if (!isNaN(parts[0])) result['外徑'] = parts[0];
            if (!isNaN(parts[1])) result['內徑'] = parts[1];
            if (!isNaN(parts[2])) result['長度'] = parts[2];
        } else {
            console.log("Branch: Thickness (>= OD)");
            if (!isNaN(parts[0])) result['外徑'] = parts[0];
            if (!isNaN(parts[1])) result['厚度'] = parts[1];
            if (!isNaN(parts[2])) result['長度'] = parts[2];
        }
    }
    return result;
};

const spec = "51*2.5*610";
const result = parseSpec(spec);
console.log("Result:", result);

// Proposed Heuristic Test
const parseSpecImproved = (spec) => {
    if (!spec) return {};
    const parts = spec.replace(/×/g, '*').replace(/x/g, '*').split('*').map(p => parseFloat(p.trim()));
    const result = {};

    if (parts.length >= 2 && parts[0] && parts[1]) {
        // If 2nd part is smaller than half of 1st part, assume Thickness.
        // Else assume ID.
        // Example: 51 * 2.5. 2.5 < 25.5 -> Thickness.
        // Example: 51 * 40. 40 > 25.5 -> ID.
        const likelyThickness = parts[1] < (parts[0] / 2);

        if (likelyThickness) {
            // Thickness
            console.log("Improved: Detected Thickness");
            if (!isNaN(parts[0])) result['外徑'] = parts[0];
            if (!isNaN(parts[1])) result['厚度'] = parts[1];
            if (!isNaN(parts[2])) result['長度'] = parts[2];
        } else {
            // ID
            console.log("Improved: Detected ID");
            if (!isNaN(parts[0])) result['外徑'] = parts[0];
            if (!isNaN(parts[1])) result['內徑'] = parts[1];
            if (!isNaN(parts[2])) result['長度'] = parts[2];
        }
    }
    return result;
}

console.log("Improved Result:", parseSpecImproved(spec));
