<script>
  // Un livre : ses trois étapes (Pages, Lecture, Livre).
  // 0.2.2 : la lecture par Mistral peut partir dès la découpe ; elle donne aussi le numéro imprimé de chaque page,
  // qui nourrit l'inventaire. Un EPUB d'essai (pages déjà lues) se fabrique à tout moment ; le dépôt dans
  // Grimmory attend l'inventaire confirmé.
  // 0.3.0 : une page manquante se reprend à l'iPhone (« Prendre ») ; un clic sur une page ouvre sa relecture.
  import { onMount } from 'svelte'
  import ArrowLeft from '@lucide/svelte/icons/arrow-left'
  import Download from '@lucide/svelte/icons/download'
  import Camera from '@lucide/svelte/icons/camera'
  import Pencil from '@lucide/svelte/icons/pencil'
  import { api, envoyerPhoto, envoyerImage } from '$lib/api.js'
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
  let aRelire = $derived(new Set(l?.bilan?.contre?.a_relire ?? []))
  let numeroReprise = $state('')      // reprise d'une page dont le trou n'est pas montré (fin du livre, doute)
  let photoInput                      // champ fichier caché : ouvre l'appareil photo sur iPhone
  let photoNumero = null

  // « Prendre » : ouvre l'appareil photo (ou le choix d'un fichier sur PC), puis envoie la photo avec son numéro.
  function prendre(numero) {
    photoNumero = Number(numero)
    if (!photoNumero) return
    photoInput.value = ''
    photoInput.click()
  }
  async function photoChoisie() {
    const fichier = photoInput.files?.[0]
    if (!fichier || !photoNumero) return
    attente = 'photo'
    message = ''
    try {
      const r = await envoyerPhoto(id, photoNumero, fichier)
      l = r
      numeroReprise = ''
    } catch (err) {
      if (err.statut === 401) ondeconnecte(); else message = err.message
    } finally { attente = '' }
  }

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
    const t = setInterval(() => { if (l && (l.etat === 'decoupe' || (l.etat === 'lecture' && l.lecture_demandee) || l.pdf_demande)) lire() }, 2500)
    // Pendant la contre-lecture par le PC (lente : 10 à 20 s par page), un coup d'œil toutes les 20 s suffit
    const c = setInterval(() => { const k = l?.bilan?.contre; if (k?.pc && k.attente + k.calcul > 0) lire() }, 20000)
    return () => { clearInterval(t); clearInterval(c) }
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

  // 0.6.6 : plafond de dépense par livre (Réglages) : au-delà, le serveur répond 402 avec le montant ; on demande
  let plafond = $state('')
  async function faireLire(depasser = false) {
    attente = 'lire'
    message = ''
    try {
      const r = await api.post(`/api/livres/${id}/lecture`, depasser ? { depasser: true } : {})
      if (r?.id) l = r.liste_pages ? r : { ...l, ...r }
      plafond = ''
      await lire()
    } catch (err) {
      if (err.statut === 401) ondeconnecte(); else if (err.statut === 402) plafond = err.message; else message = err.message
    } finally { attente = '' }
  }
  const euros = (x) => x.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  const modifierPage = (rang, corps) => geste('page', `/api/livres/${id}/pages/${rang}`, corps)
  async function validerNumero(rang) {
    await modifierPage(rang, { numero: numeroSaisi === '' ? null : Number(numeroSaisi) })
    numeroEdite = null
  }
  // Fiche par l'ISBN (0.4.0) : la BnF, puis Open Library, proposent ; rien n'est enregistré sans « Reprendre »
  let proposition = $state(null)
  async function chercherNotice() {
    proposition = null
    const r = await geste('notice', `/api/livres/${id}/notice`, fiche.isbn ? { isbn: fiche.isbn } : {})
    if (r) proposition = r
  }
  // Code-barres (0.4.3) : photo du dos du livre, lue sur le NAS ; l'ISBN trouvé remplit le champ puis la fiche est cherchée
  let codeInput
  async function codeChoisi() {
    const fichier = codeInput.files?.[0]
    if (!fichier) return
    attente = 'code'
    message = ''
    proposition = null
    try {
      const r = await envoyerImage(`/api/livres/${id}/isbn/photo`, fichier)
      fiche = { ...fiche, isbn: r.isbn }
    } catch (err) {
      if (err.statut === 401) ondeconnecte(); else message = err.message
      return
    } finally { attente = '' }
    await chercherNotice()
  }
  function reprendre() {
    const n = proposition.notice
    fiche = { ...fiche, titre: n.titre || fiche.titre, auteur: n.auteur || fiche.auteur, editeur: n.editeur || fiche.editeur,
              annee: n.annee || fiche.annee, isbn: n.isbn }
    proposition = null
  }
  const ouvrirFiche = () => {
    fiche = { titre: l.titre, auteur: l.auteur, langue: l.langue, editeur: l.editeur, annee: l.annee, isbn: l.isbn }
    proposition = null
    edition = true
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

  // Tuiles du bilan des pages (0.4.1) : inventaire des numéros, puis contre-lecture par le PC
  let filtre = $state(null)
  function tuiles(b) {
    const inv = b.inventaire, k = b.contre
    const sansNumero = l.liste_pages.filter((p) => !p.ecartee && p.numero == null).length
    const enAttente = k ? k.attente + k.calcul : 0
    return [
      { id: 'manquantes', nom: 'Manquantes', n: inv.manquantes.length, alerte: true, valeur: plages(inv.manquantes) || 'aucune' },
      { id: 'a_verifier', nom: 'Trous à vérifier', n: inv.a_verifier.length, alerte: true,
        valeur: inv.a_verifier.length ? inv.a_verifier.map((v) => `${v.manquent} entre ${v.entre[0]} et ${v.entre[1]}`).join(' ; ') : 'rien' },
      { id: 'doubles', nom: 'En double', n: inv.doubles.length, valeur: plages(inv.doubles) || 'aucune' },
      { id: 'sans_numero', nom: 'Sans numéro lu', n: sansNumero, valeur: `${sansNumero}` },
      { id: 'a_relire', nom: 'Mots à relire (PC)', n: k?.a_relire.length ?? 0, alerte: true,
        valeur: !k?.pc ? 'pas de PC' : k.a_relire.length ? `${k.a_relire.length} page${k.a_relire.length > 1 ? 's' : ''}`
          : enAttente ? `PC : ${k.faite} faite${k.faite > 1 ? 's' : ''}, ${enAttente} en attente` : 'rien' },
    ]
  }
  const nomsFiltre = { manquantes: 'pages manquantes', a_verifier: 'trous à vérifier', doubles: 'pages en double',
                       sans_numero: 'pages sans numéro lu', a_relire: 'pages aux mots à relire' }
  function garder(it, b) {
    if (!filtre) return true
    const inv = b.inventaire
    if (filtre === 'manquantes') return it.type === 'trou'
    if (filtre === 'a_verifier') {
      if (it.type === 'doute') return true
      // les pages qui bordent un trou à vérifier, et les pages sans numéro entre les deux
      return it.type === 'page' && !it.ecartee && inv.a_verifier.some((v) =>
        it.numero === v.entre[0] || it.numero === v.entre[1] || (it.numero == null && entre(it, v.entre)))
    }
    if (it.type !== 'page') return false
    if (filtre === 'doubles') return !it.ecartee && inv.doubles.includes(it.numero)
    if (filtre === 'sans_numero') return !it.ecartee && it.numero == null
    if (filtre === 'a_relire') return aRelire.has(it.rang)
    return true
  }
  // Une page sans numéro est « entre » a et b si elle se trouve après la page a et avant la page b dans l'ordre du livre
  function entre(page, [a, b]) {
    const liste = l.liste_pages
    const i = liste.findIndex((p) => p.rang === page.rang)
    const ia = liste.findIndex((p) => p.numero === a), ib = liste.findIndex((p) => p.numero === b)
    return ia >= 0 && ib >= 0 && i > ia && i < ib
  }

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
        <label class="flex flex-col gap-1.5 text-sm">Auteur <span class="text-xs text-muted-foreground">plusieurs : séparés par des virgules</span>
          <input bind:value={fiche.auteur} class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" /></label>
        <div class="grid gap-3 sm:grid-cols-[1fr_7rem]">
          <label class="flex flex-col gap-1.5 text-sm">Éditeur
            <input bind:value={fiche.editeur} class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" /></label>
          <label class="flex flex-col gap-1.5 text-sm">Année
            <input bind:value={fiche.annee} inputmode="numeric" maxlength="4" class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" /></label>
        </div>
        <div class="flex flex-wrap items-end gap-2">
          <label class="flex min-w-48 flex-1 flex-col gap-1.5 text-sm">ISBN
            <input bind:value={fiche.isbn} inputmode="numeric" placeholder="vide : cherché dans le texte lu"
                   class="h-10 rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring" /></label>
          <input bind:this={codeInput} type="file" accept="image/*" capture="environment" class="hidden" onchange={codeChoisi} tabindex="-1" aria-hidden="true" />
          <Button type="button" variant="outline" onclick={() => { codeInput.value = ''; codeInput.click() }} disabled={attente === 'code'}>
            <Camera class="size-4" aria-hidden="true" /> {attente === 'code' ? 'Lecture du code…' : 'Photographier le code-barres'}</Button>
          <Button type="button" variant="outline" onclick={chercherNotice} disabled={attente === 'notice'}>
            {attente === 'notice' ? 'Recherche…' : 'Chercher la fiche par l\'ISBN'}</Button>
        </div>
        {#if proposition}
          <div class="rounded-xl border border-primary/50 p-3 text-sm" role="status">
            {#if proposition.notice}
              <p><span class="text-muted-foreground">{proposition.notice.source} propose :</span>
                <span class="font-medium">{proposition.notice.titre}</span>{proposition.notice.auteur ? ` — ${proposition.notice.auteur}` : ''}
                {[proposition.notice.editeur, proposition.notice.annee].filter(Boolean).length ? ` (${[proposition.notice.editeur, proposition.notice.annee].filter(Boolean).join(', ')})` : ''}</p>
              <div class="mt-2"><Button type="button" size="sm" onclick={reprendre}>Reprendre dans la fiche</Button></div>
            {:else}
              <p>{proposition.message}</p>
            {/if}
          </div>
        {/if}
        <p class="text-sm text-muted-foreground">Couverture : {l.couverture ? `la page de rang ${l.couverture}` : 'la première page'}. Pour en changer, ouvre une page et touche « Prendre comme couverture ».</p>
        <div class="flex gap-2"><Button type="submit" disabled={attente === 'fiche'}>Enregistrer la fiche</Button>
          <Button type="button" variant="ghost" onclick={() => (edition = false)}>Annuler</Button></div>
      </form>
    {:else}
      <div class="flex flex-wrap items-start justify-between gap-3">
        <h1 class="lettrine-titre text-4xl md:text-5xl">{l.titre}</h1>
        <!-- 0.4.4 : un vrai bouton (le lien gris de la ligne d'infos passait inaperçu) -->
        <Button variant="outline" onclick={ouvrirFiche} class="mt-1 shrink-0">
          <Pencil class="size-4" aria-hidden="true" /> Modifier la fiche
        </Button>
      </div>
      <p class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
        {#if l.auteur}<span>{l.auteur}</span>{/if}
        {#if l.editeur || l.annee}<span>{[l.editeur, l.annee].filter(Boolean).join(', ')}</span>{/if}
        {#if l.isbn}<span>ISBN {l.isbn}</span>{/if}
        <span>{b.pages} pages dans le PDF</span>
        {#if !l.isbn}<span class="text-sm">pas d'ISBN</span>{/if}
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
      <!-- Chaque tuile filtre la grille des pages : un clic montre les pages en question, un second clic montre tout -->
      <div class="mb-4 grid max-w-4xl grid-cols-2 gap-3 md:grid-cols-5" role="group" aria-label="Montrer seulement">
        {#each tuiles(b) as t (t.id)}
          <button type="button" aria-pressed={filtre === t.id} disabled={!t.n} onclick={() => (filtre = filtre === t.id ? null : t.id)}
                  class="rounded-xl border bg-card p-3 text-left transition-colors enabled:hover:border-primary/60 aria-pressed:border-primary aria-pressed:bg-secondary disabled:cursor-default">
            <span class="block text-sm text-muted-foreground">{t.nom}</span>
            <span class="mt-1 block font-medium {t.n && t.alerte ? 'text-primary' : ''}">{t.valeur}</span>
          </button>
        {/each}
      </div>
      <p class="mb-4 max-w-3xl text-sm text-muted-foreground">
        Les numéros viennent de Mistral dès qu'une page est lue (avant, d'une lecture locale moins sûre).
        Vérifie avec le sommaire du livre : un numéro faux se corrige d'un clic, une page en double s'écarte.
        Une page manquante se reprend à l'iPhone avec « Prendre » : la photo est redressée, recadrée et rangée à sa place.
        Un clic sur une page ouvre sa relecture (image et texte côte à côte). Un clic sur une tuile ci-dessus ne montre que les pages en question.
      </p>
      <input bind:this={photoInput} type="file" accept="image/*" capture="environment" class="hidden" onchange={photoChoisie} tabindex="-1" aria-hidden="true" />
      {#if attente === 'photo'}<p class="mb-3 text-sm" role="status">Envoi de la photo…</p>{/if}

      {#if filtre}
        <p class="mb-3 flex flex-wrap items-center gap-3 text-sm" role="status">
          <span>Seulement les {nomsFiltre[filtre]} ({grille.filter((it) => garder(it, b)).length}).</span>
          <Button size="sm" variant="ghost" onclick={() => (filtre = null)}>Tout montrer</Button>
        </p>
      {/if}
      <ul class="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6 xl:grid-cols-8" aria-label="Pages du PDF">
        {#each grille.filter((it) => garder(it, b)) as it (it.type === 'page' ? 'p' + it.rang : it.type + (it.de ?? it.entre?.join('-')))}
          {#if it.type === 'trou'}
            <li class="flex aspect-[3/4] flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-primary/70 p-2 text-center text-sm text-primary">
              <span>{it.de === it.a ? `Page ${it.de}` : `Pages ${it.de} à ${it.a}`}<span class="block text-xs">manquante{it.de === it.a ? '' : 's'}</span></span>
              <Button size="sm" variant="outline" onclick={() => prendre(it.de)} disabled={attente === 'photo'} aria-label={`Prendre la page ${it.de} en photo`}>
                <Camera class="size-4" aria-hidden="true" /> Prendre {it.de === it.a ? '' : it.de}
              </Button>
            </li>
          {:else if it.type === 'doute'}
            <li class="flex aspect-[3/4] flex-col items-center justify-center rounded-lg border-2 border-dashed p-2 text-center text-xs text-muted-foreground">
              {it.manquent} page{it.manquent > 1 ? 's' : ''} manque{it.manquent > 1 ? 'nt' : ''} entre {it.entre[0]} et {it.entre[1]} ?
            </li>
          {:else}
            <li class="flex flex-col gap-1 {it.ecartee ? 'opacity-40' : ''}">
              <a href={`#/livre/${id}/page/${it.rang}`} title="Relire cette page"
                 class="relative block overflow-hidden rounded-lg border bg-white {it.numero == null && !it.ecartee ? 'border-dashed border-muted-foreground' : ''}">
                <img src={`/api/livres/${id}/pages/${it.rang}.jpg?cote=260`} alt={`Page ${it.numero ?? 'sans numéro'} (rang ${it.rang} du PDF)`}
                     loading="lazy" class="aspect-[3/4] w-full object-cover object-top" />
                {#if it.source === 'photo'}<span class="absolute top-1 right-1 rounded bg-background/85 p-0.5" title="Reprise à l'iPhone"><Camera class="size-3.5" aria-label="Reprise à l'iPhone" /></span>{/if}
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
              {#if aRelire.has(it.rang)}
                <span class="text-xs font-medium text-primary">{it.doutes ? `${it.doutes} mot${it.doutes > 1 ? 's' : ''} à relire` : 'lectures divergentes'}</span>
              {:else if !it.ecartee && (it.lecture !== 'attente' || it.rendu_choisi === 'image')}
                <span class="text-xs {it.lecture === 'erreur' ? 'text-destructive' : 'text-muted-foreground'}" title={it.lecture_erreur}>
                  {it.rendu_choisi === 'image' ? 'gardée en image' : it.texte_main ? 'corrigée' : lectureNom[it.lecture]}</span>
              {/if}
            </li>
          {/if}
        {/each}
      </ul>

      <form class="mt-4 flex flex-wrap items-center gap-2 text-sm" onsubmit={(e) => { e.preventDefault(); prendre(numeroReprise) }}>
        <label for="numero-reprise" class="text-muted-foreground">Reprendre une autre page, n°</label>
        <input id="numero-reprise" bind:value={numeroReprise} inputmode="numeric" class="h-9 w-20 rounded-lg border border-input bg-transparent px-2" />
        <Button type="submit" size="sm" variant="outline" disabled={!numeroReprise || attente === 'photo'}><Camera class="size-4" aria-hidden="true" /> Prendre</Button>
      </form>

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
          {#if b.contre}
            <div class="mt-3 border-t pt-3 text-sm">
              {#if b.contre.pc}
                <p class="text-muted-foreground">
                  Contre-lecture par le PC : {b.contre.faite} page{b.contre.faite > 1 ? 's' : ''} relue{b.contre.faite > 1 ? 's' : ''}
                  · {b.contre.attente + b.contre.calcul} en attente{#if b.contre.erreur} · {b.contre.erreur} en erreur{/if}
                </p>
                {#if b.contre.a_relire.length}
                  <p class="mt-2 flex flex-wrap items-center gap-3">
                    <span>{b.contre.a_relire.length} page{b.contre.a_relire.length > 1 ? 's' : ''} à relire : Mistral et Marker n'y lisent pas les mêmes mots.</span>
                    <Button size="sm" href={`#/livre/${id}/page/${b.contre.a_relire[0]}`}>Relire la première</Button>
                  </p>
                {/if}
              {:else}
                <p class="text-muted-foreground">Pas de contre-lecture : aucun jeton pour le PC de calcul dans la stack (voir Connexion).</p>
              {/if}
            </div>
          {/if}
          {#if b.estimation.pages}
            <div class="mt-4 flex flex-wrap items-center gap-3">
              <Button onclick={() => faireLire()} disabled={lectureSeule || attente === 'lire'}>
                Faire lire {b.estimation.pages} page{b.estimation.pages > 1 ? 's' : ''} par Mistral
              </Button>
              <span class="text-sm text-muted-foreground">environ {b.estimation.dollars.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} $
                (livre : environ {euros(b.estimation.apres)} €{b.estimation.plafond > 0 && !b.estimation.leve ? ` pour un plafond de ${euros(b.estimation.plafond)} €` : ''})</span>
              {#if lectureSeule}<Badge variant="outline">lecture seule : rien n'est envoyé</Badge>{/if}
            </div>
            {#if plafond}
              <div class="mt-3 flex flex-wrap items-center gap-3 rounded-xl border p-3 text-sm" role="alert">
                <span class="min-w-0 flex-1">{plafond}</span>
                <Button variant="outline" onclick={() => faireLire(true)} disabled={attente === 'lire'}>Dépasser pour ce livre</Button>
                <Button variant="ghost" onclick={() => (plafond = '')}>Annuler</Button>
              </div>
            {/if}
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
        <div class="flex flex-wrap items-center gap-3 border-t pt-4">
          {#if l.pdf_demande}
            <p class="text-sm" role="status">Mise en page du PDF A5… quelques minutes pour un gros livre. Tu peux fermer cette page.</p>
          {:else}
            <Button variant="outline" onclick={() => geste('pdf', `/api/livres/${id}/pdf`)} disabled={attente === 'pdf' || (l.etat === 'lecture' && l.lecture_demandee)}>
              {b.pdf ? 'Refaire le PDF A5' : 'Mettre en page un PDF A5'}</Button>
            {#if b.pdf}<Button variant="outline" href={`/api/livres/${id}/telecharger/pdf`}><Download class="size-4" aria-hidden="true" /> PDF A5</Button>{/if}
            <span class="text-sm text-muted-foreground">Le livre recomposé, à lire à l'écran ou à imprimer : couverture, sommaire, pages du livre papier en marge.</span>
          {/if}
          {#if l.pdf_erreur}<p class="w-full text-sm text-destructive" role="alert">PDF A5 en échec : {l.pdf_erreur}</p>{/if}
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
      <p class="mb-2 text-sm">Le livre part dans la corbeille (écran Livres) : il peut y être restauré pendant 30 jours, puis le PDF importé, les pages et le texte lu sont effacés du NAS. Un livre déjà déposé reste dans Grimmory.</p>
      <div class="flex gap-2"><Button variant="destructive" onclick={supprimer} disabled={attente === 'supprimer'}>Supprimer ce livre</Button>
        <Button variant="ghost" onclick={() => (suppression = false)}>Garder</Button></div>
    {:else}
      <Button variant="ghost" onclick={() => (suppression = true)}>Supprimer ce livre…</Button>
    {/if}
  </footer>
{/if}
