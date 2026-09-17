import { computed, ref } from 'vue'

const user = ref(null)

function getToken() {
  return localStorage.getItem('token') || ''
}

async function refreshUser() {
  const token = getToken()
  if (!token) {
    user.value = null
    return null
  }

  try {
    const response = await fetch('/api/members/me', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })

    if (!response.ok) {
      user.value = null
      return null
    }

    const data = await response.json()
    user.value = data
    return data
  } catch {
    user.value = null
    return null
  }
}

export function useAuth() {
  return {
    user,
    isAdmin: computed(() => Boolean(user.value?.is_admin || user.value?.isAdmin)),
    refreshUser
  }
}
