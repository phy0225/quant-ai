import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin, type VueQueryPluginOptions } from '@tanstack/vue-query'
import router from './router'
import App from './App.vue'

import './styles/global.css'

const app = createApp(App)

// Pinia 状态管理
app.use(createPinia())

// Vue Router
app.use(router)

// TanStack Vue Query
const vueQueryOptions: VueQueryPluginOptions = {
  queryClientConfig: {
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: 2,
        refetchOnWindowFocus: false,
      },
    },
  },
}
app.use(VueQueryPlugin, vueQueryOptions)

app.mount('#app')
