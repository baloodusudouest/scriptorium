<script>
  // Navigation commune aux applis (0.2.0) : rail à gauche sur PC, pilule d'icônes en bas sur iPhone.
  // Les entrées attendues dans une appli : son écran de travail ou « À traiter » en tuiles,
  // « Connexion » (une tuile par service extérieur) et « Réglages » (ce qui n'est pas un service,
  // la version, la déconnexion). Voir docs/format.md.
  import { onMount } from 'svelte'
  import { fly } from 'svelte/transition'
  import Library from '@lucide/svelte/icons/library'
  import Network from '@lucide/svelte/icons/network'
  import SlidersHorizontal from '@lucide/svelte/icons/sliders-horizontal'
  import { api } from '$lib/api.js'
  import Connexion from './pages/Connexion.svelte'
  import Livres from './pages/Livres.svelte'
  import Livre from './pages/Livre.svelte'
  import Page from './pages/Page.svelte'
  import Services from './pages/Services.svelte'
  import Reglages from './pages/Reglages.svelte'

  // Livres est l'écran de travail ; un livre ouvert (#/livre/12) garde l'onglet Livres allumé.
  const onglets = [
    { page: 'livres', nom: 'Livres', icone: Library },
    { page: 'connexion', nom: 'Connexion', icone: Network },
    { page: 'reglages', nom: 'Réglages', icone: SlidersHorizontal },
  ]

  let connecte = $state(null) // null : on ne sait pas encore
  let session = $state({ version: '', lecture_seule: false })
  let page = $state(lirePage())
  let livreId = $state(lireLivre())
  let pageRang = $state(lireRang())

  function lirePage() {
    const p = location.hash.replace('#/', '').split('/')[0]
    if (p === 'livre') return 'livres'
    return onglets.some((o) => o.page === p) ? p : 'livres'
  }
  function lireLivre() {
    const m = location.hash.match(/^#\/livre\/(\d+)/)
    return m ? Number(m[1]) : null
  }
  function lireRang() {   // #/livre/12/page/40 : relecture d'une page
    const m = location.hash.match(/^#\/livre\/\d+\/page\/(\d+)/)
    return m ? Number(m[1]) : null
  }

  async function verifier() {
    try {
      const s = await api.get('/api/session')
      session = s
      connecte = s.connecte
    } catch {
      connecte = false
    }
  }

  async function deconnecter() {
    try { await api.post('/api/deconnexion') } catch { /* déjà déconnecté */ }
    connecte = false
  }

  onMount(verifier)
</script>

<svelte:window onhashchange={() => { page = lirePage(); livreId = lireLivre(); pageRang = lireRang() }} />

{#if connecte === false}
  <Connexion onconnecte={verifier} />
{:else if connecte}
  <div class="md:pl-52">
    <!-- iPhone : pilule flottante en bas, icônes seules (le nom de la section est le titre de l'écran).
         PC : rail à gauche, avec les noms. Mêmes entrées, même ordre. -->
    <nav
      aria-label="Sections"
      class="fixed bottom-[calc(0.75rem+env(safe-area-inset-bottom))] left-1/2 z-20 flex -translate-x-1/2 items-center gap-1 rounded-full border bg-card/80 p-1.5 shadow-lg backdrop-blur-md
             md:inset-y-0 md:left-0 md:w-52 md:translate-x-0 md:flex-col md:items-stretch md:gap-1 md:rounded-none md:border-0 md:border-r md:bg-transparent md:p-4 md:shadow-none md:backdrop-blur-none"
    >
      <span class="mb-4 hidden px-2 text-xl font-light tracking-tight md:block">Scriptorium</span>
      {#each onglets as o}
        {@const Icone = o.icone}
        <a
          href={'#/' + o.page}
          aria-label={o.nom}
          aria-current={page === o.page ? 'page' : undefined}
          class="flex h-11 items-center gap-2 rounded-full px-4 text-sm font-medium text-muted-foreground transition-colors
                 hover:text-foreground aria-[current=page]:bg-foreground aria-[current=page]:text-background
                 md:h-10 md:rounded-lg md:px-3 md:aria-[current=page]:bg-secondary md:aria-[current=page]:text-foreground"
        >
          <Icone class="size-[1.15rem]" aria-hidden="true" />
          <span class="sr-only md:not-sr-only">{o.nom}</span>
        </a>
      {/each}
    </nav>

    <main
      class="mx-auto max-w-5xl px-[max(1rem,env(safe-area-inset-left))] pt-[calc(1.25rem+env(safe-area-inset-top))] pb-[calc(6rem+env(safe-area-inset-bottom))] md:px-8 md:pt-8 md:pb-10"
    >
      {#if session.lecture_seule}
        <p class="mb-4 rounded-xl border border-primary/50 px-4 py-2 text-sm" role="status">
          Mode lecture seule : l'appli lit tout mais n'écrit nulle part (SCRIPTORIUM_LECTURE_SEULE).
        </p>
      {/if}
      {#key page + (livreId ?? '') + '/' + (pageRang ?? '')}
        <div in:fly={{ y: 6, duration: 180 }}>
          {#if page === 'connexion'}
            <Services ondeconnecte={() => (connecte = false)} />
          {:else if page === 'reglages'}
            <Reglages {session} {deconnecter} />
          {:else if livreId && pageRang}
            <Page id={livreId} rang={pageRang} lectureSeule={session.lecture_seule} ondeconnecte={() => (connecte = false)} />
          {:else if livreId}
            <Livre id={livreId} lectureSeule={session.lecture_seule} ondeconnecte={() => (connecte = false)} />
          {:else}
            <Livres ondeconnecte={() => (connecte = false)} />
          {/if}
        </div>
      {/key}
    </main>
  </div>
{/if}
