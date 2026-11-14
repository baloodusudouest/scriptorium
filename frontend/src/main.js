import { mount } from 'svelte'
import '@fontsource-variable/inter'
// EB Garamond : la lettrine et le texte recomposé (on lit déjà le livre tel qu'il sortira)
import '@fontsource/eb-garamond/latin-400.css'
import '@fontsource/eb-garamond/latin-400-italic.css'
import '@fontsource/eb-garamond/latin-500.css'
import './app.css'
import App from './App.svelte'

export default mount(App, { target: document.getElementById('app') })
