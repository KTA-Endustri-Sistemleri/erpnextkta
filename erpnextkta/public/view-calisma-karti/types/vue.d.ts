declare module "vue" {
    // Minimal stubs for Composition API to satisfy TS in this folder.
    export function ref<T = any>(value?: T): any;
    export function computed<T = any>(getter: any): any;
    export function onMounted(fn: any): void;
    export function onUnmounted(fn: any): void;
    export function watch(source: any, cb: any, options?: any): void;

    export type DefineComponent<P = any, S = any, E = any> = any;
}