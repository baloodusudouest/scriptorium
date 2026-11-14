<script>
  // Un livre : ses trois étapes (Pages, Lecture, Livre).
  // 0.2.2 : la lecture par Mistral peut partir dès la découpe ; elle donne aussi le numéro imprimé de chaque page,
  // qui nourrit l'inventaire. Un EPUB d'essai (pages déjà lues) se fabrique à tout moment ; le dépôt dans
  // Grimmory attend l'inventaire confirmé.
  import { onMount } from 'svelte'
  import ArrowLeft from '@lucide/svelte/icons/arrow-left'
  import Download from '@lucide/svelte/icons/download'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'
  import { Badge } from '$lib/components/ui/badge/index.js'
  import { Progress } from '$lib/components/ui/progress/index.js'

  let { id, lectureSeule = false, ondeconnecte } = $props()
  let l = $state(null)
  let erreur = $state('')
  let message = $state('')
  let attente = $state('')            // geste en cours : 'confirmer', 'lire', 'fabriquer', 'deposer'
  let edition = $state(false)
  let fiche = $state({ titre: '', auteur: '' })
  let numeroEdite = $state(null)      // rang de la page dont on corrige le numéro
  let numeroSaisi = $state('')
  let suppression = $state(false)
  let lienEssai = $state('')

  async function essai() {
    lienEssai = ''
    const r = await geste('essai', `/api/livres/${id}/fabriquer?partiel=true`)
    if (r?.essai) lienEssai = `/api/livres/${id}/telecharger/essai?t=${Date.now()}`
  }

  async function lire() {
    try { l = await api.get(`/api/livres/${id}`); erreur = '' }
    catch (err) { if (err.statut === 401) ondeconnecte(); else erreur = err.message }
  }
  onMount(() => {
    lire()
    const t = setInterval(() => { if (l && (l.etat === 'decoupe' || (l.etat === 'lecture' && l.lecture_demandee))) lire() }, 2500)
    return () => clearInterval(t)
  })

  async function geste(nom, chemin, corps) {
    attente = nom
    message = ''
    try {
      const r = await api.post(chemin, corps)
      if (r?.id) l = r.liste_pages ? r : { ...l, ...r }
      if (!r?.liste_pages) await lire()
      return r
    } catch (err) {
      if (err.statut === 401) ondeconnecte(); else message = err.message
    } finally { attente = '' }
  }

  const modifierPage = (rang, corps) => geste('page', `/api/livres/${id}/pages/${rang}`, corps)
  async function validerNumero(rang) {
    await modifierPage(rang, { numero: numeroSaisi === '' ? null : Number(numeroSaisi) })
    numeroEdite = null
  }
  async function enregistrerFiche(e) {
    e.preventDefault()
    if (await geste('fiche', `/api/livres/${id}/fiche`, fiche)) edition = false
  }
  async function supprimer() {
    if (await geste('supprimer', `/api/livres/${id}/supprimer`)) location.hash = '#/livres'
  }

  // Les pages dans l'ordre du PDF, avec les trous de numérotation montrés à leur place.
  let grille = $derived.by(() => {
    if (!l?.liste_pages) return []
    const items = []
    let dernier = null, sansNumero = 0
    for (const p of l.liste_pages) {
      if (!p.ecartee && p.numero != null) {
        if (dernier != null && p.numero > dernier + 1) {
          const manquent = p.numero - dernier - 1 - sansNumero
          if (sansNumero === 0) items.push({ type: 'trou', de: dernier + 1, a: p.numero - 1 })
          else if (manquent > 0) items.push({ type: 'doute', manquent, entre: [dernier, p.numero] })
        }
        if (dernier == null || p.numero > dernier) { dernier = p.numero; sansNumero = 0 }
      } else if (!p.ecartee) sansNumero++
      items.push({ type: 'page', ...p })
    }
    return items
  })

  const plages = (liste) => {
    if (!liste?.length) return ''
    const out = []
    let debut = liste[0], prec = liste[0]
    for (const n of [...liste.slice(1), null]) {
      if (n === prec + 1) { prec = n; continue }
      out.push(debut === prec ? `${debut}` : `${debut} à ${prec}`)
      debut = prec = n
    }
    return out.join(', ')
  }
  const lectureNom = { attente: 'à lire', faite: 'lue', douteuse: 'en image', erreur: 'erreur' }
</script>

<a href="#/livres" class="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
  <ArrowLeft class="size-4" aria-hidden="true" /> Livres
</a>

{#if erreur}
  <p class="rounded-xl border border-destructive/40 p-4 text-sm text-destructive" role="alert">{erreur}</p>
{:else if !l}
  <p class="text-sm text-muted-foreground">Lecture du livre…</p>
{:else}
  {@const b = l.bilan}
  <header class="mb-6 flow-root max-w-3xl">
    {#if edition}
      <form class="flex flex-col gap-3 rounded-2xl border bg-card p-5" onsubmit={enregistrerFiche} aria-label="Fiche du livre">
        <label class="flex flex-col gap-1.5 text-sm">Titre
          <input bind:value={fiche.titre} required class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" /></label>
        <label class="flex flex-col gap-1.5 text-sm">Auteur
          <input bind:value={fiche.auteur} class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" /></label>
        <div class="flex gap-2"><Button type="submit" disabled={attente === 'fiche'}>Enregistrer la fiche</Button>
          <Button type="button" variant="ghost" onclick={() => (edition = false)}>Annuler</Button></div>
      </form>
    {:else}
      <h1 class="lettrine-titre text-4xl md:text-5xl">{l.titre}</h1>
      <p class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
        {#if l.auteur}<span>{l.auteur}</span>{/if}
        <span>{b.pages} pages dans le PDF</span>
        <button type="button" class="text-sm underline-offset-4 hover:text-foreground hover:underline"
                onclick={() => { fiche = { titre: l.titre, auteur: l.auteur, langue: l.langue }; edition = true }}>Modifier la fiche</button>
      </p>
    {/if}
  </header>

  {#if message}<p class="mb-4 rounded-xl border border-destructive/40 p-3 text-sm text-destructive" role="alert">{message}</p>{/if}

  {#if l.etat === 'envoi'}
    <section class="max-w-xl rounded-2xl border bg-card p-5">
      <h2 class="text-lg font-semibold">Envoi interrompu</h2>
      <p class="mt-1 text-sm text-muted-foreground">Le PDF n'est pas arrivé en entier. Supprime ce livre et relance l'import depuis « Livres ».</p>
    </section>
  {:else if l.etat === 'erreur'}
    <section class="max-w-xl rounded-2xl border border-destructive/40 bg-card p-5" role="alert">
      <h2 class="text-lg font-semibold">Ce PDF n'a pas pu être découpé</h2>
      <p class="mt-1 text-sm text-muted-foreground">{l.erreur}</p>
    </section>
  {:else if l.etat === 'decoupe'}
    <section class="max-w-xl rounded-2xl border bg-card p-5" role="status">
      <h2 class="text-lg font-semibold">{l.relire ? 'Relecture des numéros' : 'Découpe des pages'}</h2>
      <p class="mt-1 text-sm text-muted-foreground">{l.relire ? 'Le numéro imprimé de chaque page est relu.' : 'Chaque page est mise en image et son numéro imprimé est lu.'} Tu peux fermer cette page : le travail continue sur le NAS.</p>
      <div class="mt-3"><Progress value={l.avancement} aria-label="Découpe" /></div>
      <p class="mt-2 text-sm tabular-nums">{l.avancement} %</p>
    </section>
  {:else}
    <!-- Étape 1 : les pages ----------------------------------------------------------- -->
    <section class="mb-8" aria-labelledby="etape-pages">
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="etape-pages" class="text-xl font-semibold">1. Les pages</h2>
        {#if l.inventaire_confirme}<Badge variant="secondary">Inventaire confirmé</Badge>{/if}
      </div>
      <dl class="mb-4 grid max-w-3xl grid-cols-2 gap-3 md:grid-cols-4">
        <div class="rounded-xl border bg-card p-3"><dt class="text-sm text-muted-foreground">Manquantes</dt>
          <dd class="mt-1 font-medium {b.inventaire.manquantes.length ? 'text-primary' : ''}">{plages(b.inventaire.manquantes) || 'aucune'}</dd></div>
        <div class="rounded-xl border bg-card p-3"><dt class="text-sm text-muted-foreground">À vérifier</dt>
          <dd class="mt-1 font-medium">{b.inventaire.a_verifier.length ? b.inventaire.a_verifier.map((v) => `${v.manquent} entre ${v.entre[0]} et ${v.entre[1]}`).join(' ; ') : 'rien'}</dd></div>
        <div class="rounded-xl border bg-card p-3"><dt class="text-sm text-muted-foreground">En double</dt>
          <dd class="mt-1 font-medium">{plages(b.inventaire.doubles) || 'aucune'}</dd></div>
        <div class="rounded-xl border bg-card p-3"><dt class="text-sm text-muted-foreground">Sans numéro lu</dt>
          <dd class="mt-1 font-medium">{b.inventaire.sans_numero.length}</dd></div>
      </dl>
      <p class="mb-4 max-w-3xl text-sm text-muted-foreground">
        Les numéros viennent de Mistral dès qu'une page est lue (avant, d'une lecture locale moins sûre).
        Vérifie avec le sommaire du livre : un numéro faux se corrige d'un clic, une page en double s'écarte.
        Les pages manquantes apparaissent à leur place ; leur reprise à l'iPhone viendra plus tard.
      </p>

      <ul class="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6 xl:grid-cols-8" aria-label="Pages du PDF">
        {#each grille as it (it.type === 'page' ? 'p' + it.rang : it.type + (it.de ?? it.entre?.join('-')))}
          {#if it.type === 'trou'}
            <li class="flex aspect-[3/4] flex-col items-center justify-center rounded-lg border-2 border-dashed border-primary/70 p-2 text-center text-sm text-primary">
              {it.de === it.a ? `Page ${it.de}` : `Pages ${it.de} à ${it.a}`}<span class="text-xs">manquante{it.de === it.a ? '' : 's'}</span>
            </li>
          {:else if it.type === 'doute'}
            <li class="flex aspect-[3/4] flex-col items-center justify-center rounded-lg border-2 border-dashed p-2 text-center text-xs text-muted-foreground">
              {it.manquent} page{it.manquent > 1 ? 's' : ''} manque{it.manquent > 1 ? 'nt' : ''} entre {it.entre[0]} et {it.entre[1]} ?
            </li>
          {:else}
            <li class="flex flex-col gap-1 {it.ecartee ? 'opacity-40' : ''}">
              <a href={`/api/livres/${id}/pages/${it.rang}.jpg`} target="_blank" rel="noopener"
                 class="block overflow-hidden rounded-lg border bg-white {it.numero == null && !it.ecartee ? 'border-dashed border-muted-foreground' : ''}">
                <img src={`/api/livres/${id}/pages/${it.rang}.jpg?cote=260`} alt={`Page ${it.numero ?? 'sans numéro'} (rang ${it.rang} du PDF)`}
                     loading="lazy" class="aspect-[3/4] w-full object-cover object-top" />
              </a>
              <div class="flex items-center justify-between gap-1 text-xs">
                {#if numeroEdite === it.rang}
                  <form class="flex gap-1" onsubmit={(e) => { e.preventDefault(); validerNumero(it.rang) }}>
                    <input bind:value={numeroSaisi} inputmode="numeric" aria-label="Numéro imprimé" class="h-7 w-14 rounded border border-input bg-transparent px-1.5" />
                    <button type="submit" class="rounded px-1.5 text-primary">OK</button>
                  </form>
                {:else}
                  <button type="button" class="rounded px-1 py-0.5 tabular-nums hover:bg-secondary" title="Corriger le numéro"
                          onclick={() => { numeroEdite = it.rang; numeroSaisi = it.numero ?? '' }}>
                    {it.numero ?? '—'}{#if it.numero_manuel}<span class="text-muted-foreground"> (corrigé)</span>{/if}
                  </button>
                  <button type="button" class="rounded px-1 py-0.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
                          onclick={() => modifierPage(it.rang, { ecartee: !it.ecartee })}>{it.ecartee ? 'Remettre' : 'Écarter'}</button>
                {/if}
              </div>
              {#if !it.ecartee && it.lecture !== 'attente'}
                <span class="text-xs {it.lecture === 'erreur' ? 'text-destructive' : 'text-muted-foreground'}" title={it.lecture_erreur}>{lectureNom[it.lecture]}</span>
              {/if}
            </li>
          {/if}
        {/each}
      </ul>

      {#if !l.inventaire_confirme}
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <Button onclick={() => geste('confirmer', `/api/livres/${id}/inventaire/confirmer`)} disabled={attente === 'confirmer'}>Confirmer l'inventaire</Button>
          {#if !b.lecture.faite && !b.lecture.douteuse && !b.lecture.erreur}
            <Button variant="outline" onclick={() => geste('relire', `/api/livres/${id}/numeros/relire`)} disabled={attente === 'relire'}>Relire les numéros</Button>
            <span class="text-sm text-muted-foreground">Les numéros corrigés à la main seront remplacés ; les pages écartées le restent.</span>
          {/if}
        </div>
      {/if}
    </section>

    <!-- Étape 2 : la lecture ---------------------------------------------------------- -->
    <section class="mb-8 max-w-3xl" aria-labelledby="etape-lecture">
      <h2 id="etape-lecture" class="mb-3 text-xl font-semibold">2. La lecture</h2>
      <div class="rounded-2xl border bg-card p-5">
        {#if l.etat === 'lecture' && l.lecture_demandee}
          <p class="text-sm" role="status">Mistral lit les pages : {l.avancement} %. Tu peux fermer cette page.</p>
          <div class="mt-3"><Progress value={l.avancement} aria-label="Lecture" /></div>
        {:else}
          <p class="text-sm text-muted-foreground">
            {b.lecture.faite} lue{b.lecture.faite > 1 ? 's' : ''} · {b.lecture.douteuse} gardée{b.lecture.douteuse > 1 ? 's' : ''} en image · {b.estimation.pages} à lire
            {#if b.facturees} · {b.facturees} page{b.facturees > 1 ? 's' : ''} facturée{b.facturees > 1 ? 's' : ''} par Mistral{/if}
          </p>
          {#if b.lecture.douteuse}
            <p class="mt-2 text-sm text-muted-foreground">Une page que Mistral rend de façon douteuse entre dans le livre en image : le livre reste complet.</p>
          {/if}
          {#if l.erreur}<p class="mt-2 text-sm text-destructive" role="alert">{l.erreur}</p>{/if}
          {#if b.estimation.pages}
            <div class="mt-4 flex flex-wrap items-center gap-3">
              <Button onclick={() => geste('lire', `/api/livres/${id}/lecture`)} disabled={lectureSeule || attente === 'lire'}>
                Faire lire {b.estimation.pages} page{b.estimation.pages > 1 ? 's' : ''} par Mistral
              </Button>
              <span class="text-sm text-muted-foreground">environ {b.estimation.dollars.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} $</span>
              {#if lectureSeule}<Badge variant="outline">lecture seule : rien n'est envoyé</Badge>{/if}
            </div>
          {/if}
        {/if}
      </div>
    </section>

    <!-- Étape 3 : le livre ------------------------------------------------------------ -->
    <section class="mb-10 max-w-3xl" aria-labelledby="etape-livre">
      <h2 id="etape-livre" class="mb-3 text-xl font-semibold">3. Le livre</h2>
      <div class="flex flex-col gap-4 rounded-2xl border bg-card p-5">
        <p class="text-sm text-muted-foreground">
          L'EPUB d'essai ne contient que les pages déjà lues : il sert à voir le rendu, même pendant la lecture.
          Le livre complet reprend toutes les pages (une page pas encore lue y entre en image), avec un PDF d'archive.
        </p>
        {#if lienEssai}<p class="text-sm" role="status">EPUB d'essai prêt : <a class="text-primary underline underline-offset-4" href={lienEssai}>le télécharger</a>.</p>{/if}
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" onclick={essai} disabled={!(b.lecture.faite + b.lecture.douteuse) || attente === 'essai'}>
            {attente === 'essai' ? 'Fabrication…' : `EPUB d'essai (${b.lecture.faite + b.lecture.douteuse} page${b.lecture.faite + b.lecture.douteuse > 1 ? 's' : ''} lue${b.lecture.faite + b.lecture.douteuse > 1 ? 's' : ''})`}
          </Button>
          <Button variant={b.fabrique ? 'outline' : 'default'} onclick={() => geste('fabriquer', `/api/livres/${id}/fabriquer`)}
                  disabled={attente === 'fabriquer' || (l.etat === 'lecture' && l.lecture_demandee)}>
            {attente === 'fabriquer' ? 'Fabrication…' : b.fabrique ? 'Fabriquer à nouveau' : 'Fabriquer le livre'}
          </Button>
          {#if b.fabrique}
            <Button variant="outline" href={`/api/livres/${id}/telecharger/epub`}><Download class="size-4" aria-hidden="true" /> EPUB</Button>
            <Button variant="outline" href={`/api/livres/${id}/telecharger/archive`}><Download class="size-4" aria-hidden="true" /> PDF d'archive</Button>
          {/if}
        </div>
        {#if b.fabrique}
          <div class="flex flex-wrap items-center gap-3 border-t pt-4">
            {#if l.depose_le}
              <p class="text-sm">Déposé dans Grimmory le {new Date(l.depose_le).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' })}.</p>
            {:else}
              <Button onclick={() => geste('deposer', `/api/livres/${id}/deposer`)} disabled={lectureSeule || !l.inventaire_confirme || attente === 'deposer'}>Déposer dans Grimmory</Button>
              <span class="text-sm text-muted-foreground">{l.inventaire_confirme ? 'L\'EPUB seul, pour éviter une seconde fiche du même livre.' : 'Confirme d\'abord l\'inventaire des pages (étape 1).'}</span>
            {/if}
          </div>
        {/if}
      </div>
    </section>
  {/if}

  <footer class="max-w-3xl border-t pt-4">
    {#if suppression}
      <p class="mb-2 text-sm">Le PDF importé, les pages et le texte lu seront effacés du NAS. Un livre déjà déposé reste dans Grimmory.</p>
      <div class="flex gap-2"><Button variant="destructive" onclick={supprimer} disabled={attente === 'supprimer'}>Supprimer ce livre</Button>
        <Button variant="ghost" onclick={() => (suppression = false)}>Garder</Button></div>
    {:else}
      <Button variant="ghost" onclick={() => (suppression = true)}>Supprimer ce livre…</Button>
    {/if}
  </footer>
{/if}
