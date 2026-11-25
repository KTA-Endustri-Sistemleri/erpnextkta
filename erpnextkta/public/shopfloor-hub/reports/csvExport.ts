const FORMULA_PREFIX_RE = /^[=+\-@\t\r]/;

export function neutralizeCsvFormula(raw: unknown): string {
  if (raw === null || raw === undefined) return "";
  const text = String(raw);
  if (FORMULA_PREFIX_RE.test(text)) {
    return `'${text}`;
  }
  return text;
}

export function escapeCsvCell(raw: unknown): string {
  const safeText = neutralizeCsvFormula(raw);
  if (/[",\r\n]/.test(safeText)) {
    return `"${safeText.replace(/"/g, '""')}"`;
  }
  return safeText;
}

export function buildCsvContent(headers: string[], rows: unknown[][]): string {
  const lines = [
    headers.map((h) => escapeCsvCell(h)).join(","),
    ...rows.map((row) => row.map((cell) => escapeCsvCell(cell)).join(",")),
  ];
  return `\uFEFF${lines.join("\r\n")}`;
}

export function formatCsvToday(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function exportRowsToCsv(
  filename: string,
  headers: string[],
  rows: unknown[][]
): void {
  const content = buildCsvContent(headers, rows);
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
