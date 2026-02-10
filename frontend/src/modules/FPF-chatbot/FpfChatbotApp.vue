<template>
  <v-container class="py-0" fluid>
    <div class="section-intro">
      <PageTitle>
        <div class="d-flex flex-column flex-md-row align-center justify-space-between ga-4">
          <div class="flex-1">
            <div class="eyebrow">Chatbot</div>
            <h1 class="headline">Unofficial Food Packaging Forum Chatbot <span class="shimmer" /></h1>
            <p class="op-80 mt-1">
              Ask questions about food packaging safety. Replies are grounded on FPF content using
              <strong>text-embedding-3-large</strong> and generated with <strong>gpt-5-mini</strong>.
            </p>
            <!-- Flow strip to show the pipeline -->
            <div class="flow-strip mt-3">
              <div class="step">
                <v-icon icon="mdi-comment-question-outline" size="24" />
                <div class="label">Question</div>
              </div>
              <div class="arrow"><v-icon icon="mdi-arrow-right" /></div>
              <div class="step">
                <v-icon icon="mdi-magnify" size="24" />
                <div class="label">Retrieve</div>
              </div>
              <div class="arrow"><v-icon icon="mdi-arrow-right" /></div>
              <div class="step">
                <v-icon icon="mdi-brain" size="24" />
                <div class="label">LLM</div>
              </div>
              <div class="arrow"><v-icon icon="mdi-arrow-right" /></div>
              <div class="step">
                <v-icon icon="mdi-message-text-outline" size="24" />
                <div class="label">Answer</div>
              </div>
            </div>
          </div>
          <div class="toolbar d-flex ga-3 align-center flex-wrap">
            <v-chip v-if="!apiKeyStore.apiKey" color="warning" variant="tonal" class="pill">Enter API key (top bar)</v-chip>
            <v-chip color="secondary" variant="tonal" class="pill">RAG-enabled</v-chip>
          </div>
        </div>
      </PageTitle>
    </div>

  <div class="disclaimer mt-2 mb-2" role="note" aria-label="Disclaimer">
    <v-icon icon="mdi-alert-decagram-outline" size="18" class="mr-2 warn-icon" />
    <div class="disc-text">
      <div class="disc-title">Disclaimer</div>
      <div class="disc-body">
        This content is provided as of 20 August 2025 (“Snapshot Date”). The information
         contained herein may be incomplete, outdated, or inaccurate due to potential limitations of 
         large language models (“LLMs”). Although the content references materials from the Food Packaging 
         Forum (“FPF”), it is provided solely for informational purposes and does not constitute legal advice. 
         Nothing in this application shall be construed as legally binding, nor shall any statements herein be 
         attributed to or deemed to represent the views, opinions, or positions of FPF. No conclusions, 
         decisions, or reliance should be placed on this content in any legal, regulatory, or 
         commercial context.
      </div>
    </div>
  </div>

  <div class="py-6"></div>
  <v-card class="chat-shell mb-4 mt-4" elevation="2">
      <div class="messages" ref="messagesEl">
        <div
          v-for="(m, idx) in messages"
          :key="m.id"
          class="message"
          :class="[m.role, { grouped: idx>0 && messages[idx-1].role === m.role }]"
        >
          <div class="bubble">
            <span class="role" v-if="!(idx>0 && messages[idx-1].role === m.role)">
              {{ m.role === 'assistant' ? 'Assistant' : 'You' }}
            </span>
            <div class="text">{{ m.text }}</div>
          </div>
        </div>
        <div v-if="loading" class="message assistant pending">
          <div class="bubble"><em>Thinking...</em></div>
        </div>
      </div>
      <v-divider />
      <form @submit.prevent="send" class="composer d-flex align-center pa-2 ga-2">
        <div class="input-wrap flex-grow-1">
          <v-textarea
            v-model="draft"
            :label="apiKeyStore.apiKey ? 'Ask something about food packaging safety...' : 'Enter API key (top bar) to chat'"
            auto-grow
            rows="1"
            max-rows="5"
            class="flex-grow-1"
            density="comfortable"
            hide-details
            :disabled="!apiKeyStore.apiKey"
            @keydown="onKeyDown"
          />
          <div v-if="!apiKeyStore.apiKey" class="input-overlay" />
        </div>
        <v-tooltip text="Enter API key in the top bar" v-if="!apiKeyStore.apiKey">
          <template #activator="{ props }">
            <div v-bind="props">
              <SendButton :disabled="true">Send</SendButton>
            </div>
          </template>
        </v-tooltip>
        <SendButton v-else :disabled="!draft.trim() || loading" :loading="loading" type="submit">Send</SendButton>
      </form>
    </v-card>
  </v-container>
</template>

<script lang="ts" setup>
import { ref, nextTick, onMounted } from 'vue'
import http from '../../lib/http'
import { useNotifyStore } from '../../stores/notify'
import { useApiKeyStore } from '../../stores/apiKey'
import PageTitle from '../../components/PageTitle.vue'
import SendButton from '../../components/SendButton.vue'

interface ChatMessage { id: string; role: 'user' | 'assistant'; text: string }

const apiKeyStore = useApiKeyStore()
const notify = useNotifyStore()
const messages = ref<ChatMessage[]>([])
const draft = ref('')
const loading = ref(false)
const messagesEl = ref<HTMLElement | null>(null)
let chatbotConfigKey: string | undefined

function push(role: ChatMessage['role'], text: string) {
  messages.value.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, role, text })
  nextTick(() => {
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  })
}

async function send() {
  const content = draft.value.trim()
  if (!apiKeyStore.apiKey) { notify.warning('Please add your API key (top bar) to start chatting'); return }
  if (!content) return
  push('user', content)
  draft.value = ''
  loading.value = true
  try {
  const res = await http.post('/api/fpf-chatbot/chat', { prompt: content, api_key: apiKeyStore.apiKey, config_key: chatbotConfigKey })
    push('assistant', res.data.reply)
  } catch (e:any) {
    const status = e?.response?.status
    if (status === 401) {
      notify.error('API key is invalid. Please check your key and try again.')
    }
    const msg = e?.response?.data?.detail || 'Error contacting backend'
    push('assistant', msg)
  } finally {
    loading.value = false
  }
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (!loading.value && apiKeyStore.apiKey && draft.value.trim()) send()
  }
}

onMounted(() => {
  if (!messages.value.length) {
    chatbotConfigKey = Math.random().toString(16).slice(2, 18)
    console.log(`Chatbot config key: ${chatbotConfigKey}`)
    push(
      'assistant',
      'Hello, this is the Unofficial Food Packaging Forum chatbot, please ask me anything related to our work and I will happily try to solve your question.'
    )
  }
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
.pill { font-weight: 600; }
.chat-shell { display:flex; flex-direction:column; max-width: 980px; margin: 0 auto; height:70vh; min-height:520px; border-radius: 16px; overflow:hidden; background: linear-gradient(180deg, rgba(23,25,45,0.7), rgba(23,25,45,0.5)); }
.messages { padding: 16px; overflow-y:auto; flex:1; background: radial-gradient(1200px 50% at 50% 0%, rgba(255,255,255,0.02), transparent); }
.message { margin-bottom: 10px; display:flex; }
.message.user { justify-content:flex-end; }
.message.assistant { justify-content:flex-start; }
.bubble { max-width: 72%; padding: 12px 16px; border-radius: 18px; position:relative; background:rgba(154,95,255,0.14); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 10px 22px -14px rgba(0,0,0,.7); }
.message.user .bubble { background: linear-gradient(135deg,#38d6ee44,#9a5fff55); }
.message.grouped .bubble { margin-top: 2px; }
.role { display:inline-block; font-size:0.62rem; opacity:0.7; text-transform:uppercase; margin-bottom:6px; letter-spacing:1px; padding: 2px 6px; border-radius: 999px; background: rgba(255,255,255,0.06); }
.text { white-space:pre-wrap; font-size:0.85rem; line-height:1.3; }
.pending .bubble { opacity:0.6; font-style:italic; }
.composer .v-textarea { flex:1; }
.input-wrap { position: relative; }
.input-overlay { position:absolute; inset:4px 6px; border-radius: 12px; background: repeating-linear-gradient(135deg, rgba(255,255,255,.06) 0 8px, rgba(255,255,255,.04) 8px 16px); pointer-events:none; opacity:.6; }
.send-btn { align-self:flex-end; }
.disclaimer { display:flex; align-items:flex-start; gap:10px; max-width: 980px; margin: 0 auto; padding: 10px 14px; border-radius: 12px; border: 1px solid rgba(250, 204, 21, 0.45); background: linear-gradient(180deg, rgba(250,204,21,0.10), rgba(250,204,21,0.04)); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.04); }
.warn-icon { color: #facc15; flex: 0 0 auto; margin-top: 3px; }
.disc-text { color: #fde68a; }
.disc-title { font-weight: 800; letter-spacing: .3px; text-transform: uppercase; font-size: .78rem; opacity: .95; color: #fde68a; }
.disc-body { font-size: .9rem; opacity: .95; line-height: 1.35; margin-top: 2px; color: #fde68a; }
/* Flow strip styles */
.flow-strip { display:flex; align-items:center; justify-content:center; gap: 10px; max-width: 1200px; margin: 8px auto 4px; padding: 0 8px; }
.flow-strip .step { display:flex; flex-direction:column; align-items:center; gap: 6px; padding: 8px 10px; border-radius: 10px; border: 1px dashed var(--border); background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01)); min-width: 90px; }
.flow-strip .label { font-size: 0.8rem; opacity: .9; }
.flow-strip .arrow { opacity: .6; }
@media (max-width: 720px) { .flow-strip { flex-wrap: wrap; row-gap: 6px; } .flow-strip .arrow { display:none; } }
</style>
