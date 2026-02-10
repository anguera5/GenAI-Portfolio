<template>
  <div class="landing">
    <!-- Header Section (no per-page background) -->
    <section class="hero header-intro">
      <v-container class="hero-content">
        <PageTitle>
          <div>
            <div class="eyebrow">AI Playground</div>
            <h1 class="headline">
              GenAI Portfolio
              <span class="shimmer" />
            </h1>
            <p class="subhead mt-2">
              <span class="typed">{{ typedText }}</span>
              <span class="cursor" :class="{ off: !cursorOn }">|</span>
            </p>
            <div class="cta d-flex ga-3 flex-wrap mt-2">
              <v-btn color="primary" size="large" @click="scrollTo('#modules')">
                Explore modules
                <v-icon class="ml-2" icon="mdi-arrow-right" />
              </v-btn>
              <v-btn size="large" variant="tonal" @click="focusKey = true">
                Enter API key
              </v-btn>
            </div>
          </div>
        </PageTitle>

  <v-expand-transition>
          <div v-show="focusKey" class="key-panel glass mt-4">
            <v-text-field
              v-model="apiKeyStore.apiKey"
              label="OpenAI API Key"
              type="password"
              density="comfortable"
              hide-details
              variant="outlined"
              prepend-inner-icon="mdi-key-outline"
            />
            <div class="tiny-note">
              Your key is used exclusively to call OpenAI: responses with
              <code>gpt-5-mini</code> and embeddings with <code>text-embedding-3-large</code> for RAG.
            </div>
          </div>
        </v-expand-transition>
      </v-container>
    </section>

    <!-- Integration + Trust Section -->
  <section class="integrations mt-4">
      <v-container>
        <v-row align="stretch">
          <v-col cols="12" md="6" class="d-flex">
            <v-card class="glass hover-raise" elevation="2">
              <v-card-item>
                <div class="d-flex align-center ga-3 mb-1">
                  <v-icon color="primary" icon="mdi-rocket-launch-outline" />
                  <div class="text-subtitle-1 font-weight-600">What is this?</div>
                </div>
                <div class="text-body-2 op-80">
                  A collection of mini-apps showcasing practical GenAI patterns: code generation, RAG Q&A,
                  and data exploration. Built with Vue 3 + Vuetify on the frontend and FastAPI on the backend.
                </div>
              </v-card-item>
            </v-card>
          </v-col>
          <v-col cols="12" md="6" class="d-flex">
            <v-card class="glass hover-raise" elevation="2">
              <v-card-item>
                <div class="d-flex align-center ga-3 mb-1">
                  <v-icon color="secondary" icon="mdi-api" />
                  <div class="text-subtitle-1 font-weight-600">Current integration</div>
                </div>
                <div class="text-body-2 op-80">
                  Provider: <strong>OpenAI</strong>
                </div>
                <div class="d-flex ga-2 mt-2 flex-wrap">
                  <v-chip color="primary" variant="tonal" size="small">Model: gpt-5-mini</v-chip>
                  <v-chip color="secondary" variant="tonal" size="small">Embeddings: text-embedding-3-large</v-chip>
                </div>
                <v-divider class="my-3" />
                <div class="text-body-2 op-80">
                  We only use your key to compute responses and to embed your inputs for retrieval-augmented generation. Nothing else.
                </div>
              </v-card-item>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </section>

    <!-- Modules Section -->
  <section id="modules" class="modules mt-2">
      <v-container>
        <h2 class="text-h5 mb-4">Available modules</h2>
        <v-row align="stretch">
          <v-col v-for="m in modules" :key="m.path" cols="12" md="6" lg="4" class="d-flex">
            <v-card :to="m.path" class="module-card hover-raise glass d-flex flex-column h-100" elevation="2">
              <v-img :src="cardThumb(m)" height="140" cover class="module-thumb">
                <template #placeholder>
                  <div class="thumb-ph" />
                </template>
              </v-img>
              <v-card-item>
                <div class="d-flex align-center ga-2">
                  <v-icon icon="mdi-rocket" class="op-80" />
                  <span class="text-subtitle-1 font-weight-600">{{ m.title }}</span>
                </div>
              </v-card-item>
              <v-card-text class="op-80 flex-grow-1">{{ m.description }}</v-card-text>
              <v-card-actions>
                <v-btn color="primary" variant="text" :to="m.path">Open</v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </section>
  </div>
  
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { modules } from '../modules'
import { useApiKeyStore } from '../stores/apiKey'
import PageTitle from '../components/PageTitle.vue'

const apiKeyStore = useApiKeyStore()
const focusKey = ref(false)

// Simple typewriter cycling phrases
const phrases = [
  'Generate clean, documented code in seconds.',
  'Ask domain data with retrieval-augmented answers.',
  'Explore ChEMBL via natural language → SQL.',
  'Review pull requests with LLM assistance.',
]
const typedText = ref('')
const cursorOn = ref(true)
let i = 0, j = 0, forward = true, timer: number | undefined, blinkTimer: number | undefined

function step() {
  const p = phrases[i]
  if (forward) {
    j++
    typedText.value = p.slice(0, j)
    if (j >= p.length) {
      forward = false
      window.setTimeout(step, 1200)
      return
    }
  } else {
    j--
    typedText.value = p.slice(0, j)
    if (j <= 0) {
      forward = true
      i = (i + 1) % phrases.length
    }
  }
  timer = window.setTimeout(step, forward ? 22 : 12) as unknown as number
}

onMounted(() => {
  step()
  blinkTimer = window.setInterval(() => { cursorOn.value = !cursorOn.value }, 500) as unknown as number
})
onBeforeUnmount(() => {
  if (timer) window.clearTimeout(timer)
  if (blinkTimer) window.clearInterval(blinkTimer)
})

function scrollTo(sel: string) {
  const el = document.querySelector(sel)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function cardThumb(m: { title: string }) {
  // SVG gradient placeholder with module title initials
  const title = m.title || 'Module'
  const initials = title.split(/\s+/).map(s => s[0]).slice(0,2).join('').toUpperCase()
  const svg = `
  <svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'>
    <defs>
      <linearGradient id='g' x1='0' x2='1' y1='0' y2='1'>
        <stop offset='0%' stop-color='#9a5fff'/>
        <stop offset='100%' stop-color='#38d6ee'/>
      </linearGradient>
      <filter id='grain'>
        <feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch' />
        <feColorMatrix type='saturate' values='0' />
        <feComponentTransfer>
          <feFuncA type='table' tableValues='0 0.12'/>
        </feComponentTransfer>
      </filter>
    </defs>
    <rect width='100%' height='100%' fill='url(#g)'/>
    <rect width='100%' height='100%' filter='url(#grain)' opacity='0.25'/>
    <circle cx='90' cy='90' r='54' fill='rgba(255,255,255,0.10)'/>
    <text x='90' y='98' text-anchor='middle' font-family='Inter,Arial' font-size='40' fill='white' opacity='0.9'>${initials}</text>
    <text x='24' y='332' font-family='Inter,Arial' font-size='16' fill='rgba(255,255,255,0.85)'>${title}</text>
  </svg>`
  const enc = encodeURIComponent(svg).replace(/'/g, '%27').replace(/\(/g, '%28').replace(/\)/g, '%29')
  return `data:image/svg+xml;charset=utf-8,${enc}`
}
</script>

<style scoped>
.landing { position: relative; }
.op-80 { opacity: 0.8; }
.glass { background: rgba(255,255,255,0.05); backdrop-filter: blur(8px) saturate(160%); border: 1px solid rgba(148,163,184,0.18); }
.hover-raise { transition: transform .2s ease, box-shadow .2s ease; }
.hover-raise:hover { transform: translateY(-2px); box-shadow: 0 10px 26px -10px rgba(0,0,0,.45); }

/* Header */
.hero.header-intro { position: relative; padding: 96px 0 48px; }
.hero .hero-content { position: relative; z-index: 1; max-width: 980px; margin: 0 auto; }
.eyebrow { letter-spacing: 1px; font-size: 0.8rem; text-transform: uppercase; opacity: 0.7; margin-bottom: 8px; }
.headline { font-size: clamp(2.0rem, 6vw, 3.2rem); font-weight: 800; line-height: 1.05; position: relative; }
.headline .shimmer { position:absolute; inset:0; background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,.12), rgba(255,255,255,0)); transform: translateX(-100%); animation: shimmer 5s infinite; pointer-events: none; }
@keyframes shimmer { 0%{ transform: translateX(-100%) } 100%{ transform: translateX(100%) } }
.subhead { font-size: clamp(1rem, 2.8vw, 1.25rem); opacity: .9; margin: 8px 0 18px; min-height: 1.5em; }
.typed { color: #c7d2fe; }
.cursor { display:inline-block; width:1px; background:#c7d2fe; margin-left:2px; animation: pulse 1s infinite; }
.cursor.off { opacity: 0; }
@keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity:.2 } }
.cta .v-btn { text-transform: none; font-weight: 600; }
.key-panel { padding: 12px; border-radius: 12px; }
.tiny-note { font-size: .75rem; opacity: .75; margin-top: 6px; }

/* per-page hero visuals removed in favor of global background */

/* Sections */
.integrations { padding: 20px 0; }
.modules { padding: 20px 0 40px; }
.module-card { width: 100%; }
.module-thumb :deep(img) { filter: saturate(1.1) contrast(1.05); }
.thumb-ph { width: 100%; height: 140px; background: linear-gradient(135deg, rgba(154,95,255,0.25), rgba(56,214,238,0.18)); }
</style>
