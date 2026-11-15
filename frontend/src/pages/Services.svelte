<script>
  // « Connexion » : une tuile par service extérieur, avec son voyant. Toucher une tuile ouvre le service :
  // ce que Scriptorium y lit et y écrit, et le geste « Vérifier ».
  // (pages/Connexion.svelte est la page du mot de passe : ne pas confondre.)
  import { onMount } from 'svelte'
  import Sparkles from '@lucide/svelte/icons/sparkles'
  import Library from '@lucide/svelte/icons/library'
  import HardDrive from '@lucide/svelte/icons/hard-drive'
  import Cpu from '@lucide/svelte/icons/cpu'
  import { api } from '$lib/api.js'
  import { Button } from '$lib/components/ui/button/index.js'

  let { ondeconnecte } = $props()
  let s = $state(null)
  let choisi = $state(null)
  let message = $state('')
  let verification = $state(null)

  async function lire() {
    try { s = await api.get('/api/services') } catch (err) { if (err.statut === 401) ondeconnecte?.(); else message = err.message }
  }
  async function verifierMistral() {
    verification = { message: 'Vérification…' }
    try { verification = await api.post('/api/services/mistral/verifier') } catch (err) { verification = { ok: false, message: err.message } }
  }
  onMount(lire)

  // « il y a 3 min » : dernier passage du PC de calcul
  function depuis(iso) {
    if (!iso) return 'jamais vu'
    const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
    if (min < 2) return 'vu à l\'instant'
    if (min < 120) return `vu il y a ${min} min`
    if (min < 2880) return `vu il y a ${Math.round(min / 60)} h`
    return `vu le ${new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })}`
  }
  const go = (o) => (o / 1e9).toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  let tuiles = $derived(s ? [
    { id: 'mistral', nom: 'Mistral OCR', icone: Sparkles, ok: s.mistral.cle, etat: s.mistral.cle ? `${s.mistral.facturees} pages facturées` : 'aucune clé' },
    { id: 'pc', nom: 'PC de calcul', icone: Cpu, ok: s.pc.configure && !!s.pc.vu_le && Date.now() - new Date(s.pc.vu_le) < 600000,
      etat: s.pc.configure ? `${depuis(s.pc.vu_le)} · ${s.pc.en_attente} page${s.pc.en_attente > 1 ? 's' : ''} en attente` : 'aucun jeton' },
    { id: 'grimmory', nom: 'Grimmory', icone: Library, ok: s.grimmory.inscriptible, etat: s.grimmory.inscriptible ? 'dépôt possible' : 'dossier inaccessible' },
    { id: 'disque', nom: 'Dossier de données', icone: HardDrive, ok: s.disque.inscriptible, etat: `${go(s.disque.libre)} Go libres` },
  ] : [])
</script>

<header class="mb-5">
  <h1 class="titre">Connexion</h1>
</header>

{#if message}<p class="mb-4 text-sm text-destructive" role="alert">{message}</p>{/if}

<div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
  {#each tuiles as t (t.id)}
    {@const Icone = t.icone}
    <button type="button" aria-pressed={choisi === t.id} onclick={() => (choisi = choisi === t.id ? null : t.id)}
            class="flex min-h-28 flex-col gap-1 rounded-2xl border bg-card p-4 text-left transition-colors hover:border-primary aria-pressed:border-primary">
      <span class="flex items-start justify-between">
        <Icone class="size-6 text-primary" aria-hidden="true" />
        <span class="size-2.5 rounded-full {t.ok ? 'bg-valide' : 'bg-muted-foreground/40'}" aria-hidden="true"></span>
      </span>
      <span class="font-medium">{t.nom}</span>
      <span class="text-sm text-muted-foreground">{t.etat}</span>
    </button>
  {/each}
</div>

{#if s && choisi === 'mistral'}
  <section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-label="Mistral OCR">
    <h2 class="text-lg font-semibold">Mistral OCR</h2>
    <p class="mt-1 text-sm text-muted-foreground">
      Scriptorium lui envoie l'image de chaque page, sur ton clic « Faire lire » ; il renvoie le texte mis en forme et les illustrations.
      La clé reste dans la stack (SCRIPTORIUM_MISTRAL_CLE) et ne passe jamais par le navigateur.
      Modèle : {s.mistral.modele}. Estimation affichée : {s.mistral.prix_page} $ par page.
    </p>
    <div class="mt-3 flex flex-wrap items-center gap-3">
      <Button variant="outline" onclick={verifierMistral}>Vérifier</Button>
      {#if verification}<span class="text-sm {verification.ok === false ? 'text-destructive' : ''}" role="status">{verification.message}</span>{/if}
    </div>
  </section>
{:else if s && choisi === 'pc'}
  <section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-label="PC de calcul">
    <h2 class="text-lg font-semibold">PC de calcul</h2>
    <p class="mt-1 text-sm text-muted-foreground">
      Le PC relit chaque page avec Marker, sur son processeur, et rend le texte. Les mots qui diffèrent de la lecture de Mistral
      deviennent les mots à relire. Il vient chercher le travail lui-même, avec son jeton (SCRIPTORIUM_JETON_CALCUL) ; éteint, il ne bloque rien.
    </p>
    {#if s.pc.configure}
      <p class="mt-2 text-sm">{s.pc.vu_le ? `Dernier passage : ${new Date(s.pc.vu_le).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' })}` : 'Le PC n\'est encore jamais passé.'}
        {#if s.pc.moteur} · {s.pc.moteur}{/if} · {s.pc.en_attente} page{s.pc.en_attente > 1 ? 's' : ''} en attente.</p>
    {:else}
      <p class="mt-2 text-sm">Aucun jeton dans la stack : la porte du PC est fermée.</p>
    {/if}
    <p class="mt-2 text-sm text-muted-foreground">Mise en route : dossier <code>pc/</code> du dépôt (fichier <code>LISEZMOI.md</code>), lancé dans Docker Desktop.</p>
    <div class="mt-3"><Button variant="outline" onclick={lire}>Vérifier</Button></div>
  </section>
{:else if s && choisi === 'grimmory'}
  <section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-label="Grimmory">
    <h2 class="text-lg font-semibold">Grimmory</h2>
    <p class="mt-1 text-sm text-muted-foreground">
      Scriptorium dépose l'EPUB fabriqué dans le dossier d'import de Grimmory (SCRIPTORIUM_BOOKDROP), sur ton clic, sans jamais remplacer un fichier déjà présent.
      Il n'y lit rien d'autre.
    </p>
    <p class="mt-2 text-sm">{s.grimmory.configure ? (s.grimmory.inscriptible ? 'Le dossier est accessible en écriture.' : 'Le dossier est absent ou en lecture seule : vérifie le volume dans la stack.') : 'Aucun dossier réglé.'}</p>
    <div class="mt-3"><Button variant="outline" onclick={lire}>Vérifier</Button></div>
  </section>
{:else if s && choisi === 'disque'}
  <section class="mt-4 max-w-3xl rounded-2xl border bg-card p-5" aria-label="Dossier de données">
    <h2 class="text-lg font-semibold">Dossier de données</h2>
    <p class="mt-1 text-sm text-muted-foreground">Les PDF importés, les pages découpées, le texte lu et les livres fabriqués. Compte environ trois fois la taille du PDF par livre.</p>
    <p class="mt-2 text-sm">{go(s.disque.libre)} Go libres sur {go(s.disque.total)} Go{s.travail ? ` · en cours : ${s.travail}` : ''}.</p>
    <div class="mt-3"><Button variant="outline" onclick={lire}>Vérifier</Button></div>
  </section>
{:else}
  <p class="mt-4 text-sm text-muted-foreground">Touche un service pour voir son état et ce que Scriptorium y fait.</p>
{/if}
