// Config mínima: só pega variáveis usadas sem existir (no-undef) e afins.
// Escopo único de propósito — pegar o padrão de bug já visto duas vezes
// nesse projeto (fSt, proc): variável referenciada que nunca foi
// declarada/destruturada naquele escopo.
export default [
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        window: 'readonly', document: 'readonly', localStorage: 'readonly',
        sessionStorage: 'readonly', fetch: 'readonly', crypto: 'readonly',
        console: 'readonly', navigator: 'readonly', location: 'readonly',
        history: 'readonly', alert: 'readonly', confirm: 'readonly',
        prompt: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly',
        setInterval: 'readonly', clearInterval: 'readonly',
        requestAnimationFrame: 'readonly', cancelAnimationFrame: 'readonly',
        FormData: 'readonly', Blob: 'readonly', File: 'readonly',
        FileReader: 'readonly', URL: 'readonly', URLSearchParams: 'readonly',
        XMLHttpRequest: 'readonly', WebSocket: 'readonly', Audio: 'readonly',
        Image: 'readonly', CustomEvent: 'readonly', Event: 'readonly',
        MutationObserver: 'readonly', IntersectionObserver: 'readonly',
        ResizeObserver: 'readonly', Notification: 'readonly',
        TextEncoder: 'readonly', TextDecoder: 'readonly',
        performance: 'readonly', matchMedia: 'readonly', print: 'readonly',
        DOMParser: 'readonly', getComputedStyle: 'readonly',
        structuredClone: 'readonly', Worker: 'readonly', btoa: 'readonly',
        atob: 'readonly', AbortSignal: 'readonly', AbortController: 'readonly',
        Node: 'readonly',
      },
    },
    rules: {
      'no-undef': 'error',
      'no-unused-vars': 'off',
    },
  },
];
