<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const familyName = ref('')
const name = ref('')
const lien = ref('parent')
const email = ref('')
const password = ref('')
const error = ref('')

const liens = ['parent', 'mère', 'père', 'fille', 'fils', 'frère', 'sœur', 'grand-mère', 'grand-père']

async function submit() {
  error.value = ''

  if (!familyName.value.trim() || !name.value.trim() || !email.value.trim() || !password.value) {
    error.value = 'Tous les champs sont requis.'
    return
  }

  try {
    const response = await fetch('/api/members/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: email.value.trim(),
        lien: lien.value,
        name: name.value.trim(),
        is_admin: true,
        family_code: familyName.value.trim(),
        password: password.value
      })
    })

    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      error.value = data.detail || 'Impossible de créer la famille.'
      return
    }

    localStorage.setItem('token', data.token)
    router.push('/tasks')
  } catch (err) {
    error.value = 'Impossible de créer la famille.'
  }
}
</script>

<template>
  <main class="auth-wrap">
    <div class="auth-card">
      <h2>Créer ma famille</h2>

      <label>Nom de la famille</label>
      <input v-model="familyName" placeholder="ex: Durand" />

      <label>Prénom</label>
      <input v-model="name" placeholder="ex: Maman" />

      <label>Lien de parenté</label>
      <select v-model="lien">
        <option v-for="item in liens" :key="item" :value="item">{{ item }}</option>
      </select>

      <label>Email</label>
      <input v-model="email" type="email" placeholder="ex: maman@famille.fr" />

      <label>Mot de passe</label>
      <input v-model="password" type="password" placeholder="••••••" @keyup.enter="submit" />

      <button class="primary" @click="submit">Créer</button>

      <p v-if="error" class="error">{{ error }}</p>

      <p class="switch">
        Déjà un compte ?
        <router-link to="/login">Se connecter</router-link>
      </p>
    </div>
  </main>
</template>
