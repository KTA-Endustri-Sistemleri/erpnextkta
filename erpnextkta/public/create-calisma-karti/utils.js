/**
 * Frappe hata objesinden temiz mesaj ayıran yardımcı
 */
export function getErrorMessage(err, defaultMsg) {
  if (!err) return defaultMsg;
  let rawMsg = '';

  if (typeof err === 'string') {
    rawMsg = err;
  } else if (err._server_messages) {
    try {
      const msgs = typeof err._server_messages === 'string'
        ? JSON.parse(err._server_messages)
        : err._server_messages;
      rawMsg = msgs.map(m => {
        try {
          const p = typeof m === 'string' ? JSON.parse(m) : m;
          return p.message || m;
        } catch { return m; }
      }).join(' ');
    } catch { rawMsg = String(err._server_messages); }
  } else {
    rawMsg = err.message || err.statusText || defaultMsg;
  }

  let cleanMsg = rawMsg;

  const patterns = [
    { reg: /Work Order (.*) not found/i, repl: 'İş Emri bulunamadı.' },
    { reg: /Job Card (.*) not found/i, repl: 'İş Kartı bulunamadı.' },
    { reg: /Employee (.*) not found/i, repl: 'Personel kaydı bulunamadı.' },
    { reg: /Operation (.*) not found/i, repl: 'Operasyon bulunamadı.' },
    { reg: /Not permitted/i, repl: 'Bu işlem için yetkiniz yok.' },
    { reg: /Insufficient Permission/i, repl: 'Yetki yetersiz.' },
  ];

  for (const p of patterns) {
    if (p.reg.test(cleanMsg)) {
      cleanMsg = p.repl;
      break;
    }
  }

  if (cleanMsg.toLowerCase().includes('not found')) {
    return defaultMsg;
  }

  if (cleanMsg.includes('Traceback') || cleanMsg.includes('OperationalError')) {
    return defaultMsg;
  }

  return cleanMsg;
}

/**
 * Work Order barkoduna smart prefix uygular.
 * "2026-01110" -> "MFG-WO-2026-01110"
 */
export function applyWorkOrderPrefix(barcode) {
  if (/^\d{4}-\d+$/.test(barcode)) {
    return `MFG-WO-${barcode}`;
  }
  return barcode;
}

/**
 * Job Card barkoduna smart prefix uygular.
 * "JOB16115" -> "PO-JOB16115"
 */
export function applyJobCardPrefix(barcode) {
  if (/^JOB\d+$/i.test(barcode)) {
    return `PO-${barcode.toUpperCase()}`;
  }
  return barcode;
}
