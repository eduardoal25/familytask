<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import ChatAssistant from '../components/ChatAssistant.vue'

const router = useRouter()
const { user, isAdmin, refreshUser } = useAuth()

const members = ref([])
const familyTasks = ref([])
const relationOptions = ref([])
const loading = ref(true)
const isFormOpen = ref(false)
const newRelationLabel = ref('')
const error = ref('')
const info = ref('')
const newMember = ref({
  prenom: '',
  lienDeParente: '',
  email: '',
  motDePasse: '',
  isAdmin: false
})

const currentMemberId = computed(() => Number(user.value?.id ?? 0))
const isAssistantOpen = ref(false)

function getAuthHeaders() {
  const token = localStorage.getItem('token') || ''
  return {
    Authorization: `Bearer ${token}`
  }
}

async function requestJson(urls, options = {}) {
  const candidates = Array.isArray(urls) ? urls : [urls]
  let lastError = null

  for (const url of candidates) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...(options.headers || {}),
          ...getAuthHeaders()
        }
      })

      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Erreur API')
      }

      return data
    } catch (err) {
      lastError = err
    }
  }

  throw lastError || new Error('Erreur API')
}

function normalizeMembers(data = []) {
  return data.map((member) => ({
    id: member.id,
    name: member.name || member.prenom || 'Membre',
    lien: member.lien || member.lienDeParente || 'Membre',
    email: member.email || '',
    isAdmin: Boolean(member.is_admin ?? member.isAdmin)
  }))
}

function normalizeTasks(data = [], memberList = []) {
  return data.map((task) => {
    const assignee = memberList.find((member) => Number(member.id) === Number(task.member_id))
    return {
      ...task,
      assigneeName: assignee?.name || 'Membre'
    }
  })
}

async function loadRelations() {
  try {
    const data = await requestJson(['/api/family/relations', '/api/liens'])
    relationOptions.value = Array.isArray(data)
      ? data.map((item) => (typeof item === 'string' ? item : item.label || item.name || '')).filter(Boolean)
      : []
  } catch {
    relationOptions.value = []
  }
}

async function loadMembers() {
  try {
    const data = await requestJson(['/api/family/members', '/api/members'])
    members.value = normalizeMembers(Array.isArray(data) ? data : [])
  } catch (err) {
    error.value = err.message || 'Impossible de charger les membres.'
    members.value = []
  }
}

async function loadTasks() {
  try {
    const data = await requestJson(['/api/family/tasks', '/api/tasks/famille'])
    familyTasks.value = normalizeTasks(Array.isArray(data) ? data : [], members.value)
  } catch (err) {
    familyTasks.value = []
    error.value = err.message || 'Impossible de charger les tâches.'
  }
}

async function loadFamilyData() {
  loading.value = true
  error.value = ''
  try {
    await loadRelations()
    await loadMembers()
    await loadTasks()
  } finally {
    loading.value = false
  }
}

async function addRelation() {
  const label = newRelationLabel.value.trim()
  if (!label) return

  try {
    await requestJson(['/api/family/relations', '/api/liens'], {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ label })
    })

    newRelationLabel.value = ''
    await loadRelations()
  } catch (err) {
    error.value = err.message || 'Impossible d’ajouter ce lien.'
  }
}

async function addMember() {
  const payload = {
    name: newMember.value.prenom.trim(),
    lien: newMember.value.lienDeParente.trim(),
    email: newMember.value.email.trim(),
    password: newMember.value.motDePasse,
    is_admin: Boolean(newMember.value.isAdmin)
  }

  if (!payload.name || !payload.lien || !payload.email || !payload.password) {
    error.value = 'Tous les champs du membre sont requis.'
    return
  }

  try {
    await requestJson(['/api/family/members', '/api/members'], {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })

    info.value = 'Membre ajouté.'
    newMember.value = {
      prenom: '',
      lienDeParente: '',
      email: '',
      motDePasse: '',
      isAdmin: false
    }
    isFormOpen.value = false
    await loadMembers()
    await loadTasks()
  } catch (err) {
    error.value = err.message || 'Impossible d’ajouter le membre.'
  }
}

function explainDeleteError(err) {
  const message = String(err?.message || '').toLowerCase()

  if (message.includes('admin') || message.includes('403')) {
    return 'Suppression refusée : seul un administrateur peut supprimer un membre, et on ne peut pas supprimer son propre compte.'
  }

  if (message.includes('your own') || message.includes('self') || message.includes('soi')) {
    return 'Suppression refusée : vous ne pouvez pas supprimer votre propre compte.'
  }

  if (message.includes('not found') || message.includes('family')) {
    return 'Suppression refusée : ce membre n’existe pas ou n’appartient pas à votre famille.'
  }

  return 'Suppression refusée par l’API. Vérifiez que vous êtes administrateur et que vous n’essayez pas de supprimer votre propre profil.'
}

async function deleteMember(member) {
  if (!member || !member.id) return
  const confirmed = window.confirm(`Supprimer ${member.name} de la famille ?`)
  if (!confirmed) return

  try {
    await requestJson([`/api/family/members/${member.id}`, `/api/members/${member.id}`], {
      method: 'DELETE'
    })
    members.value = members.value.filter((item) => Number(item.id) !== Number(member.id))
    familyTasks.value = familyTasks.value.filter((task) => Number(task.member_id) !== Number(member.id))
    info.value = `${member.name} a bien été supprimé.`
  } catch (err) {
    error.value = explainDeleteError(err)
  }
}

onMounted(async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    router.push('/login')
    return
  }

  await refreshUser()
  if (!isAdmin.value) {
    router.push('/tasks')
    return
  }

  await loadFamilyData()
})

async function refreshAssistantData() {
  await loadTasks()
  await loadFamilyData()
}

function initials(name = 'M') {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('') || 'M'
}
</script>

<template>
  <div class="family-page">
    <header class="family-header">
      <button class="icon-btn back-btn" @click="router.push('/tasks')" aria-label="Retour">←</button>
      <h1>Famille</h1>
      <button class="icon-btn menu-btn" aria-label="Menu">⋯</button>
    </header>

    <button class="assistant-fab" @click="isAssistantOpen = true" aria-label="Ouvrir l’assistant">
      🤖
    </button>

    <div v-if="isAssistantOpen" class="assistant-overlay" @click.self="isAssistantOpen = false">
      <div class="assistant-panel">
        <div class="assistant-panel-header">
          <span>Assistant</span>
          <button class="close-btn" @click="isAssistantOpen = false" aria-label="Fermer">✕</button>
        </div>
        <ChatAssistant @refresh-tasks="refreshAssistantData" />
      </div>
    </div>

    <main class="family-content">
      <section class="panel">
        <div class="panel-header">
          <h2>Membres</h2>
          <button class="primary-btn" @click="isFormOpen = !isFormOpen">+ Ajouter un membre</button>
        </div>

        <div v-if="isFormOpen" class="member-form">
          <div class="field-row">
            <input v-model="newMember.prenom" type="text" placeholder="Prénom" />
            <select v-model="newMember.lienDeParente">
              <option value="">Lien</option>
              <option v-for="relation in relationOptions" :key="relation" :value="relation">
                {{ relation }}
              </option>
            </select>
          </div>

          <div class="field-row relation-inline">
            <input v-model="newRelationLabel" type="text" placeholder="Ajouter un lien" />
            <button class="secondary-btn" @click="addRelation">+ Ajouter un lien</button>
          </div>

          <div class="field-row">
            <input v-model="newMember.email" type="email" placeholder="Email" />
            <input v-model="newMember.motDePasse" type="password" placeholder="Mot de passe" />
          </div>

          <label class="checkbox-row">
            <input v-model="newMember.isAdmin" type="checkbox" />
            <span>Administrateur</span>
          </label>

          <button class="primary-btn submit-btn" @click="addMember">Créer le membre</button>
        </div>

        <p v-if="error" class="error-msg">{{ error }}</p>
        <p v-if="info" class="success-msg">{{ info }}</p>

        <div v-if="loading" class="empty-state">Chargement de la famille…</div>

        <ul v-else class="member-list">
          <li v-for="member in members" :key="member.id" class="member-item">
            <div class="member-main">
              <div class="avatar">{{ initials(member.name) }}</div>
              <div class="member-meta">
                <div class="member-name-line">
                  <span class="member-name">{{ member.name }}</span>
                  <span v-if="Number(member.id) === Number(currentMemberId)" class="self-tag">(moi)</span>
                </div>
                <span class="member-relation">{{ member.lien }}</span>
              </div>
            </div>

            <div class="member-actions">
              <span v-if="member.isAdmin" class="admin-badge">Admin</span>
              <button
                v-if="Number(member.id) !== Number(currentMemberId)"
                class="trash-btn"
                @click="deleteMember(member)"
                aria-label="Supprimer le membre"
              >
                🗑
              </button>
            </div>
          </li>
        </ul>
      </section>

      <section class="panel tasks-panel">
        <h2>Tâches de la famille</h2>
        <div v-if="familyTasks.length === 0" class="empty-state">Aucune tâche pour la famille.</div>
        <ul v-else class="task-list">
          <li v-for="task in familyTasks" :key="task.id" class="task-item">
            <div class="task-avatar">{{ initials(task.assigneeName) }}</div>
            <div class="task-text">
              <strong>{{ task.title }}</strong>
              <span>{{ task.assigneeName }}</span>
            </div>
          </li>
        </ul>
      </section>
    </main>

    <nav class="bottom-nav">
      <router-link to="/tasks" class="nav-item" active-class="active">
        <span>✓</span>
        <span>Tâches</span>
      </router-link>
      <router-link to="/assistant" class="nav-item" active-class="active">
        <span>🤖</span>
        <span>Assistant</span>
      </router-link>
      <router-link v-if="isAdmin" to="/famille" class="nav-item" active-class="active">
        <span>👥</span>
        <span>Famille</span>
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
:root {
  --bg: #0b0f13;
  --panel: #111827;
  --panel-2: #171f2c;
  --text: #F5F5F5;
  --text-secondary: #F5F5F5;
  --divider: rgba(148, 163, 184, 0.18);
  --admin-badge: #2563eb;
  --blue-soft: #1d4ed8;
  --blue-strong: #60a5fa;
}

* {
  box-sizing: border-box;
}

.family-page {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  padding-bottom: 92px;
}

.family-header {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 72px;
  padding: 0 18px;
  background: rgba(11, 15, 19, 0.96);
  border-bottom: 1px solid var(--divider);
  backdrop-filter: blur(8px);
}

.family-header h1 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: whitesmoke
}

.family-content {
  max-width: 720px;
  margin: 0 auto;
  padding: 16px 14px 0;
}

.panel {
  background: rgba(17, 24, 39, 0.94);
  border: 1px solid var(--divider);
  border-radius: 18px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 12px 20px rgba(15, 23, 42, 0.22);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.panel-header h2,
.tasks-panel h2 {
  margin: 0;
  font-size: 1.05rem;
  color: var(--text);
}

.icon-btn,
.primary-btn,
.secondary-btn,
.trash-btn {
  border: none;
  cursor: pointer;
}

.icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.15);
  color: var(--text);
  font-size: 1.2rem;
}

.primary-btn,
.secondary-btn {
  border-radius: 10px;
  padding: 10px 12px;
  font-weight: 600;
}

.primary-btn {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: white;
}

.secondary-btn {
  background: rgba(96, 165, 250, 0.12);
  color: var(--text);
}

.member-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.relation-inline {
  grid-template-columns: 1fr auto;
}

input,
select {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.7);
  color: whitesmoke;
  padding: 10px 12px;
}

input::placeholder,
select {
  color: whitesmoke;
  opacity: 1;
}

.checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: whitesmoke;
  margin-top: 4px;
}

.secondary-btn {
  color: whitesmoke;
}

.submit-btn {
  margin-top: 8px;
}

.member-list,
.task-list {
  list-style: none;
  padding: 0;
  margin: 14px 0 0;
}

.member-item,
.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-top: 1px solid var(--divider);
}

.member-item:first-child,
.task-item:first-child {
  border-top: none;
}

.member-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.avatar,
.task-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1e3a8a, #3b82f6);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.82rem;
  font-weight: 700;
  flex-shrink: 0;
}

.member-meta {
  min-width: 0;
}

.member-name-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.member-name {
  font-weight: 700;
  color: whitesmoke;
}

.member-relation {
  display: block;
  margin-top: 2px;
  font-size: 0.76rem;
  color: whitesmoke;
}

.self-tag {
  color: #bfdbfe;
  font-size: 0.72rem;
}

.member-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-badge {
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--admin-badge);
  color: white;
  font-size: 0.72rem;
  font-weight: 700;
}

.trash-btn {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  font-size: 1rem;
}

.empty-state {
  color: var(--text-secondary);
  padding: 16px 0 8px;
}

.error-msg {
  margin: 10px 0 0;
  color: #fca5a5;
}

.success-msg {
  margin: 10px 0 0;
  color: #bfdbfe;
}

.tasks-panel {
  padding-bottom: 8px;
}

.task-item {
  justify-content: flex-start;
}

.task-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-text strong {
  color: whitesmoke;
}

.task-text span {
  color: whitesmoke;
  font-size: 0.8rem;
}

.assistant-fab {
  position: fixed;
  right: 18px;
  bottom: 82px;
  z-index: 15;
  border: none;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  color: #F5F5F5;
  box-shadow: 0 18px 35px rgba(37, 99, 235, 0.38);
  font-size: 1.5rem;
  cursor: pointer;
}

.assistant-overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  background: rgba(2, 6, 23, 0.48);
  padding: 18px;
}

.assistant-panel {
  width: min(100%, 440px);
  height: min(78vh, 560px);
  background: rgba(11, 15, 19, 0.98);
  border: 1px solid var(--divider);
  border-radius: 22px 22px 18px 18px;
  overflow: hidden;
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.35);
}

.assistant-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--divider);
  background: rgba(17, 24, 39, 0.9);
  color: var(--text);
  font-weight: 700;
}

.close-btn {
  border: none;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.12);
  color: var(--text);
  cursor: pointer;
}

.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  background: rgba(11, 15, 19, 0.98);
  border-top: 1px solid var(--divider);
  backdrop-filter: blur(10px);
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 10px 12px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.72rem;
}

.nav-item.active {
  color: #dbeafe;
  background: rgba(37, 99, 235, 0.14);
}

@media (max-width: 540px) {
  .field-row,
  .relation-inline {
    grid-template-columns: 1fr;
  }

  .panel-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .primary-btn {
    width: 100%;
  }
}
</style>
