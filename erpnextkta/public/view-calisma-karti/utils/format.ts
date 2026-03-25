/**
 * Converts float minutes into HH:MM:SS string format.
 * Example: 1.5 -> "00:01:30"
 * Example: 70 -> "01:10:00"
 */
export function formatDuration(minutes: number | null | undefined): string {
    if (minutes === null || minutes === undefined || isNaN(minutes) || minutes < 0) {
        return "00:00:00";
    }

    const totalSeconds = Math.round(minutes * 60);
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;

    const pad = (n: number) => n.toString().padStart(2, "0");

    return `${pad(h)}:${pad(m)}:${pad(s)}`;
}
