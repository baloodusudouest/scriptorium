<script>
  // « Réglages » : ce qui n'est pas un service. Le journal des écritures, puis la version et la déconnexion.
  import { onMount } from 'svelte'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { session, deconnecter } = $props()
  let journal = $state(null)
  const noms = { import: 'Import', lecture_mistral: 'Lecture par Mistral', depot_grimmory: 'Dépôt dans Grimmory', suppression: 'Suppression' }

  onMount(async () => { try { journal = await api.get('/api/journal') } catch { journal = [] } })
</script>

<header class="mb-5">
  <h1 class="titre">Réglages</h1>
</header>

<section class="max-w-3xl rounded-2xl border bg-card p-5">
  <h2 class="text-lg font-semibold">Écriture</h2>
  <p class="mt-1 text-sm text-muted-foreground">
    {session.lecture_seule
      ? 'Lecture seule : rien n\'est envoyé à Mistral et rien n\'est déposé dans Grimmory. À retirer dans la stack (SCRIPTORIUM_LECTURE_SEULE) quand le premier jour s\'est bien passé.'
      : 'Scriptorium envoie les pages à Mistral et dépose les livres dans Grimmory, toujours sur ton clic. Pour le premier jour d\'une nouvelle version : SCRIPTORIUM_LECTURE_SEULE=oui dans la stack.'}
  </p>
</section>

<section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-labelledby="titre-journal">
  <h2 id="titre-journal" class="text-lg font-semibold">Journal</h2>
  {#if journal === null}
    <p class="mt-1 text-sm text-muted-foreground">Lecture…</p>
  {:else if !journal.length}
    <p class="mt-1 text-sm text-muted-foreground">Rien encore : le journal note chaque import, chaque lecture par Mistral, chaque dépôt et chaque suppression.</p>
  {:else}
    <ul class="mt-2 divide-y text-sm">
      {#each journal as j (j.id)}
        <li class="flex flex-wrap justify-between gap-x-4 py-2">
          <span><span class="font-medium">{noms[j.quoi] ?? j.quoi}</span>{#if j.titre} · {j.titre}{/if}{#if j.detail} · <span class="text-muted-foreground">{j.detail}</span>{/if}</span>
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
