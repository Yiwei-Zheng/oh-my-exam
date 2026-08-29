import { createApp } from 'vue'
import 'element-plus/theme-chalk/base.css'
import 'element-plus/theme-chalk/el-alert.css'
import 'element-plus/theme-chalk/el-button.css'
import 'element-plus/theme-chalk/el-empty.css'
import 'element-plus/theme-chalk/el-icon.css'
import 'element-plus/theme-chalk/el-input.css'
import 'element-plus/theme-chalk/el-progress.css'
import 'element-plus/theme-chalk/el-skeleton.css'
import 'element-plus/theme-chalk/el-tree.css'

import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'
import { pinia } from './stores'
import './styles/global.css'

document.documentElement.lang = i18n.global.locale.value

createApp(App).use(pinia).use(i18n).use(router).mount('#app')
