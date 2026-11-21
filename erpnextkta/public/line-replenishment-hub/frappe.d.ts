export {};

declare global {
  const frappe: any;
  interface Window {
    frappe: any;
    __: (...args: any[]) => string;
  }
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<{}, {}, any>;
  export default component;
}
