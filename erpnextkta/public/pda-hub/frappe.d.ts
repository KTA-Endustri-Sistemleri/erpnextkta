export {};

declare global {
  const frappe: any;
  interface Window {
    frappe: any;
    __: (...args: any[]) => string;
    csrf_token?: string;
    build_version?: string;
    __KTA_PDA_BOOT__?: any;
  }
}
