import { describe, it, expect } from 'vitest';
import { getErrorMessage, applyWorkOrderPrefix, applyJobCardPrefix } from '../utils.js';

// ──────────────────────────────────────────────────────────────────────────────
// getErrorMessage
// ──────────────────────────────────────────────────────────────────────────────
describe('getErrorMessage', () => {
  it('err null ise defaultMsg döner', () => {
    expect(getErrorMessage(null, 'Varsayılan hata')).toBe('Varsayılan hata');
  });

  it('err undefined ise defaultMsg döner', () => {
    expect(getErrorMessage(undefined, 'Hata')).toBe('Hata');
  });

  it('string hata direkt döner', () => {
    expect(getErrorMessage('Bir sorun oluştu', 'Varsayılan')).toBe('Bir sorun oluştu');
  });

  it('err.message kullanılır', () => {
    expect(getErrorMessage({ message: 'Bağlantı hatası' }, 'Varsayılan')).toBe('Bağlantı hatası');
  });

  it('err.statusText kullanılır (message yoksa)', () => {
    expect(getErrorMessage({ statusText: 'Bad Gateway' }, 'Varsayılan')).toBe('Bad Gateway');
  });

  it('_server_messages JSON string parse edilir', () => {
    const err = {
      _server_messages: JSON.stringify([
        JSON.stringify({ message: 'Sunucu hatası' }),
      ]),
    };
    expect(getErrorMessage(err, 'Varsayılan')).toBe('Sunucu hatası');
  });

  it('_server_messages birden fazla mesaj birleştirilir', () => {
    const err = {
      _server_messages: JSON.stringify([
        JSON.stringify({ message: 'Hata 1' }),
        JSON.stringify({ message: 'Hata 2' }),
      ]),
    };
    expect(getErrorMessage(err, 'Varsayılan')).toBe('Hata 1 Hata 2');
  });

  it('_server_messages parse hatasında string olarak döner', () => {
    const err = { _server_messages: 'invalid json{{' };
    const result = getErrorMessage(err, 'Varsayılan');
    expect(typeof result).toBe('string');
  });

  // Türkçe çeviriler
  it('"Work Order xxx not found" → Türkçe mesaja çevrilir', () => {
    expect(getErrorMessage('Work Order MFG-001 not found', 'Hata')).toBe('İş Emri bulunamadı.');
  });

  it('"Job Card xxx not found" → Türkçe mesaja çevrilir', () => {
    expect(getErrorMessage('Job Card JC-001 not found', 'Hata')).toBe('İş Kartı bulunamadı.');
  });

  it('"Employee xxx not found" → Türkçe mesaja çevrilir', () => {
    expect(getErrorMessage('Employee EMP-001 not found', 'Hata')).toBe('Personel kaydı bulunamadı.');
  });

  it('"Operation xxx not found" → Türkçe mesaja çevrilir', () => {
    expect(getErrorMessage('Operation OP-001 not found', 'Hata')).toBe('Operasyon bulunamadı.');
  });

  it('"Not permitted" → Türkçe mesaja çevrilir', () => {
    expect(getErrorMessage('Not permitted', 'Hata')).toBe('Bu işlem için yetkiniz yok.');
  });

  it('"Insufficient Permission" → Türkçe mesaja çevrilir', () => {
    expect(getErrorMessage('Insufficient Permission for action', 'Hata')).toBe('Yetki yetersiz.');
  });

  it('Eşleşmeyen "not found" içeriyorsa defaultMsg döner', () => {
    expect(getErrorMessage('Workstation not found', 'Hata oluştu')).toBe('Hata oluştu');
  });

  it('Traceback içeriyorsa defaultMsg döner', () => {
    const err = { message: 'Traceback (most recent call last): File...' };
    expect(getErrorMessage(err, 'Hata oluştu')).toBe('Hata oluştu');
  });

  it('OperationalError içeriyorsa defaultMsg döner', () => {
    const err = { message: 'OperationalError: no such table' };
    expect(getErrorMessage(err, 'Hata oluştu')).toBe('Hata oluştu');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// applyWorkOrderPrefix
// ──────────────────────────────────────────────────────────────────────────────
describe('applyWorkOrderPrefix', () => {
  it('"2026-01110" → "MFG-WO-2026-01110"', () => {
    expect(applyWorkOrderPrefix('2026-01110')).toBe('MFG-WO-2026-01110');
  });

  it('"2025-99" → "MFG-WO-2025-99"', () => {
    expect(applyWorkOrderPrefix('2025-99')).toBe('MFG-WO-2025-99');
  });

  it('Zaten prefixli ise değişmez', () => {
    expect(applyWorkOrderPrefix('MFG-WO-2026-01110')).toBe('MFG-WO-2026-01110');
  });

  it('Rastgele string değişmez', () => {
    expect(applyWorkOrderPrefix('HELLO')).toBe('HELLO');
  });

  it('Boş string değişmez', () => {
    expect(applyWorkOrderPrefix('')).toBe('');
  });

  it('Sadece yıl formatı değil (2026 tek sayı) değişmez', () => {
    expect(applyWorkOrderPrefix('2026')).toBe('2026');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// applyJobCardPrefix
// ──────────────────────────────────────────────────────────────────────────────
describe('applyJobCardPrefix', () => {
  it('"JOB16115" → "PO-JOB16115"', () => {
    expect(applyJobCardPrefix('JOB16115')).toBe('PO-JOB16115');
  });

  it('Küçük harf "job123" → "PO-JOB123"', () => {
    expect(applyJobCardPrefix('job123')).toBe('PO-JOB123');
  });

  it('Zaten prefixli "PO-JOB123" değişmez', () => {
    expect(applyJobCardPrefix('PO-JOB123')).toBe('PO-JOB123');
  });

  it('"JC-00001" formatı değişmez (JOB ile başlamıyor)', () => {
    expect(applyJobCardPrefix('JC-00001')).toBe('JC-00001');
  });

  it('Boş string değişmez', () => {
    expect(applyJobCardPrefix('')).toBe('');
  });

  it('"JOBXYZ" (sayısal değil) değişmez', () => {
    expect(applyJobCardPrefix('JOBXYZ')).toBe('JOBXYZ');
  });
});
