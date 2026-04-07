import { useState } from 'react'

export interface Favorite {
  type: 'team' | 'player'
  name: string
  addedAt: number
}

const STORAGE_KEY = 'kl_favorites'

function load(): Favorite[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function save(favs: Favorite[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(favs))
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<Favorite[]>(load)

  function toggle(type: 'team' | 'player', name: string) {
    const exists = favorites.some(f => f.type === type && f.name === name)
    const next = exists
      ? favorites.filter(f => !(f.type === type && f.name === name))
      : [...favorites, { type, name, addedAt: Date.now() }]
    save(next)
    setFavorites(next)
  }

  function isFavorite(type: 'team' | 'player', name: string) {
    return favorites.some(f => f.type === type && f.name === name)
  }

  return { favorites, toggle, isFavorite }
}
