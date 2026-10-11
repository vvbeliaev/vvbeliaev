import '@fontsource-variable/sora';
import '@fontsource-variable/hanken-grotesk';
import '@fontsource-variable/jetbrains-mono';
import './app.css';

import { mount } from 'svelte';

import App from './App.svelte';

const target = document.getElementById('app');
if (!target) throw new Error('no #app element');

export default mount(App, { target });
