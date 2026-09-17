
<script setup>
import { ref, onMounted } from 'vue'

const memberName = ref('')

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
      throw new Error('Member is not authenticated')
    }

    const data = await response.json()
    memberName.value = data.name || ''
  } catch {
    memberName.value = ''
  }
}

onMounted(() => {
  loadCurrentMember()
})
</script>

<template>
  <header class="topbar">
    <h1>🏠 FamilyTask</h1>
    <div class="user-bar">
      <span>{{ memberName || 'Membre' }}</span>
      <button class="ghost" @click="logout">Se déconnecter</button>
    </div>
  </header>

  <router-view />
</template>