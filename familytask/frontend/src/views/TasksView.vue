<script setup>
import { ref, onMounted } from 'vue'

const newTask = ref('')
const tasks = ref([])
const status = ref('...')
const memberName = ref('')

async function loadCurrentMember() {
  const token = localStorage.getItem('token')
  if (!token) {
    memberName.value = ''
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
  } catch {
    memberName.value = ''
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

  const response = await fetch('/api/tasks', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('token') || ''}`
    },
    body: JSON.stringify({ title, done: false })
  })

  if (!response.ok) {
    throw new Error('Impossible d’ajouter la tâche')
  }

  tasks.value.push(await response.json())
  newTask.value = ''
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
    await loadTasks()
  } catch {
    status.value = 'tâches indisponibles'
  }
})
</script>

<template>
  <main>
    <header class="topbar">
      <h1>🏠 FamilyTask</h1>
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
