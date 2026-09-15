<script setup>
import { ref, onMounted } from 'vue'

const status = ref('...')
const newTask = ref('')
const tasks = ref([])

function addTask() {
  const taskTitle = newTask.value.trim()

  if (!taskTitle) {
    return
  }

  tasks.value.push({
    id: Date.now(),
    taskTitle,
    done: false
  })

  newTask.value = ''
}

function toggleDone(id) {
  tasks.value = tasks.value.map(task =>
    task.id === id ? { ...task, done: !task.done } : task
  )
}

function deleteTask(id) {
  tasks.value = tasks.value.filter(task => task.id !== id)
}

onMounted(async () => {
  try {
    const r = await fetch('/api/health')
    status.value = (await r.json()).status
  } catch (e) {
    status.value = 'back pas encore prêt'
  }

  tasks.value = [
    { id: 1, taskTitle: 'Faire les courses', done: false },
    { id: 2, taskTitle: 'Faire les devoirs', done: true },
    { id: 3, taskTitle: 'Nettoyer la voiture', done: false }
  ]
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
              <td>{{ task.taskTitle }}</td>
              <td>{{ task.done ? '✅ Fait' : '❌ Pas encore' }}</td>
              <td>
                <button @click="toggleDone(task.id)">
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