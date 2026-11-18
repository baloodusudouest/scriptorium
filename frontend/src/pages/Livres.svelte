<script>
  // « Livres » : la bibliothèque des livres en cours et finis, et l'import d'un PDF déjà scanné.
  // La prise de vue à l'iPhone arrive en 0.4 ; d'ici là, un livre entre par son PDF.
  import { onMount } from 'svelte'
  import Upload from '@lucide/svelte/icons/upload'
  import { api, envoyerFichier } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import { Progress } from '$lib/components/ui/progress/index.js'

  let { ondeconnecte } = $props()
  let livres = $state(null)
  let erreur = $state('')
  let ouvert = $state(false)
  let fichier = $state(null)
  let titre = $state('')
  let auteur = $state('')
  let envoi = $state(null)          // avancement de 0 à 1 pendant l'envoi
  let messageEnvoi = $state('')
  let corbeille = $state([])        // 0.6.7 : livres supprimés, gardés 30 jours
  let messageCorbeille = $state('')

  async function lire() {
    try {
      livres = await api.get('/api/livres'); erreur = ''
      corbeille = await api.get('/api/corbeille')
    }
    catch (err) { if (err.statut === 401) ondeconnecte(); else erreur = err.message }
  }

  async function restaurer(l) {
    messageCorbeille = ''
    try { await api.post(`/api/livres/${l.id}/restaurer`); await lire() }
    catch (err) { messageCorbeille = err.message }
  }
  const jour = (d) => new Date(`${d}T12:00:00`).toLocaleDateString('fr-FR', { dateStyle: 'long' })

  onMount(() => {
    lire()
    const id = setInterval(() => { if (livres?.some((l) => ['decoupe', 'lecture'].includes(l.etat))) lire() }, 4000)
    return () => clearInterval(id)
  })

  function choisir(e) {
    fichier = e.currentTarget.files?.[0] ?? null
    if (fichier && !titre) titre = fichier.name.replace(/\.pdf$/i, '').replace(/[_-]+/g, ' ').trim()
  }

  async function importer(e) {
    e.preventDefault()
    if (!fichier) return
    messageEnvoi = ''
    envoi = 0
    try {
      const livre = await api.post('/api/livres', { titre, auteur, nom_fichier: fichier.name, octets: fichier.size })
      await envoyerFichier(livre.id, fichier, (a) => (envoi = a))
      location.hash = `#/livre/${livre.id}`
    } catch (err) {
      messageEnvoi = err.statut === 401 ? 'Session expirée : reconnecte-toi puis relance l\'envoi.' : err.message
      envoi = null
    }
  }

  const mo = (o) => Math.round(o / 1e6).toLocaleString('fr-FR')
  function resume(l) {
    const b = l.bilan
    if (l.etat === 'envoi') return 'Envoi du PDF interrompu'
    if (l.etat === 'decoupe') return `Découpe des pages : ${l.avancement} %`
    if (l.etat === 'erreur') return l.erreur
    if (l.etat === 'inventaire') {
      const m = b.inventaire.manquantes.length
      return `${b.gardees} pages · ${m ? `${m} manquante${m > 1 ? 's' : ''}` : 'aucune page manquante repérée'}`
    }
    if (l.etat === 'lecture') return l.lecture_demandee ? `Lecture : ${l.avancement} %` : (l.erreur || `${b.estimation.pages} pages à lire`)
    if (l.depose_le) return 'Déposé dans Grimmory'
    if (b.fabrique) return 'Livre fabriqué'
    return 'Prêt à fabriquer'
  }
</script>

<header class="mb-6 flex flex-wrap items-end justify-between gap-3">
  <h1 class="titre">Livres</h1>
  {#if !ouvert}<Button onclick={() => (ouvert = true)}><Upload class="size-4" aria-hidden="true" /> Importer un PDF</Button>{/if}
</header>

{#if ouvert}
  <form class="mb-8 max-w-xl rounded-2xl border bg-card p-5" onsubmit={importer} aria-label="Importer un livre déjà scanné">
    <h2 class="text-lg font-semibold">Importer un livre déjà scanné</h2>
    <p class="mt-1 text-sm text-muted-foreground">Le PDF part par morceaux : un gros fichier passe, et un envoi coupé reprend où il s'était arrêté.</p>
    <div class="mt-4 flex flex-col gap-3">
      <label class="flex flex-col gap-1.5 text-sm">
        PDF du livre
        <input type="file" accept="application/pdf,.pdf" onchange={choisir} required disabled={envoi !== null}
               class="text-sm file:mr-3 file:rounded-lg file:border file:border-input file:bg-secondary file:px-3 file:py-1.5 file:text-foreground" />
      </label>
      {#if fichier}<p class="text-sm text-muted-foreground">{fichier.name} · {mo(fichier.size)} Mo</p>{/if}
      <label class="flex flex-col gap-1.5 text-sm">
        Titre
        <input bind:value={titre} required disabled={envoi !== null}
               class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" />
      </label>
      <label class="flex flex-col gap-1.5 text-sm">
        Auteur
        <input bind:value={auteur} disabled={envoi !== null}
               class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" />
      </label>
      {#if envoi !== null}
        <div class="flex flex-col gap-1.5" role="status">
          <Progress value={Math.round(envoi * 100)} aria-label="Envoi du PDF" />
          <p class="text-sm text-muted-foreground">Envoi : {Math.round(envoi * 100)} % — garde cette page ouverte.</p>
        </div>
      {/if}
      {#if messageEnvoi}<p class="text-sm text-destructive" role="alert">{messageEnvoi}</p>{/if}
      <div class="flex gap-2">
        <Button type="submit" disabled={!fichier || envoi !== null}>Importer</Button>
        <Button type="button" variant="ghost" disabled={envoi !== null} onclick={() => { ouvert = false; fichier = null; titre = ''; auteur = '' }}>Annuler</Button>
      </div>
    </div>
  </form>
{/if}

{#if erreur}
  <p class="rounded-xl border border-destructive/40 p-4 text-sm text-destructive" role="alert">Lecture impossible : {erreur}</p>
{:else if !livres}
  <p class="text-sm text-muted-foreground">Lecture des livres…</p>
{:else if !livres.length && !ouvert}
  <div class="max-w-md rounded-2xl border border-dashed p-6">
    <p class="lettrine-titre text-2xl">Aucun livre pour l'instant.</p>
    <p class="mt-3 text-sm text-muted-foreground">Importe le PDF d'un livre déjà scanné : Scriptorium repère les pages qui manquent, fait lire le texte, puis fabrique l'EPUB.</p>
  </div>
{:else}
  <ul class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Livres">
    {#each livres as l (l.id)}
      <li>
        <a href={`#/livre/${l.id}`}
           class="flex h-full flex-col gap-3 rounded-2xl border bg-card p-5 transition-colors hover:border-primary focus-visible:border-primary">
          <span class="lettrine-titre flow-root text-2xl">{l.titre}</span>
          {#if l.auteur}<span class="text-sm text-muted-foreground">{l.auteur}</span>{/if}
          <span class="mt-auto text-sm {l.etat === 'erreur' ? 'text-destructive' : 'text-muted-foreground'}">{resume(l)}</span>
          {#if ['decoupe', 'lecture'].includes(l.etat) && (l.etat === 'decoupe' || l.lecture_demandee)}
            <Progress value={l.avancement} aria-label="Avancement" />
          {/if}
        </a>
      </li>
    {/each}
  </ul>
{/if}

{#if corbeille.length}
  <section class="mt-10 max-w-xl" aria-label="Corbeille">
    <h2 class="text-lg font-semibold">Corbeille</h2>
    <p class="mt-1 text-sm text-muted-foreground">Un livre supprimé reste ici 30 jours, avec son PDF, ses pages et son texte, puis il est effacé du NAS.</p>
    <ul class="mt-3 grid gap-2">
      {#each corbeille as l (l.id)}
        <li class="flex flex-wrap items-center justify-between gap-2 rounded-xl border p-3 text-sm">
          <span class="min-w-0 break-words">
            <span class="font-medium">{l.titre}</span>
            {#if l.efface_le}<br /><span class="text-muted-foreground">Effacé le {jour(l.efface_le)}</span>{/if}
          </span>
          <Button variant="outline" size="sm" onclick={() => restaurer(l)}>Restaurer</Button>
        </li>
      {/each}
    </ul>
    {#if messageCorbeille}<p class="mt-2 text-sm text-destructive" role="alert">{messageCorbeille}</p>{/if}
  </section>
{/if}
