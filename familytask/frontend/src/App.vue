<script setup>
import { ref, onMounted } from 'vue'

const status = ref('...')
const newTask = ref('')
const tasks = ref([])

async function loadTasks() {
  const response = await fetch('/api/tasks')
  if (!response.ok) {
    throw new Error('Unable to load tasks')
  }
  tasks.value = await response.json()
}

async function addTask() {
  const title = newTask.value.trim()

  if (!title) {
    return
  }

  const response = await fetch('/api/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, done: false })
  })
  if (!response.ok) {
    throw new Error('Unable to create task')
  }

  tasks.value.push(await response.json())
  newTask.value = ''
}

async function toggleDone(task) {
  const response = await fetch(`/api/tasks/${task.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title: task.title,
      done: !task.done
    })
  })
  if (!response.ok) {
    throw new Error('Unable to update task')
  }

  const updatedTask = await response.json()
  tasks.value = tasks.value.map(currentTask =>
    currentTask.id === updatedTask.id ? updatedTask : currentTask
  )
}

async function deleteTask(id) {
  const response = await fetch(`/api/tasks/${id}`, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error('Unable to delete task')
  }

  tasks.value = tasks.value.filter(task => task.id !== id)
}

onMounted(async () => {
  try {
    const r = await fetch('/api/health')
    status.value = (await r.json()).status
  } catch (e) {
    status.value = 'back pas encore prêt'
  }

  try {
    await loadTasks()
  } catch (e) {
    status.value = 'tâches indisponibles'
  }
})
</script>

<template>
  <header><h1>🏠 FamilyTask</h1></header>
  <main>
    <div class="card">
      <h2>Tâches</h2>

      <div class="task-form">
        <input v-model="newTask" type="text" placeholder="Ajouter une tâche" />
        <button @click="addTask">Ajouter</button>
      </div>

      <div class="task-table">
        <table>
          <thead>
            <tr>
              <!--<th>ID</th> -->
              <th>Task</th>
              <th>Status</th>
              <th>Check</th>
              <th>Delete</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="task in tasks" :key="task.id">
              <!--<td>{{ task.id }}</td> -->
              <td>{{ task.title }}</td>
              <td>{{ task.done ? '✅ Fait' : '❌ Pas encore' }}</td>
              <td>
                <button @click="toggleDone(task)">
                  {{ task.done ? 'Non fait' : 'Fait' }}
                </button>
              </td>
              <td>
                <button @click="deleteTask(task.id)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </main>
</template>