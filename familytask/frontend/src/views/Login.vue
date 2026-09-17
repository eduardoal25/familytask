<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')

async function submit() {
  error.value = ''

  if (!email.value.trim() || !password.value) {
    error.value = 'Email et mot de passe requis.'
    return
  }

  try {
    const response = await fetch('/api/members/login?email=' + encodeURIComponent(email.value.trim()) + '&password=' + encodeURIComponent(password.value), {
      method: 'POST'
    })

    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      error.value = data.detail || 'Email ou mot de passe invalide.'
      return
    }

    localStorage.setItem('token', data.token)
    router.push('/tasks')
  } catch (err) {
    error.value = 'Impossible de se connecter.'
  }
}
</script>

<template>
  <main class="auth-wrap">
    <div class="auth-card">
      <h2>Connexion</h2>

      <label>Email</label>
      <input v-model="email" type="email" placeholder="ex: maman@famille.fr" />

      <label>Mot de passe</label>
      <input v-model="password" type="password" placeholder="••••••" @keyup.enter="submit" />

      <button class="primary" @click="submit">Se connecter</button>

      <p v-if="error" class="error">{{ error }}</p>

      <p class="switch">
        Pas encore de compte ?
        <router-link to="/signup">Créer ma famille</router-link>
      </p>
    </div>
  </main>
</template>
