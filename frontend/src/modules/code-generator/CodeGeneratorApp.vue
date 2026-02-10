<template>
  <v-container class="py-0 animate-in" fluid>
    <div class="section-intro">
      <PageTitle>
        <div class="d-flex flex-column flex-md-row align-center justify-space-between ga-4">
          <div class="flex-1">
            <div class="eyebrow">Generator</div>
            <h1 class="headline">Code Generation <span class="shimmer" /></h1>
            <p class="op-80 mt-1">
              Describe what you need and let the model craft clean, documented code. We call OpenAI’s
              <strong>gpt-5-mini</strong> for code and use <strong>text-embedding-3-large</strong> for RAG in other modules.
            </p>
            <!-- Flow strip below the title for quick mental model -->
            <div class="flow-strip mt-3">
              <div class="step">
                <v-icon icon="mdi-comment-text-outline" size="24" />
                <div class="label">Prompt</div>
              </div>
              <div class="arrow"><v-icon icon="mdi-arrow-right" /></div>
              <div class="step">
                <v-icon icon="mdi-brain" size="24" />
                <div class="label">LLM</div>
              </div>
              <div class="arrow"><v-icon icon="mdi-arrow-right" /></div>
              <div class="step">
                <v-icon icon="mdi-code-tags" size="24" />
                <div class="label">Code</div>
              </div>
              <div class="arrow"><v-icon icon="mdi-arrow-right" /></div>
              <div class="step">
                <v-icon icon="mdi-file-document-outline" size="24" />
                <div class="label">Docs</div>
              </div>
              <div class="arrow"><v-icon icon="mdi-arrow-right" /></div>
              <div class="step">
                <v-icon icon="mdi-clipboard-check-outline" size="24" />
                <div class="label">Tests</div>
              </div>
            </div>
          </div>
          <div class="toolbar d-flex ga-3 align-center flex-wrap">
            <v-select
              v-model="language"
              :items="languages"
              label="Language"
              style="max-width: 220px; min-width: 160px;"
              hide-details
              density="comfortable"
              variant="outlined"
            />
            <v-chip v-if="missingKey" color="warning" variant="tonal" class="pill">Enter API key (top bar)</v-chip>
          </div>
        </div>
      </PageTitle>
    </div>

  <div class="py-6"></div>
    <!-- Knowledge cards: how it works, use-cases, tutorial -->
  <div class="content-wrap">
  <v-row class="mt-6" align="stretch">
      <v-col cols="12" md="4">
        <v-card class="glass-panel hover-raise h-100">
          <v-card-item>
            <div class="d-flex align-center ga-2 mb-1">
              <v-icon color="primary" icon="mdi-transit-connection-variant" />
              <div class="text-subtitle-1 font-weight-600">How it works</div>
            </div>
            <ul class="mini-list op-80">
              <li><span class="num-badge">1</span> You provide a prompt and pick a language.</li>
              <li><span class="num-badge">2</span> The app sends your request to the backend with your API key.</li>
              <li><span class="num-badge">3</span> Backend queries <strong>gpt-5-mini</strong> and returns code.</li>
              <li><span class="num-badge">4</span> Optionally add docs/tests and copy or download.</li>
            </ul>
          </v-card-item>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card class="glass-panel hover-raise h-100">
          <v-card-item>
            <div class="d-flex align-center ga-2 mb-1">
              <v-icon color="secondary" icon="mdi-lightbulb-on-outline" />
              <div class="text-subtitle-1 font-weight-600">Great use-cases</div>
            </div>
            <div class="d-flex flex-wrap ga-2 pt-1">
              <v-chip size="small" variant="tonal" color="primary">Utilities & helpers</v-chip>
              <v-chip size="small" variant="tonal" color="secondary">API clients</v-chip>
              <v-chip size="small" variant="tonal" color="primary">Boilerplate</v-chip>
              <v-chip size="small" variant="tonal" color="secondary">Test skeletons</v-chip>
              <v-chip size="small" variant="tonal" color="primary">Docstrings</v-chip>
              <v-chip size="small" variant="tonal" color="secondary">Small scripts</v-chip>
            </div>
            <div class="op-70 mt-3 small">
              Tip: be specific about inputs, outputs, and edge cases for best results.
            </div>
          </v-card-item>
        </v-card>
      </v-col>
      <v-col cols="12" md="4">
        <v-card class="glass-panel hover-raise h-100">
          <v-card-item>
            <div class="d-flex align-center ga-2 mb-1">
              <v-icon color="primary" icon="mdi-play-circle-outline" />
              <div class="text-subtitle-1 font-weight-600">Quick tutorial</div>
            </div>
            <ol class="mini-steps op-80">
              <li>Choose a language.</li>
              <li>Describe your goal (what, inputs, outputs).</li>
              <li>Click <strong>Generate!</strong></li>
              <li>Use <strong>Add Documentation</strong> and <strong>Add Unit Tests</strong> as needed.</li>
              <li>Copy or download your code.</li>
            </ol>
          </v-card-item>
        </v-card>
      </v-col>
  </v-row>
  <v-row>
      <v-col cols="12" md="6">
        <div class="glass-panel p-4 hover-raise" style="height: 100%">
          <v-textarea
            v-model="prompt"
            label="Describe what to generate"
            auto-grow
            rows="8"
            clearable
          />
          <div class="d-flex mb-6 panel-actions">
            <v-btn class="bg-primary" @click="generate" :loading="loading">Generate!</v-btn>
            <v-btn class="bg-primary" @click="genDocs" :disabled="!codeText" :loading="loadingDocs">Add Documentation</v-btn>
            <v-btn class="bg-primary" @click="genTests" :disabled="!codeText" :loading="loadingTests">Add Unit Tests</v-btn>
          </div>
        </div>
      </v-col>

      <v-col cols="12" md="6">
        <div class="glass-panel p-4 hover-raise" style="height: 100%">
          <div class="mb-2 d-flex align-center justify-space-between">
            <v-tabs v-model="activeTab" density="comfortable" color="primary" bg-color="transparent">
              <v-tab value="code">Code</v-tab>
              <v-tab value="tests">Tests</v-tab>
            </v-tabs>
            <div>
              <v-btn size="small" variant="text" @click="copyCurrent" :disabled="!currentText">Copy</v-btn>
              <v-btn size="small" variant="text" @click="downloadCurrent" :disabled="!currentText">Download</v-btn>
            </div>
          </div>
          <div class="editor">
            <div ref="editorEl" style="height: 520px;"></div>
          </div>
        </div>
      </v-col>
    </v-row>
  </div>


  </v-container>
</template>

<script lang="ts" setup>
import '../../monaco-setup'
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as monaco from 'monaco-editor'
import http from '../../lib/http'
import { useNotifyStore } from '../../stores/notify'
import { useApiKeyStore } from '../../stores/apiKey'
import PageTitle from '../../components/PageTitle.vue'

const prompt = ref('')
const codeText = ref('')
const testsText = ref('')

const languageMap = {
  python: 'py',
  java: 'java',
  javascript: 'js',
  R: 'r',
  matlab: 'm',
  node: 'js'
} as const

type Language = keyof typeof languageMap
const languages = Object.keys(languageMap)
const language = ref<Language>('python')
const apiKeyStore = useApiKeyStore()
const notify = useNotifyStore()
const missingKey = computed(() => !apiKeyStore.apiKey)

let outputLanguage = ''

const activeTab = ref<'code' | 'tests'>('code')

const loading = ref(false)
const loadingTests = ref(false)
const loadingDocs = ref(false)

// Monaco types are accessed via the monaco.editor namespace
let editor: any = null
let codeModel: any = null
let testsModel: any = null
const editorEl = ref<HTMLDivElement | null>(null)

onMounted(() => {
  codeModel = monaco.editor.createModel(codeText.value, language.value)
  testsModel = monaco.editor.createModel(testsText.value, language.value)
  editor = monaco.editor.create(editorEl.value!, {
    model: codeModel,
    theme: 'vs-dark',
    minimap: { enabled: false },
    wordWrap: 'on',
    automaticLayout: true,
    readOnly: true,
  })
  editor.onDidChangeModelContent(() => {
    const m = editor!.getModel()
    if (m === codeModel) codeText.value = m.getValue()
    else if (m === testsModel) testsText.value = m.getValue()
  })
})

watch(codeText, (val) => {
  if (codeModel && val !== codeModel.getValue()) codeModel.setValue(val)
})
watch(testsText, (val) => {
  if (testsModel && val !== testsModel.getValue()) testsModel.setValue(val)
})

watch(language, (lang) => {
  if (codeModel) monaco.editor.setModelLanguage(codeModel, lang)
  if (testsModel) monaco.editor.setModelLanguage(testsModel, lang)
})

watch(activeTab, (tab) => {
  if (!editor) return
  if (tab === 'code' && codeModel) editor.setModel(codeModel)
  if (tab === 'tests' && testsModel) editor.setModel(testsModel)
})

async function generate() {
  loading.value = true
  try {
  const res = await http.post('/api/generate', { prompt: prompt.value, language: language.value , api_key: apiKeyStore.apiKey})
    if (res.data.code === 'Please introduce code-related prompt') {
      notify.warning('The inputted query was not code related according to our model.')
      return
    }
    codeText.value = res.data.code
    activeTab.value = 'code'
    outputLanguage = language.value
  } catch (e: any) {
  // Error popup handled by interceptor; optionally use message locally
  const errorMsg = e?.response?.data?.detail || 'Generation failed'
  } finally {
    loading.value = false
  }
}

async function genTests() {
  loadingTests.value = true
  try {
  const res = await http.post('/api/tests', { code: codeText.value })
    testsText.value = res.data.code
    activeTab.value = 'tests'
  } catch (e) {
    console.error(e)
  } finally {
    loadingTests.value = false
  }
}

async function genDocs() {
  loadingDocs.value = true
  try {
  const res = await http.post('/api/docs', { code: codeText.value })
    codeText.value = res.data.code
    activeTab.value = 'code'
  } catch (e) {
    console.error(e)
  } finally {
    loadingDocs.value = false
  }
}

const currentText = computed(() => (activeTab.value === 'code' ? codeText.value : testsText.value))

async function copyCurrent() {
  if (!currentText.value) return
  await navigator.clipboard.writeText(currentText.value)
}

function downloadCurrent() {
  if (!currentText.value) return
  const blob = new Blob([currentText.value], { type: 'text/plain;charset=utf-8' })
  const a = document.createElement('a')
  const baseExt = languageMap[outputLanguage]
  const suffix = activeTab.value === 'tests' ? '.test' : ''
  const ext = `${suffix}.${baseExt}`
  a.href = URL.createObjectURL(blob)
  a.download = `generated${ext}`
  a.click()
  URL.revokeObjectURL(a.href)
}

onBeforeUnmount(() => {
  editor?.dispose()
  codeModel?.dispose()
  testsModel?.dispose()
})
</script>

<style scoped>
.section-intro { position: relative; padding: 48px 16px 8px; max-width: 1200px; margin: 0 auto; }
.headline { position: relative; font-weight: 800; font-size: clamp(1.8rem, 4.6vw, 2.6rem); line-height: 1.1; }
.headline .shimmer { position:absolute; inset:0; background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.12), rgba(255,255,255,0)); transform: translateX(-100%); animation: shimmer 5s infinite; pointer-events: none; }
@keyframes shimmer { 0%{ transform: translateX(-100%) } 100%{ transform: translateX(100%) } }
.eyebrow { letter-spacing: 1px; font-size: 0.75rem; text-transform: uppercase; opacity: 0.7; }
.toolbar :deep(.v-field) { background: rgba(255,255,255,0.06); }
.op-80 { opacity: .8; }
.op-70 { opacity: .7; }
.small { font-size: .85rem; }
.pill { font-weight: 600; }
.num-badge { display:inline-grid; place-items:center; width: 18px; height: 18px; border-radius: 50%; background: rgba(154,95,255,0.35); color: #fff; font-size: 0.72rem; margin-right: 6px; }
.mini-list { list-style: none; padding-left: 0; }
.mini-list li { margin: 6px 0; }
.panel-actions { display: flex; gap: 8px; }
@media (max-width: 600px) {
  .panel-actions { flex-direction: column; align-items: stretch; }
  .panel-actions > * { width: 100%; }
}
/* Flow strip styles (shared look with ChEMBL module) */
.flow-strip { display:flex; align-items:center; justify-content:center; gap: 10px; max-width: 1200px; margin: 8px auto 4px; padding: 0 8px; }
.flow-strip .step { display:flex; flex-direction:column; align-items:center; gap: 6px; padding: 8px 10px; border-radius: 10px; border: 1px dashed var(--border); background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)); min-width: 90px; }
.flow-strip .label { font-size: 0.8rem; opacity: .9; }
.flow-strip .arrow { opacity: .6; }
@media (max-width: 720px) { .flow-strip { flex-wrap: wrap; row-gap: 6px; } .flow-strip .arrow { display:none; } }
/* Match other modules width */
.content-wrap { max-width: 1200px; margin: 0 auto; padding: 0 8px; }
</style>
