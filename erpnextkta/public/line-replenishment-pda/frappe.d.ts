export {};

declare global {
  const frappe: any;
  interface Window {
    frappe: any;
    __: (...args: any[]) => string;
  }
}
