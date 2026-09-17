<script setup>
import { ref, onMounted } from 'vue'

const newTask = ref('')
const tasks = ref([])
const members = ref([])
const status = ref('...')
const memberName = ref('')
const isAdmin = ref(false)
const selectedMemberId = ref('')

async function loadCurrentMember() {
  const token = localStorage.getItem('token')
  if (!token) {
    memberName.value = ''
    isAdmin.value = false
    return
  }

  try {
    const response = await fetch('/api/members/me', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })

    if (!response.ok) {
      throw new Error('Invalid token')
    }

    const data = await response.json()
    memberName.value = data.name || ''
    isAdmin.value = Boolean(data.is_admin)
    selectedMemberId.value = ''
  } catch {
    memberName.value = ''
    isAdmin.value = false
    selectedMemberId.value = ''
  }
}

async function loadMembers() {
  const token = localStorage.getItem('token')
  if (!token) return

  const response = await fetch('/api/members', {
    headers: {
      Authorization: `Bearer ${token}`
    }
  })

  if (!response.ok) {
    throw new Error('Impossible de charger les membres')
  }

  const data = await response.json()
  members.value = data

  if (isAdmin.value) {
    selectedMemberId.value = ''
  } else {
    selectedMemberId.value = String(data.find(member => member.id === Number(localStorage.getItem('memberId')))?.id || data[0]?.id || '')
  }
}

async function loadTasks() {
  const response = await fetch('/api/tasks', {
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token') || ''}`
    }
  })

  if (!response.ok) {
    throw new Error('Impossible de charger les tâches')
  }

  tasks.value = await response.json()
}

async function addTask() {
  const title = newTask.value.trim()
  if (!title) return

  const payload = {
    title,
    done: false,
    ...(isAdmin.value && selectedMemberId.value === 'all' ? { assign_to_all: true } : {}),
    ...(isAdmin.value && selectedMemberId.value && selectedMemberId.value !== 'all' ? { member_id: Number(selectedMemberId.value) } : {})
  }

  const response = await fetch('/api/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('token') || ''}`
    },
    body: JSON.stringify(payload)
  })

  if (!response.ok) {
    throw new Error('Impossible d’ajouter la tâche')
  }

  tasks.value.push(await response.json())
  newTask.value = ''
  if (isAdmin.value) {
    selectedMemberId.value = ''
  }
}

async function toggleDone(task) {
  const response = await fetch(`/api/tasks/${task.id}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('token') || ''}`
    },
    body: JSON.stringify({
      title: task.title,
      done: !task.done
    })
  })

  if (!response.ok) {
    throw new Error('Impossible de mettre à jour la tâche')
  }

  const updatedTask = await response.json()
  tasks.value = tasks.value.map(t => (t.id === updatedTask.id ? updatedTask : t))
}

async function deleteTask(taskId) {
  const response = await fetch(`/api/tasks/${taskId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token') || ''}`
    }
  })

  if (!response.ok) {
    throw new Error('Impossible de supprimer la tâche')
  }

  tasks.value = tasks.value.filter(task => task.id !== taskId)
}

async function logout() {
  const token = localStorage.getItem('token')

  if (token) {
    try {
      await fetch('/api/logout', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        }
      })
    } catch {
      // Ignore server errors: the logout must still work locally.
    }
  }

  localStorage.removeItem('token')
  window.location.href = '/login'
}

onMounted(async () => {
  try {
    const response = await fetch('/api/health')
    status.value = (await response.json()).status
  } catch {
    status.value = 'back pas encore prêt'
  }

  try {
    await loadCurrentMember()
    await loadMembers()
    await loadTasks()
  } catch {
    status.value = 'tâches indisponibles'
  }
})
</script>

<template>
  <main>
    <header class="topbar">
      <h1 class="brand-title" @click="$router.push('/famille')" role="button" tabindex="0" @keydown.enter="$router.push('/famille')" @keydown.space.prevent="$router.push('/famille')">🏠 FamilyTask</h1>
      <div class="user-bar">
        <span>{{ memberName || 'Membre' }}</span>
        <button class="ghost" @click="logout">Se déconnecter</button>
      </div>
    </header>

    <div class="card">
      <p class="hint">Status: {{ status }}</p>

      <h2>Tâches</h2>

      <div class="task-form">
        <input v-model="newTask" type="text" placeholder="Ajouter une tâche" />
        <select v-if="isAdmin" v-model="selectedMemberId">
          <option value="">Pour moi</option>
          <option value="all">Tous les membres</option>
          <option v-for="member in members.filter(m => String(m.id) !== String(currentMemberId))" :key="member.id" :value="String(member.id)">
            {{ member.name }} ({{ member.lien }})
          </option>
        </select>
        <button @click="addTask">Ajouter</button>
      </div>

      <div class="task-table">
        <table>
          <thead>
            <tr>
              <th>Task</th>
              <th>Status</th>
              <th>Check</th>
              <th>Delete</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="task in tasks" :key="task.id">
              <td>{{ task.title }}</td>
              <td>{{ task.done ? '✅ Fait' : '❌ Pas encore' }}</td>
              <td>
                <button class="check-btn" @click="toggleDone(task)">
                  {{ task.done ? 'Non fait' : 'Fait' }}
                </button>
              </td>
              <td>
                <button class="danger-btn" @click="deleteTask(task.id)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>
</template>

<style scoped>
.brand-title {
  cursor: pointer;
  user-select: none;
  transition: opacity 0.2s ease;
}

.brand-title:hover,
.brand-title:focus {
  opacity: 0.85;
  outline: none;
}
</style>
