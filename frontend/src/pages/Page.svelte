<script>
  // Relecture d'une page (0.3.0) : l'image à gauche, le texte lu par Mistral à droite (l'un sous l'autre sur iPhone).
  // On peut corriger le texte (il n'est alors plus jamais écrasé par Mistral), faire relire cette page seule,
  // la garder en image dans le livre, ou tourner une photo prise de travers.
  // 0.3.1 : les mots qui diffèrent entre Mistral et Marker (contre-lecture du PC) sont listés au-dessus du texte ;
  // un clic sélectionne le mot dans la zone de texte, « Prendre » met la lecture de Marker à sa place.
  import { onMount } from 'svelte'
  import ArrowLeft from '@lucide/svelte/icons/arrow-left'
  import ChevronLeft from '@lucide/svelte/icons/chevron-left'
  import ChevronRight from '@lucide/svelte/icons/chevron-right'
  import RotateCw from '@lucide/svelte/icons/rotate-cw'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import { Badge } from '$lib/components/ui/badge/index.js'

  let { id, rang, lectureSeule = false, ondeconnecte } = $props()
  let l = $state(null)
  let texte = $state('')
  let original = $state('')
  let erreur = $state('')
  let message = $state('')
  let attente = $state('')
  let version = $state(Date.now())   // change après une rotation : l'image est rechargée
  let marker = $state(null)          // texte lu par Marker (contre-lecture), ou null
  let doutes = $state([])            // [{lu, propose, debut, fin, pris}]
  let pageEntiere = $state(false)
  let zone = $state()                // la zone de texte, pour y sélectionner un mot

  let page = $derived(l?.liste_pages?.find((p) => p.rang === rang))
  let index = $derived(l?.liste_pages?.findIndex((p) => p.rang === rang) ?? -1)
  let precedente = $derived(index > 0 ? l.liste_pages[index - 1] : null)
  let suivante = $derived(index >= 0 && index < (l?.liste_pages?.length ?? 0) - 1 ? l.liste_pages[index + 1] : null)
  let modifie = $derived(texte !== original)
  let enLecture = $derived(page?.lecture === 'attente' && l?.etat === 'lecture' && l?.lecture_demandee)
  let aRelire = $derived(l?.bilan?.contre?.a_relire ?? [])
  let suivanteARelire = $derived.by(() => {
    if (!l || index < 0) return null
    const ordre = l.liste_pages.map((p) => p.rang)
    return aRelire.map((r) => ({ r, i: ordre.indexOf(r) })).filter((x) => x.i > index).sort((a, b) => a.i - b.i)[0]?.r ?? null
  })
  let restants = $derived(doutes.filter((d) => !d.pris))

  async function charger(avecTexte = true) {
    try {
      l = await api.get(`/api/livres/${id}`)
      if (avecTexte) {
        const t = await api.get(`/api/livres/${id}/pages/${rang}/texte`)
        original = texte = t.markdown
        marker = t.marker
        doutes = (t.comparaison?.doutes ?? []).map((d) => ({ ...d, pris: false }))
        pageEntiere = !!t.comparaison?.page_entiere
      }
      erreur = ''
    } catch (err) { if (err.statut === 401) ondeconnecte(); else erreur = err.message }
  }
  onMount(() => {
    charger()
    // Pendant que Mistral relit cette page, on attend son texte
    const t = setInterval(async () => {
      if (!enLecture) return
      await charger(false)
      if (page && page.lecture !== 'attente' && !modifie) await charger(true)
    }, 2500)
    return () => clearInterval(t)
  })

  async function geste(nom, chemin, corps) {
    attente = nom
    message = ''
    try {
      const r = await api.post(chemin, corps)
      if (r?.liste_pages) l = r
      return r ?? true
    } catch (err) {
      if (err.statut === 401) ondeconnecte(); else message = err.message
    } finally { attente = '' }
  }

  async function enregistrer() {
    if (await geste('texte', `/api/livres/${id}/pages/${rang}/texte`, { markdown: texte })) original = texte
  }
  const relire = () => geste('relire', `/api/livres/${id}/pages/${rang}/relire`)
  const rendu = (valeur) => geste('rendu', `/api/livres/${id}/pages/${rang}`, { rendu: valeur })
  async function tourner() {
    if (await geste('tourner', `/api/livres/${id}/pages/${rang}/tourner`)) version = Date.now()
  }

  // Position actuelle d'un mot douteux : là où il était, sinon l'occurrence la plus proche (le texte a pu changer)
  function trouver(d) {
    if (texte.slice(d.debut, d.fin) === d.lu) return d.debut
    let meilleur = -1, i = texte.indexOf(d.lu)
    while (i >= 0) {
      if (meilleur < 0 || Math.abs(i - d.debut) < Math.abs(meilleur - d.debut)) meilleur = i
      i = texte.indexOf(d.lu, i + 1)
    }
    return meilleur
  }
  function voir(d) {
    const pos = trouver(d)
    if (pos < 0 || !zone) return
    zone.focus()
    zone.setSelectionRange(pos, pos + d.lu.length)
    const ligne = parseFloat(getComputedStyle(zone).lineHeight) || 20
    zone.scrollTop = Math.max(0, (texte.slice(0, pos).split('\n').length - 4) * ligne)
  }
  function prendre(d) {
    const pos = trouver(d)
    if (pos < 0) return
    texte = texte.slice(0, pos) + d.propose + texte.slice(pos + d.lu.length)
    const ecart = d.propose.length - d.lu.length
    doutes = doutes.map((x) => (x === d ? { ...x, pris: true } : x.debut > pos ? { ...x, debut: x.debut + ecart, fin: x.fin + ecart } : x))
  }
  const relue = () => geste('relue', `/api/livres/${id}/pages/${rang}/relue`)

  function aller(p) {
    if (!p) return
    if (modifie && !confirm('Le texte corrigé n\'est pas enregistré. Changer de page quand même ?')) return
    location.hash = `#/livre/${id}/page/${p.rang}`
  }
  const allerRang = (r) => aller(l?.liste_pages?.find((p) => p.rang === r))
  const nom = (p) => (p.numero != null ? `Page ${p.numero}` : `Page sans numéro`)
  const etat = { attente: 'pas encore lue', faite: 'lue par Mistral', douteuse: 'lecture douteuse : entre en image', erreur: 'erreur de lecture' }
</script>

<a href={`#/livre/${id}`} class="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
  <ArrowLeft class="size-4" aria-hidden="true" /> {l?.titre ?? 'Livre'}
</a>

{#if erreur}
  <p class="rounded-xl border border-destructive/40 p-4 text-sm text-destructive" role="alert">{erreur}</p>
{:else if !l}
  <p class="text-sm text-muted-foreground">Lecture de la page…</p>
{:else if !page}
  <p class="rounded-xl border p-4 text-sm">Cette page n'existe pas dans ce livre.</p>
{:else}
  <header class="mb-4 flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold">{nom(page)}</h1>
      <p class="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>{page.texte_main ? 'texte corrigé à la main' : etat[page.lecture]}</span>
        {#if page.source === 'photo'}<Badge variant="secondary">reprise à l'iPhone</Badge>{/if}
        {#if page.rendu_choisi === 'image'}<Badge variant="outline">gardée en image</Badge>{/if}
        {#if page.ecartee}<Badge variant="outline">écartée</Badge>{/if}
      </p>
    </div>
    <nav class="flex flex-wrap gap-2" aria-label="Pages voisines">
      {#if suivanteARelire}
        <Button variant="ghost" onclick={() => allerRang(suivanteARelire)}>Page suivante à relire</Button>
      {/if}
      <Button variant="outline" onclick={() => aller(precedente)} disabled={!precedente} aria-label="Page précédente">
        <ChevronLeft class="size-4" aria-hidden="true" /> <span class="hidden sm:inline">{precedente ? nom(precedente) : 'Précédente'}</span>
      </Button>
      <Button variant="outline" onclick={() => aller(suivante)} disabled={!suivante} aria-label="Page suivante">
        <span class="hidden sm:inline">{suivante ? nom(suivante) : 'Suivante'}</span> <ChevronRight class="size-4" aria-hidden="true" />
      </Button>
    </nav>
  </header>

  {#if message}<p class="mb-4 rounded-xl border border-destructive/40 p-3 text-sm text-destructive" role="alert">{message}</p>{/if}

  <div class="grid gap-4 lg:grid-cols-2">
    <figure class="flex flex-col gap-2">
      <a href={`/api/livres/${id}/pages/${rang}.jpg?v=${version}`} target="_blank" rel="noopener" class="block overflow-hidden rounded-xl border bg-white">
        <img src={`/api/livres/${id}/pages/${rang}.jpg?cote=1400&v=${version}`} alt={`Image de la ${nom(page).toLowerCase()}`}
             class="max-h-[78vh] w-full object-contain" />
      </a>
      <figcaption class="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>Rang {page.rang} {page.source === 'photo' ? '(photo ajoutée)' : 'du PDF'}</span>
        {#if (l.couverture ?? l.liste_pages.find((p) => !p.ecartee)?.rang) === rang}
          <span class="text-xs">couverture du livre</span>
        {:else}
          <Button variant="ghost" size="sm" onclick={() => geste('couverture', `/api/livres/${id}/couverture`, { rang })} disabled={attente === 'couverture'}>Prendre comme couverture</Button>
        {/if}
        <Button variant="ghost" size="sm" onclick={tourner} disabled={attente === 'tourner'}>
          <RotateCw class="size-4" aria-hidden="true" /> Tourner
        </Button>
      </figcaption>
    </figure>

    <div class="flex flex-col gap-3">
      <fieldset class="flex rounded-lg border p-1 text-sm" aria-label="Dans le livre">
        <legend class="sr-only">Dans le livre, cette page entre</legend>
        <button type="button" aria-pressed={page.rendu_choisi !== 'image'} onclick={() => rendu('auto')} disabled={attente === 'rendu'}
                class="flex-1 rounded-md px-3 py-1.5 text-muted-foreground aria-pressed:bg-secondary aria-pressed:text-foreground">Recomposer (texte)</button>
        <button type="button" aria-pressed={page.rendu_choisi === 'image'} onclick={() => rendu('image')} disabled={attente === 'rendu'}
                class="flex-1 rounded-md px-3 py-1.5 text-muted-foreground aria-pressed:bg-secondary aria-pressed:text-foreground">Garder en image</button>
      </fieldset>

      {#if marker !== null && !enLecture}
        {#if (doutes.length || pageEntiere) && !page.relue && !page.texte_main}
          <section class="rounded-xl border border-primary/50 p-3" aria-labelledby="titre-doutes">
            <h2 id="titre-doutes" class="text-sm font-semibold text-primary">
              {pageEntiere ? 'Lectures très différentes' : `${restants.length} mot${restants.length > 1 ? 's' : ''} à relire`}
            </h2>
            {#if pageEntiere}
              <p class="mt-1 text-sm text-muted-foreground">Mistral et Marker ne lisent presque pas la même chose : relis la page entière, ou garde-la en image.</p>
            {:else}
              <p class="mt-1 text-sm text-muted-foreground">Mistral et Marker ne lisent pas ces mots de la même façon. Toucher un mot le montre dans le texte.</p>
            {/if}
            <ul class="mt-2 flex max-h-56 flex-col gap-1 overflow-y-auto text-sm">
              {#each doutes as d, i (i)}
                <li class="flex flex-wrap items-center gap-x-2 gap-y-1 {d.pris ? 'opacity-50' : ''}">
                  <button type="button" onclick={() => voir(d)} class="rounded px-1 font-medium underline decoration-primary decoration-2 underline-offset-4 hover:bg-secondary">{d.lu}</button>
                  <span class="text-muted-foreground">Marker lit</span>
                  <span class="font-livre text-base">{d.propose}</span>
                  {#if d.pris}
                    <span class="text-xs text-muted-foreground">remplacé</span>
                  {:else}
                    <Button variant="ghost" size="sm" onclick={() => prendre(d)} aria-label={`Remplacer « ${d.lu} » par « ${d.propose} »`}>Prendre</Button>
                  {/if}
                </li>
              {/each}
            </ul>
            <div class="mt-2 flex flex-wrap items-center gap-2 border-t pt-2">
              <Button size="sm" variant="outline" onclick={relue} disabled={modifie || attente === 'relue'}>Page relue, rien à changer</Button>
              {#if modifie}<span class="text-xs text-muted-foreground">Texte changé : « Enregistrer le texte » vaut relecture.</span>{/if}
            </div>
          </section>
        {:else if page.relue || page.texte_main}
          <p class="text-sm text-muted-foreground">Page relue{doutes.length ? ` (${doutes.length} différence${doutes.length > 1 ? 's' : ''} avec Marker)` : ''}.</p>
        {:else}
          <p class="text-sm text-muted-foreground">Mistral et Marker lisent les mêmes mots sur cette page.</p>
        {/if}
      {/if}

      {#if enLecture}
        <p class="rounded-xl border p-4 text-sm" role="status">Mistral lit cette page… le texte arrivera ici.</p>
      {:else}
        <label class="flex flex-1 flex-col gap-1.5 text-sm">
          <span class="text-muted-foreground">Texte de la page (Markdown : <code># titre</code>, <code>- ingrédient</code>, <code>*italique*</code>)</span>
          <textarea bind:this={zone} bind:value={texte} spellcheck="true" lang="fr"
                    class="min-h-[50vh] flex-1 resize-y rounded-xl border border-input bg-card p-4 font-mono text-sm leading-relaxed outline-none focus:border-ring lg:min-h-[66vh]"
                    placeholder={page.lecture === 'attente' ? 'Pas encore lue : fais-la lire par Mistral, ou tape le texte toi-même.' : ''}></textarea>
        </label>
      {/if}

      <div class="flex flex-wrap items-center gap-2">
        <Button onclick={enregistrer} disabled={!modifie || attente === 'texte'}>{attente === 'texte' ? 'Enregistrement…' : 'Enregistrer le texte'}</Button>
        {#if modifie}<Button variant="ghost" onclick={() => (texte = original)}>Annuler les changements</Button>{/if}
        <Button variant="outline" onclick={relire} disabled={lectureSeule || enLecture || attente === 'relire'}>Faire relire par Mistral</Button>
      </div>
      {#if marker !== null}
        <details class="text-sm">
          <summary class="cursor-pointer text-muted-foreground">Lecture de Marker (contre-lecture du PC)</summary>
          <pre class="mt-2 max-h-80 overflow-auto rounded-xl border bg-card p-3 text-xs whitespace-pre-wrap">{marker}</pre>
        </details>
      {/if}
      <p class="text-sm text-muted-foreground">
        Un texte enregistré ici n'est plus remplacé par Mistral. « Faire relire » l'abandonne et renvoie cette seule page (environ 0,002 $).
      </p>
    </div>
  </div>
{/if}
