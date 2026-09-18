<script setup>
import { onMounted, ref } from 'vue'

const emit = defineEmits(['refresh-tasks'])

const messages = ref([
  {
    id: 1,
    sender: 'assistant',
    text: 'Bonjour ! Je peux t’aider à gérer les tâches de la famille.'
  }
])
const input = ref('')
const isLoading = ref(false)
const isListening = ref(false)
const errorMessage = ref('')
const speechSupported = ref(false)
const recognitionRef = ref(null)

function getAuthToken() {
  return localStorage.getItem('token') || ''
}

function appendMessage(sender, text) {
  messages.value.push({
    id: Date.now() + Math.random(),
    sender,
    text
  })
}

function scrollToBottom() {
  const container = document.querySelector('.assistant-messages')
  if (container) {
    container.scrollTop = container.scrollHeight
  }
}

onMounted(() => {
  speechSupported.value = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
  scrollToBottom()
})

function handleSpeechResult(event) {
  const transcript = Array.from(event.results)
    .map((result) => result[0]?.transcript || '')
    .join(' ')
    .trim()

  if (transcript) {
    input.value = transcript
  }
}

function toggleListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    speechSupported.value = false
    return
  }

  if (recognitionRef.value) {
    recognitionRef.value.stop()
    recognitionRef.value = null
    isListening.value = false
    return
  }

  const recognition = new SpeechRecognition()
  recognition.lang = 'fr-FR'
  recognition.continuous = false
  recognition.interimResults = false

  recognition.onstart = () => {
    isListening.value = true
  }

  recognition.onend = () => {
    isListening.value = false
    recognitionRef.value = null
  }

  recognition.onerror = () => {
    isListening.value = false
    recognitionRef.value = null
    errorMessage.value = 'La reconnaissance vocale n’est pas disponible pour le moment.'
  }

  recognition.onresult = (event) => {
    handleSpeechResult(event)
  }

  recognitionRef.value = recognition
  recognition.start()
}

async function sendMessage() {
  const message = input.value.trim()
  if (!message || isLoading.value) {
    return
  }

  input.value = ''
  appendMessage('user', message)
  isLoading.value = true
  errorMessage.value = ''

  try {
    const response = await fetch(`/api/assistant?message=${encodeURIComponent(message)}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getAuthToken()}`
      }
    })

    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(data.detail || data.message || 'Erreur du serveur')
    }

    const reply = data.reply || 'Je n’ai pas de réponse pour le moment.'
    appendMessage('assistant', reply)
    emit('refresh-tasks')
  } catch (err) {
    appendMessage('error', err.message || 'Impossible de contacter l’assistant.')
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

function onKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault()
    sendMessage()
  }
}
</script>

<template>
  <div class="assistant-shell">
    <header class="assistant-header">
      <div>
        <p class="eyebrow">Assistant</p>
        <h3>FamilyTask AI</h3>
      </div>
    </header>

    <div class="assistant-messages" aria-live="polite">
      <div
        v-for="message in messages"
        :key="message.id"
        :class="['message-row', message.sender]"
      >
        <div :class="['bubble', message.sender]">
          {{ message.text }}
        </div>
      </div>
    </div>

    <div v-if="errorMessage" class="error-inline">{{ errorMessage }}</div>

    <div class="assistant-compose">
      <input
        v-model="input"
        type="text"
        placeholder="Écris ton message…"
        @keydown="onKeydown"
      />

      <button
        v-if="speechSupported"
        type="button"
        class="mic-btn"
        :class="{ listening: isListening }"
        :disabled="isLoading"
        @click="toggleListening"
        aria-label="Dictée vocale"
      >
        🎤
      </button>

      <button type="button" class="send-btn" :disabled="isLoading || !input.trim()" @click="sendMessage">
        {{ isLoading ? '...' : 'Envoyer' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
:root {
  --assistant-bg: #0b0f13;
  --assistant-panel: #111827;
  --assistant-panel-2: #171f2c;
  --assistant-accent: #2563eb;
  --assistant-accent-soft: rgba(37, 99, 235, 0.18);
  --assistant-text: #F5F5F5;
  --assistant-user: #2d3748;
  --assistant-muted: #cbd5e1;
  --assistant-error: #fca5a5;
  --assistant-border: rgba(148, 163, 184, 0.18);
}

.assistant-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 420px;
  background: var(--assistant-bg);
  color: var(--assistant-text);
  border-radius: 18px;
  overflow: hidden;
}

.assistant-header {
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--assistant-border);
  background: rgba(11, 15, 19, 0.96);
}

.eyebrow {
  margin: 0 0 2px;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--assistant-muted);
}

.assistant-header h3 {
  margin: 0;
  color: var(--assistant-text);
  font-size: 1.1rem;
}

.assistant-messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 12px;
  background: rgba(17, 24, 39, 0.9);
}

.message-row {
  display: flex;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant,
.message-row.error {
  justify-content: flex-start;
}

.bubble {
  max-width: 82%;
  padding: 10px 12px;
  border-radius: 14px;
  line-height: 1.45;
  color: var(--assistant-text);
  word-break: break-word;
}

.bubble.assistant {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
}

.bubble.user {
  background: #2d3748;
}

.bubble.error {
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
  border: 1px solid rgba(239, 68, 68, 0.28);
}

.error-inline {
  margin: 0 12px 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
  font-size: 0.82rem;
}

.assistant-compose {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 12px;
  background: rgba(11, 15, 19, 0.96);
  border-top: 1px solid var(--assistant-border);
}

.assistant-compose input {
  flex: 1;
  height: 42px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(15, 23, 42, 0.7);
  color: var(--assistant-text);
  padding: 0 12px;
  outline: none;
}

.assistant-compose input::placeholder {
  color: var(--assistant-muted);
}

.mic-btn,
.send-btn {
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.mic-btn {
  width: 42px;
  height: 42px;
  background: rgba(37, 99, 235, 0.2);
  color: var(--assistant-text);
}

.mic-btn.listening {
  background: rgba(14, 165, 233, 0.2);
  box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.35);
}

.send-btn {
  min-width: 96px;
  height: 42px;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #f5f5f5;
  font-weight: 700;
}

.send-btn:disabled,
.mic-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
