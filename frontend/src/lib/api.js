// Appels à l'API de Scriptorium. Une réponse 401 renvoie à l'écran de connexion.
export class ErreurApi extends Error {
  constructor(message, statut) {
    super(message)
    this.statut = statut
  }
}

async function appel(methode, chemin, corps) {
  const r = await fetch(chemin, {
    method: methode,
    headers: corps ? { 'Content-Type': 'application/json' } : undefined,
    body: corps ? JSON.stringify(corps) : undefined,
    credentials: 'same-origin',
  })
  let donnees = null
  try { donnees = await r.json() } catch { /* réponse sans contenu */ }
  if (!r.ok) throw new ErreurApi(donnees?.detail || `Le serveur a répondu ${r.status}.`, r.status)
  return donnees
}

export const api = {
  get: (chemin) => appel('GET', chemin),
  post: (chemin, corps) => appel('POST', chemin, corps ?? {}),
  put: (chemin, corps) => appel('PUT', chemin, corps ?? {}),
}

// Envoi d'un gros PDF par morceaux de 8 Mo. Le serveur dit combien il a reçu : après une coupure, on
// reprend à cet endroit (un morceau n'est jamais ajouté deux fois). Trois essais par morceau.
const MORCEAU = 8 * 1024 * 1024

export async function envoyerFichier(livreId, fichier, surAvance) {
  let recus = (await api.get(`/api/livres/${livreId}/envoi`)).recus
  let essais = 0
  while (recus < fichier.size) {
    const bout = fichier.slice(recus, Math.min(fichier.size, recus + MORCEAU))
    try {
      const r = await fetch(`/api/livres/${livreId}/envoi?debut=${recus}`, {
        method: 'PUT', body: bout, credentials: 'same-origin', headers: { 'Content-Type': 'application/octet-stream' },
      })
      const d = await r.json().catch(() => ({}))
      if (r.status === 409 && typeof d.recus === 'number') { recus = d.recus; continue }
      if (!r.ok) throw new ErreurApi(d.detail || `Le serveur a répondu ${r.status}.`, r.status)
      recus = d.recus
      essais = 0
      surAvance?.(recus / fichier.size)
    } catch (err) {
      if (err.statut === 401 || ++essais >= 3) throw err
      await new Promise((ok) => setTimeout(ok, 1500 * essais))
      recus = (await api.get(`/api/livres/${livreId}/envoi`)).recus
    }
  }
  return api.post(`/api/livres/${livreId}/envoi/fin`)
}

// Page reprise à l'iPhone : la photo part telle quelle (JPEG ou HEIC), le serveur la redresse et la recadre.
export const envoyerPhoto = (livreId, numero, fichier) => envoyerImage(`/api/livres/${livreId}/pages/ajouter?numero=${numero}`, fichier)

// Envoi d'une photo telle quelle (PUT, corps brut) : page reprise, code-barres de l'ISBN
export async function envoyerImage(chemin, fichier) {
  const r = await fetch(chemin, {
    method: 'PUT', body: fichier, credentials: 'same-origin', headers: { 'Content-Type': 'application/octet-stream' },
  })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new ErreurApi(d.detail || `Le serveur a répondu ${r.status}.`, r.status)
  return d
}
