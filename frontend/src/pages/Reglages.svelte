<script>
  // « Réglages » : ce qui n'est pas un service. L'écriture, les réglages d'usage et leur restauration (0.6),
  // le dossier de données (0.8.0 : venu de Connexion, ce n'est pas un service), le journal des écritures,
  // puis la version et la déconnexion.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { session, deconnecter } = $props()
  let journal = $state(null)
  const noms = {
    import: 'Import', lecture_mistral: 'Lecture par Mistral', depot_grimmory: 'Dépôt dans Grimmory', suppression: 'Suppression',
    reglages: 'Réglages', reglage_repris: 'Réglage repris de la stack', restauration: 'Restauration des réglages',
  }

  // ---------------------------------------------------------------- réglages d'usage
  // Repris une fois des anciennes variables de la stack au premier démarrage de la 0.6 ; ensuite, cet écran fait foi.
  const libelles = {
    recherche_web: 'Recherche en ligne de la fiche',
    prix_page: 'Prix estimé par page lue',
    dpi: 'Définition des pages découpées',
    plafond_livre: 'Plafond de dépense par livre',
  }
  let reglages = $state(null)        // valeurs enregistrées
  let saisie = $state(null)          // valeurs du formulaire
  let bornes = $state({})
  let etatReglages = $state('')
  let erreurReglages = $state('')
  let enregistrement = $state(false)

  async function lireReglages() {
    try {
      const r = await api.get('/api/reglages')
      reglages = r.reglages
      saisie = { ...r.reglages }
      bornes = r.bornes || {}
    } catch (err) { erreurReglages = err.message }
  }

  let modifie = $derived(!!(reglages && saisie) && Object.keys(reglages).some((k) => String(reglages[k]) !== String(saisie[k])))

  async function enregistrer(e) {
    e.preventDefault()
    erreurReglages = ''
    etatReglages = ''
    enregistrement = true
    try {
      const r = await api.put('/api/reglages', {
        recherche_web: !!saisie.recherche_web, prix_page: Number(saisie.prix_page), dpi: Number(saisie.dpi),
        plafond_livre: Number(saisie.plafond_livre),
      })
      reglages = r.reglages
      saisie = { ...r.reglages }
      etatReglages = 'Réglages enregistrés.'
      journal = await api.get('/api/journal').catch(() => journal)
    } catch (err) { erreurReglages = err.message }
    enregistrement = false
  }

  // ---------------------------------------------------------------- restaurer depuis une sauvegarde de l'Anneau
  let dates = $state(null)           // null : pas encore demandé
  let date = $state('')
  let apercu = $state(null)          // { le, version, differences }
  let messageRestaurer = $state('')
  let attenteRestaurer = $state(false)

  const texte = (k, v) => (typeof v === 'boolean' ? (v ? 'oui' : 'non') : k === 'prix_page' ? `${v} $` : k === 'plafond_livre' ? (Number(v) ? `${v} €` : 'aucun') : k === 'dpi' ? `${v} dpi` : String(v))
  const jour = (d) => new Date(`${d}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  async function chercherDates() {
    messageRestaurer = ''
    apercu = null
    attenteRestaurer = true
    try {
      dates = (await api.get('/api/restaurer')).dates
      date = dates[0] || ''
      if (date) await voir()
    } catch (err) { dates = []; messageRestaurer = err.message }
    attenteRestaurer = false
  }

  async function voir() {
    messageRestaurer = ''
    apercu = null
    if (!date) return
    try { apercu = await api.get(`/api/restaurer?le=${encodeURIComponent(date)}`) } catch (err) { messageRestaurer = err.message }
  }

  async function confirmer() {
    attenteRestaurer = true
    messageRestaurer = ''
    try {
      const r = await api.post('/api/restaurer', { le: date })
      reglages = r.reglages
      saisie = { ...r.reglages }
      messageRestaurer = r.appliques.length ? `Restauré : ${r.appliques.map((k) => libelles[k] ?? k).join(', ')}.` : 'Rien à changer.'
      apercu = { ...apercu, differences: [] }
      journal = await api.get('/api/journal').catch(() => journal)
    } catch (err) { messageRestaurer = err.message }
    attenteRestaurer = false
  }

  // ---------------------------------------------------------------- dossier de données (0.8.0, venu de Connexion)
  let dossier = $state(null)
  let erreurDossier = $state('')
  async function lireDossier() {
    erreurDossier = ''
    try { dossier = await api.get('/api/dossier') } catch (err) { erreurDossier = err.message }
  }
  const go = (o) => (o / 1e9).toLocaleString('fr-FR', { maximumFractionDigits: 1 })

  onMount(async () => {
    lireReglages()
    lireDossier()
    try { journal = await api.get('/api/journal') } catch { journal = [] }
  })

  const champ = 'h-10 w-full rounded-lg border border-input bg-transparent px-3 text-base outline-none focus:border-ring'
</script>

<header class="mb-5">
  <h1 class="titre">Réglages</h1>
</header>

<section class="max-w-3xl rounded-2xl border bg-card p-5">
  <h2 class="text-lg font-semibold">Écriture</h2>
  <p class="mt-1 text-sm text-muted-foreground">
    <!-- la lecture seule peut venir de toute la maison (MAISON_LECTURE_SEULE) ou de Scriptorium seul -->
    {#if session.lecture_seule && session.origine_lecture_seule === 'maison'}
      Lecture seule pour toute la maison (MAISON_LECTURE_SEULE) : rien n'est envoyé à Mistral et rien n'est déposé dans Grimmory. À retirer dans la stack quand le premier jour s'est bien passé, ou SCRIPTORIUM_LECTURE_SEULE=non pour rendre l'écriture à Scriptorium seul.
    {:else if session.lecture_seule}
      Lecture seule pour cette appli (SCRIPTORIUM_LECTURE_SEULE) : rien n'est envoyé à Mistral et rien n'est déposé dans Grimmory. À retirer dans la stack quand le premier jour s'est bien passé.
    {:else}
      Scriptorium envoie les pages à Mistral et dépose les livres dans Grimmory, toujours sur ton clic. Pour le premier jour d'une nouvelle version : MAISON_LECTURE_SEULE=oui (toute la maison) ou SCRIPTORIUM_LECTURE_SEULE=oui (cette appli) dans la stack.
    {/if}
  </p>
</section>

<section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-labelledby="titre-usage">
  <h2 id="titre-usage" class="text-lg font-semibold">Usage</h2>
  <p class="mt-1 text-sm text-muted-foreground">Ces réglages ne touchent que Scriptorium : ils se changent ici, même en lecture seule. L'Anneau les sauvegarde chaque nuit.</p>
  {#if erreurReglages && !saisie}
    <p class="mt-3 text-sm text-destructive" role="alert">{erreurReglages}</p>
  {:else if !saisie}
    <p class="mt-3 text-sm text-muted-foreground">Lecture…</p>
  {:else}
    <form class="mt-4 flex flex-col gap-4" onsubmit={enregistrer} aria-label="Réglages d'usage">
      <label class="flex items-start gap-3 text-sm">
        <input type="checkbox" bind:checked={saisie.recherche_web} class="mt-0.5 size-5 shrink-0 accent-[var(--app)]" />
        <span class="min-w-0">
          <span class="font-medium">{libelles.recherche_web}</span>
          <span class="block text-muted-foreground">Sur ton clic, l'ISBN du livre est envoyé à la BnF puis à Open Library pour proposer titre, auteurs, éditeur et année. Décoché : la fiche se remplit à la main.</span>
        </span>
      </label>
      <div class="grid gap-4 sm:grid-cols-2">
        <label class="flex min-w-0 flex-col gap-1.5 text-sm"><span class="font-medium">{libelles.prix_page}</span>
          <span class="text-xs text-muted-foreground">en dollars, pour l'estimation affichée avant une lecture par Mistral</span>
          <input type="number" inputmode="decimal" step="0.0001" min={bornes.prix_page?.[0]} max={bornes.prix_page?.[1]} required
                 bind:value={saisie.prix_page} class={champ} /></label>
        <label class="flex min-w-0 flex-col gap-1.5 text-sm"><span class="font-medium">{libelles.dpi}</span>
          <span class="text-xs text-muted-foreground">en points par pouce, pour les prochains PDF importés</span>
          <input type="number" inputmode="numeric" step="1" min={bornes.dpi?.[0]} max={bornes.dpi?.[1]} required
                 bind:value={saisie.dpi} class={champ} /></label>
        <label class="flex min-w-0 flex-col gap-1.5 text-sm"><span class="font-medium">{libelles.plafond_livre}</span>
          <span class="text-xs text-muted-foreground">en euros de lecture par Mistral (1 $ ≈ 0,90 €) ; au-delà, Scriptorium s'arrête et demande ; 0 : pas de plafond</span>
          <input type="number" inputmode="decimal" step="0.5" min={bornes.plafond_livre?.[0]} max={bornes.plafond_livre?.[1]} required
                 bind:value={saisie.plafond_livre} class={champ} /></label>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={!modifie || enregistrement}>{enregistrement ? 'Enregistrement…' : 'Enregistrer les réglages'}</Button>
        {#if erreurReglages}<span class="text-sm text-destructive" role="alert">{erreurReglages}</span>
        {:else if etatReglages}<span class="text-sm" role="status">{etatReglages}</span>{/if}
      </div>
    </form>
  {/if}
</section>

<section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-labelledby="titre-dossier">
  <h2 id="titre-dossier" class="text-lg font-semibold">Dossier de données</h2>
  <p class="mt-1 text-sm text-muted-foreground">Les PDF importés, les pages découpées, le texte lu et les livres fabriqués. Compte environ trois fois la taille du PDF par livre.</p>
  {#if dossier}
    <p class="mt-2 text-sm">{go(dossier.libre)} Go libres sur {go(dossier.total)} Go{dossier.travail ? ` · en cours : ${dossier.travail}` : ''}.</p>
    {#if !dossier.inscriptible}<p class="mt-1 text-sm text-destructive" role="alert">Le dossier n'est pas accessible en écriture : vérifie le volume dans la stack.</p>{/if}
  {:else if erreurDossier}
    <p class="mt-2 text-sm text-destructive" role="alert">{erreurDossier}</p>
  {:else}
    <p class="mt-2 text-sm text-muted-foreground">Lecture…</p>
  {/if}
  <div class="mt-3"><Button variant="outline" onclick={lireDossier}>Relire</Button></div>
</section>

<section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-labelledby="titre-restaurer">
  <h2 id="titre-restaurer" class="text-lg font-semibold">Restaurer les réglages</h2>
  <p class="mt-1 text-sm text-muted-foreground">Reprend les réglages d'usage d'une sauvegarde de l'Anneau. Rien d'autre ne change : ni les livres, ni la stack.</p>
  {#if dates === null}
    <div class="mt-3"><Button variant="outline" onclick={chercherDates} disabled={attenteRestaurer}>{attenteRestaurer ? 'Demande à l\'Anneau…' : 'Voir les sauvegardes'}</Button></div>
  {:else if dates.length}
    <label class="mt-3 flex min-w-0 flex-col gap-1.5 text-sm sm:max-w-sm"><span class="font-medium">Sauvegarde du</span>
      <select bind:value={date} onchange={voir} class="{champ} bg-card">
        {#each dates as d (d)}<option value={d}>{jour(d)}</option>{/each}
      </select></label>
    {#if apercu}
      {#if apercu.differences.length}
        <ul class="mt-3 divide-y text-sm" aria-label="Différences avec la sauvegarde">
          {#each apercu.differences as d (d.cle)}
            <li class="flex flex-wrap justify-between gap-x-4 py-2">
              <span class="font-medium">{libelles[d.cle] ?? d.cle}</span>
              <span class="tabular-nums"><span class="text-muted-foreground">{texte(d.cle, d.actuel)}</span> → {texte(d.cle, d.sauve)}</span>
            </li>
          {/each}
        </ul>
        <div class="mt-3"><Button onclick={confirmer} disabled={attenteRestaurer}>{attenteRestaurer ? 'Restauration…' : 'Restaurer ces réglages'}</Button></div>
      {:else}
        <p class="mt-3 text-sm text-muted-foreground">Les réglages actuels sont ceux de cette sauvegarde{apercu.version ? ` (Scriptorium ${apercu.version})` : ''}.</p>
      {/if}
    {/if}
  {/if}
  {#if messageRestaurer}<p class="mt-3 text-sm" role="status">{messageRestaurer}</p>{/if}
  {#if dates !== null && !dates.length}
    <div class="mt-3"><Button variant="outline" onclick={chercherDates} disabled={attenteRestaurer}>Réessayer</Button></div>
  {/if}
</section>

<section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-labelledby="titre-journal">
  <h2 id="titre-journal" class="text-lg font-semibold">Journal</h2>
  {#if journal === null}
    <p class="mt-1 text-sm text-muted-foreground">Lecture…</p>
  {:else if !journal.length}
    <p class="mt-1 text-sm text-muted-foreground">Rien encore : le journal note chaque import, chaque lecture par Mistral, chaque dépôt, chaque suppression et chaque changement de réglage.</p>
  {:else}
    <ul class="mt-2 divide-y text-sm">
      {#each journal as j (j.id)}
        <li class="flex flex-wrap justify-between gap-x-4 py-2">
          <span class="min-w-0 break-words"><span class="font-medium">{noms[j.quoi] ?? j.quoi}</span>{#if j.titre} · {j.titre}{/if}{#if j.detail} · <span class="text-muted-foreground">{j.detail}</span>{/if}</span>
          <time class="text-muted-foreground tabular-nums" datetime={j.le}>{new Date(j.le).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })}</time>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<p class="mt-6 flex max-w-3xl items-center justify-between gap-3 text-sm text-muted-foreground">
  <span>Scriptorium {session.version}</span>
  <Button variant="outline" onclick={deconnecter}>Se déconnecter</Button>
</p>
